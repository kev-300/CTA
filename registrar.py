import os
import sys
import sqlite3
from datetime import datetime, time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QLabel

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registros.db")
INICIO, FIN = time(6, 40), time(7, 30)


def registrar_asistencia(con, persona_id, metodo="manual"):
    """Punto de entrada único. El módulo de rostro/huella llamará esta misma
    función con el persona_id identificado y metodo='rostro' o 'huella'.
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
        self.resize(420, 170)
        self.con = sqlite3.connect(DB)
        self.con.execute("PRAGMA foreign_keys = ON")

        v = QVBoxLayout(self)
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Ingresa tu identificación y presiona Enter")
        self.entrada.returnPressed.connect(self.registrar)
        self.msg = QLabel("")
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setWordWrap(True)
        v.addWidget(self.entrada)
        v.addWidget(self.msg)

    def mostrar(self, texto, color):
        self.msg.setText(texto)
        self.msg.setStyleSheet(f"color: {color}; font-size: 15px;")

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
        pid, nombre, rol = fila
        nuevo, estado, hora = registrar_asistencia(self.con, pid)
        if not nuevo:
            self.mostrar(f"{nombre} ya registró asistencia hoy", "#f59e0b")
        elif estado == "PRESENTE":
            self.mostrar(f"{nombre} ({rol})\nRegistrado a las {hora}", "#34d399")
        else:
            self.mostrar(f"{nombre} ({rol})\nRegistrado a las {hora} — fuera de horario", "#f59e0b")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Registro()
    w.show()
    sys.exit(app.exec())
