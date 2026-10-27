"""Panel 'Registrar Asistencia' para gestor_local.py (id manual, rostro o huella)."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from rostro import Camara, cargar_reconocedor, UMBRAL
from registrar import registrar_asistencia, ACIERTOS, TIEMPO_MAX
from huella import LectorAsistencia


class PanelAsistencia(QWidget):
    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self.rec, self.candidato, self.aciertos = None, None, 0

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        titulo = QLabel("Registrar Asistencia")
        titulo.setObjectName("title")
        sub = QLabel("Registra la asistencia con identificación, rostro o huella.")
        sub.setObjectName("subtitle")
        v.addWidget(titulo)
        v.addWidget(sub)
        v.addSpacing(16)

        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Ingresa tu identificación y presiona Enter")
        self.entrada.setFixedWidth(420)
        self.entrada.returnPressed.connect(self.registrar_id)
        self.btn_rostro = QPushButton("Reconocer por rostro")
        self.btn_rostro.setObjectName("small")
        self.btn_rostro.setFixedWidth(420)
        self.btn_rostro.clicked.connect(self.alternar_rostro)
        self.btn_huella = QPushButton("Reconocer por huella")
        self.btn_huella.setObjectName("small")
        self.btn_huella.setFixedWidth(420)
        self.btn_huella.clicked.connect(self.alternar_huella)
        self.cam = Camara(self.al_reconocer)
        self.cam.hide()
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        self.msg.setFixedWidth(420)
        self.msg.setMinimumHeight(90)
        self.msg.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        for w in (self.entrada, self.btn_rostro, self.btn_huella, self.cam, self.msg):
            v.addWidget(w, 0, Qt.AlignLeft)
        v.addStretch()

        self.espera = QTimer(self)
        self.espera.setSingleShot(True)
        self.espera.timeout.connect(self.tiempo_agotado)

        # La lógica de huella vive en huella.py: aquí solo se conectan las señales
        self.lector = LectorAsistencia(con, self)
        self.lector.mensaje.connect(lambda t: self.mostrar(t, "#4b5563"))
        self.lector.persona.connect(lambda pid, nom, rol: self.registrar_persona(pid, nom, rol, "huella"))
        self.lector.desconocida.connect(
            lambda slot: self.mostrar(f"Huella reconocida (ID {slot}) pero sin un usuario activo asociado.", "#b91c1c"))
        self.lector.no_reconocida.connect(
            lambda: self.mostrar("Huella no reconocida. Intenta de nuevo.", "#b91c1c"))
        self.lector.terminado.connect(self.fin_huella)

    # --- API que usa gestor_local ---
    def al_mostrar(self):
        self.entrada.setFocus()

    def parar(self):
        self.espera.stop()
        self.cam.detener()
        self.cam.hide()
        self.btn_rostro.setText("Reconocer por rostro")
        self.parar_huella()

    # --- lógica interna ---
    def mostrar(self, texto, color="#000"):
        self.msg.setText(texto)
        self.msg.setStyleSheet(f"color: {color}; font-size: 15px;")

    def registrar_id(self):
        ident = self.entrada.text().strip()
        self.entrada.clear()
        if not ident:
            return
        fila = self.con.execute(
            """SELECT p.id, p.nombre, r.nombre FROM persona p
               JOIN rol r ON r.id = p.rol_id
               WHERE p.identificacion = ? AND p.activo = 1""", (ident,)).fetchone()
        if not fila:
            self.mostrar("Identificación no registrada", "#b91c1c")
            return
        self.registrar_persona(*fila, metodo="manual")

    def registrar_persona(self, pid, nombre, rol, metodo):
        nuevo, estado, hora = registrar_asistencia(self.con, pid, metodo)
        if not nuevo:
            self.mostrar(f"{nombre} ya registró asistencia hoy", "#b45309")
        elif estado == "PRESENTE":
            self.mostrar(f"{nombre} ({rol})\nRegistrado a las {hora}", "#15803d")
        else:
            self.mostrar(f"{nombre} ({rol})\nRegistrado a las {hora} — fuera de horario", "#b45309")

    # --- rostro ---
    def alternar_rostro(self):
        if self.cam.activa():
            self.parar()
            return
        self.parar_huella()               # el rostro y la huella no corren a la vez
        self.rec = cargar_reconocedor(self.con)
        if self.rec is None:
            self.mostrar("No hay rostros registrados", "#b91c1c")
            return
        self.candidato, self.aciertos = None, 0
        self.cam.show()
        if not self.cam.iniciar():
            self.cam.hide()
            self.mostrar("No se pudo abrir la cámara", "#b91c1c")
            return
        self.btn_rostro.setText("Cancelar")
        self.mostrar("Mira a la cámara...")
        self.espera.start(TIEMPO_MAX)

    def tiempo_agotado(self):
        self.parar()
        self.mostrar("No se reconoció el rostro", "#b91c1c")

    def al_reconocer(self, cara):
        pid, conf = self.rec.predict(cara)
        if conf < UMBRAL:
            self.aciertos = self.aciertos + 1 if pid == self.candidato else 1
            self.candidato = pid
        else:
            self.candidato, self.aciertos = None, 0
        self.mostrar(f"Reconociendo... ({conf:.0f})")
        if self.aciertos >= ACIERTOS:
            self.parar()
            fila = self.con.execute(
                """SELECT p.nombre, r.nombre FROM persona p
                   JOIN rol r ON r.id = p.rol_id WHERE p.id = ?""", (pid,)).fetchone()
            self.registrar_persona(pid, *fila, metodo="rostro")

    # --- huella ---
    def alternar_huella(self):
        if self.lector.activo():
            self.parar_huella()
            self.mostrar("Lector de huella detenido")
            return
        if self.cam.activa():             # cierra la cámara si estaba activa
            self.espera.stop()
            self.cam.detener()
            self.cam.hide()
            self.btn_rostro.setText("Reconocer por rostro")
        self.btn_huella.setText("Detener lector de huella")
        self.mostrar("Conectando con el lector...", "#4b5563")
        self.lector.iniciar()

    def parar_huella(self):
        self.lector.detener()
        self.btn_huella.setText("Reconocer por huella")

    def fin_huella(self, ok, detalle):
        self.btn_huella.setText("Reconocer por huella")
        if not ok:
            self.mostrar(f"Lector de huella detenido: {detalle}", "#b91c1c")