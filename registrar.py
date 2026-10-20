import os
import sys
import sqlite3
from datetime import datetime, time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit,
                               QLabel, QPushButton)
from rostro import Camara, cargar_reconocedor, UMBRAL

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registros.db")
INICIO, FIN = time(6, 40), time(7, 30)
ACIERTOS = 5          # frames seguidos que deben coincidir con la misma persona
TIEMPO_MAX = 15000    # ms para reconocer antes de rendirse


def registrar_asistencia(con, persona_id, metodo="manual"):
    """Punto de entrada único (id manual, rostro o huella).
    Devuelve (se_registró, estado, hora)."""
    ahora = datetime.now()
    hora = ahora.strftime("%H:%M:%S")
    estado = "PRESENTE" if INICIO <= ahora.time() <= FIN else "FUERA_DE_HORARIO"
    cur = con.execute("""
        INSERT INTO asistencia (persona_id, fecha, hora, estado, metodo)
        VALUES (?,?,?,?,?)
        ON CONFLICT(persona_id, fecha) DO UPDATE SET
            hora = excluded.hora, estado = excluded.estado, metodo = excluded.metodo
        WHERE asistencia.estado = 'AUSENTE'""",
        (persona_id, ahora.date().isoformat(), hora, estado, metodo))
    con.commit()
    return cur.rowcount == 1, estado, hora


class Registro(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Registro de asistencia")
        self.con = sqlite3.connect(DB)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.rec = None
        self.candidato, self.aciertos = None, 0

        v = QVBoxLayout(self)
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Ingresa tu identificación y presiona Enter")
        self.entrada.returnPressed.connect(self.registrar)
        self.btn_rostro = QPushButton("Reconocer por rostro")
        self.btn_rostro.clicked.connect(self.alternar_rostro)
        self.cam = Camara(self.al_detectar_cara)
        self.cam.hide()
        self.msg = QLabel("")
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setWordWrap(True)
        for w in (self.entrada, self.btn_rostro, self.cam, self.msg):
            v.addWidget(w)
        v.setAlignment(self.cam, Qt.AlignHCenter)

        self.espera = QTimer(self)
        self.espera.setSingleShot(True)
        self.espera.timeout.connect(self.tiempo_agotado)
        self.resize(520, 160)

    def mostrar(self, texto, color):
        self.msg.setText(texto)
        self.msg.setStyleSheet(f"color: {color}; font-size: 15px;")

    # ---------- Registro por identificación ----------
    def registrar(self):
        ident = self.entrada.text().strip()
        self.entrada.clear()
        if not ident:
            return
        fila = self.con.execute(
            """SELECT p.id, p.nombre, r.nombre FROM persona p
               JOIN rol r ON r.id = p.rol_id
               WHERE p.identificacion = ? AND p.activo = 1""", (ident,)).fetchone()
        if not fila:
            self.mostrar("Identificación no registrada", "#ef4444")
            return
        self.registrar_persona(*fila, metodo="manual")

    def registrar_persona(self, pid, nombre, rol, metodo):
        nuevo, estado, hora = registrar_asistencia(self.con, pid, metodo)
        if not nuevo:
            self.mostrar(f"{nombre} ya registró asistencia hoy", "#f59e0b")
        elif estado == "PRESENTE":
            self.mostrar(f"{nombre} ({rol})\nRegistrado a las {hora}", "#34d399")
        else:
            self.mostrar(f"{nombre} ({rol})\nRegistrado a las {hora} — fuera de horario", "#f59e0b")

    # ---------- Registro por rostro ----------
    def alternar_rostro(self):
        if self.cam.activa():
            self.parar_rostro()
            return
        self.rec = cargar_reconocedor(self.con)
        if self.rec is None:
            self.mostrar("No hay rostros registrados", "#ef4444")
            return
        self.candidato, self.aciertos = None, 0
        self.cam.show()
        if not self.cam.iniciar():
            self.cam.hide()
            self.mostrar("No se pudo abrir la cámara", "#ef4444")
            return
        self.btn_rostro.setText("Cancelar")
        self.mostrar("Mira a la cámara...", "#9ca3af")
        self.espera.start(TIEMPO_MAX)

    def parar_rostro(self):
        self.espera.stop()
        self.cam.detener()
        self.cam.hide()
        self.btn_rostro.setText("Reconocer por rostro")
        self.adjustSize()

    def tiempo_agotado(self):
        self.parar_rostro()
        self.mostrar("No se reconoció el rostro", "#ef4444")

    def al_detectar_cara(self, cara):
        pid, conf = self.rec.predict(cara)
        if conf < UMBRAL:
            self.aciertos = self.aciertos + 1 if pid == self.candidato else 1
            self.candidato = pid
        else:
            self.candidato, self.aciertos = None, 0
        self.mostrar(f"Reconociendo... ({conf:.0f})", "#9ca3af")   # conf: para ajustar UMBRAL
        if self.aciertos >= ACIERTOS:
            self.parar_rostro()
            fila = self.con.execute(
                """SELECT p.nombre, r.nombre FROM persona p
                   JOIN rol r ON r.id = p.rol_id WHERE p.id = ?""", (pid,)).fetchone()
            self.registrar_persona(pid, *fila, metodo="rostro")

    def closeEvent(self, e):
        self.cam.detener()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Registro()
    w.show()
    sys.exit(app.exec())