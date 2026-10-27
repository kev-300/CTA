"""Panel 'Agregar Nuevo': alta y edición de personas, con captura de rostro y huella."""
import sqlite3
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QMessageBox,
)
from rostro import Camara, guardar_muestras
from huella import RegistroHuella, tiene_huella
from panel_base import PanelBase

MUESTRAS = 8   # fotos del rostro que se guardan por persona


class PanelAgregar(PanelBase):
    guardado = Signal()     # se guardó una persona (nueva o editada)

    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self.editando, self.n_rostros = None, 0
        self.muestras, self.contador = [], 0
        self.huella = RegistroHuella(con, self)   # la lógica vive en huella.py

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        enc = self.encabezado("Agregar Nuevo", "Registra un nuevo usuario.")
        self.tit_agregar = enc.itemAt(0).widget()
        self.sub_agregar = enc.itemAt(1).widget()
        v.addLayout(enc)
        v.addSpacing(16)

        fila = QHBoxLayout()
        fila.setAlignment(Qt.AlignTop)

        caja = QWidget()
        caja.setMaximumWidth(420)
        f = QVBoxLayout(caja)
        f.setContentsMargins(0, 0, 0, 0)

        self.in_nombre = QLineEdit()
        self.in_nombre.setPlaceholderText("Nombre completo")
        self.in_ident = QLineEdit()
        self.in_ident.setPlaceholderText("Número de identificación")
        self.in_rol = QComboBox()
        self.cargar_roles()

        for texto, w in (("Nombre", self.in_nombre),
                         ("Identificación", self.in_ident),
                         ("Rol", self.in_rol)):
            l = QLabel(texto)
            l.setObjectName("fieldLabel")
            f.addWidget(l)
            f.addWidget(w)
            f.addSpacing(8)

        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setObjectName("primary")
        self.btn_guardar.setCursor(Qt.PointingHandCursor)
        self.btn_guardar.clicked.connect(self.guardar)
        f.addWidget(self.btn_guardar)
        f.addStretch()
        fila.addWidget(caja)
        fila.addSpacing(32)

        # Panel de cámara en la misma ventana
        panel = QVBoxLayout()
        self.cam = Camara(self.al_detectar_cara)
        self.btn_rostro = QPushButton("Capturar rostro")
        self.btn_rostro.setObjectName("small")
        self.btn_rostro.setCursor(Qt.PointingHandCursor)
        self.btn_rostro.clicked.connect(self.alternar_captura)
        self.lbl_rostro = QLabel("Rostro: sin capturar (opcional)")
        self.lbl_rostro.setObjectName("subtitle")
        panel.addWidget(self.cam)
        panel.addWidget(self.btn_rostro)
        panel.addWidget(self.lbl_rostro)

        # Huella (solo visible al editar una persona ya guardada)
        panel.addSpacing(12)
        self.btn_huella = QPushButton("Agregar huella")
        self.btn_huella.setObjectName("small")
        self.btn_huella.setCursor(Qt.PointingHandCursor)
        self.btn_huella.clicked.connect(self.alternar_huella)
        self.lbl_huella = QLabel("")
        self.lbl_huella.setObjectName("subtitle")
        self.lbl_huella.setWordWrap(True)
        panel.addWidget(self.btn_huella)
        panel.addWidget(self.lbl_huella)
        self.btn_huella.hide()
        self.lbl_huella.hide()
        self.huella.mensaje.connect(self.lbl_huella.setText)
        self.huella.exito.connect(self.huella_exito)
        self.huella.fallo.connect(self.huella_fallo)
        self.huella.cancelado.connect(self.refrescar_huella)

        fila.addLayout(panel)
        fila.addStretch()

        v.addLayout(fila)
        v.addStretch()

    # ---------- API que usa gestor_local ----------
    def al_mostrar(self):
        self.cargar_roles()
        self.modo_nuevo()

    def parar(self):
        self.cancelar_captura()
        self.huella.detener()

    def editar(self, pid):
        """Abre el panel en modo edición (gestor_local ya lo mostró)."""
        nombre, ident, rol_id = self.con.execute(
            "SELECT nombre, identificacion, rol_id FROM persona WHERE id = ?", (pid,)).fetchone()
        n = self.con.execute(
            "SELECT COUNT(*) FROM biometrico WHERE persona_id = ? AND tipo = 'rostro'",
            (pid,)).fetchone()[0]
        self.editando, self.n_rostros = pid, n
        self.in_nombre.setText(nombre)
        self.in_ident.setText(ident)
        self.in_rol.setCurrentIndex(max(0, self.in_rol.findData(rol_id)))
        self.tit_agregar.setText("Editar usuario")
        self.sub_agregar.setText("Corrige los datos o vuelve a capturar el rostro.")
        self.btn_guardar.setText("Guardar cambios")
        self.btn_rostro.setText("Capturar rostro nuevo")
        self.lbl_rostro.setText(self.texto_rostro())
        self.btn_huella.show()
        self.lbl_huella.show()
        self.refrescar_huella()

    # ---------- Formulario ----------
    def cargar_roles(self):
        self.in_rol.clear()
        for rid, nombre in self.con.execute("SELECT id, nombre FROM rol ORDER BY nombre"):
            self.in_rol.addItem(nombre, rid)

    def texto_rostro(self):
        if self.editando:
            if self.n_rostros:
                return f"Rostro actual: {self.n_rostros} muestras. Captura uno nuevo para reemplazarlo."
            return "Sin rostro registrado."
        return "Rostro: sin capturar (opcional)"

    def modo_nuevo(self):
        self.editando, self.n_rostros, self.muestras = None, 0, []
        self.in_nombre.clear()
        self.in_ident.clear()
        self.in_rol.setCurrentIndex(0)
        self.tit_agregar.setText("Agregar Nuevo")
        self.sub_agregar.setText("Registra un nuevo usuario.")
        self.btn_guardar.setText("Guardar")
        self.btn_rostro.setText("Capturar rostro")
        self.lbl_rostro.setText(self.texto_rostro())
        self.btn_huella.hide()
        self.lbl_huella.hide()

    def guardar(self):
        nombre = self.in_nombre.text().strip()
        ident = self.in_ident.text().strip()
        rol_id = self.in_rol.currentData()
        if not nombre or not ident or rol_id is None:
            QMessageBox.warning(self, "Campos vacíos", "Nombre, identificación y rol son obligatorios.")
            return
        if self.cam.activa():
            QMessageBox.information(self, "Captura en curso", "Termina o cancela la captura del rostro.")
            return
        if self.huella.activo():
            QMessageBox.information(self, "Captura en curso", "Termina o cancela el registro de la huella.")
            return
        try:
            if self.editando:
                pid = self.editando
                self.con.execute(
                    "UPDATE persona SET nombre = ?, identificacion = ?, rol_id = ? WHERE id = ?",
                    (nombre, ident, rol_id, pid))
                if self.muestras:        # rostro nuevo: reemplaza el anterior
                    self.con.execute(
                        "DELETE FROM biometrico WHERE persona_id = ? AND tipo = 'rostro'", (pid,))
                    guardar_muestras(self.con, pid, self.muestras)
            else:
                cur = self.con.execute(
                    "INSERT INTO persona (nombre, identificacion, rol_id) VALUES (?,?,?)",
                    (nombre, ident, rol_id))
                if self.muestras:
                    guardar_muestras(self.con, cur.lastrowid, self.muestras)
            self.con.commit()
        except sqlite3.IntegrityError:
            self.con.rollback()
            QMessageBox.warning(self, "Duplicado", "Ya existe una persona con esa identificación.")
            return
        self.modo_nuevo()
        self.guardado.emit()

    # ---------- Captura de rostro ----------
    def alternar_captura(self):
        if self.cam.activa():
            self.cancelar_captura()
            return
        self.muestras, self.contador = [], 0
        if not self.cam.iniciar():
            QMessageBox.warning(self, "Cámara", "No se pudo abrir la cámara.")
            return
        self.btn_rostro.setText("Cancelar captura")
        self.lbl_rostro.setText(f"Mira a la cámara y mueve un poco la cabeza... 0/{MUESTRAS}")

    def cancelar_captura(self):
        self.cam.detener()
        self.btn_rostro.setText("Capturar rostro")
        if len(self.muestras) < MUESTRAS:
            self.muestras = []
            self.lbl_rostro.setText(self.texto_rostro())

    def al_detectar_cara(self, cara):
        self.contador += 1
        if self.contador % 10:            # una muestra cada ~10 frames con rostro
            return
        self.muestras.append(cara)
        self.lbl_rostro.setText(f"Capturando... {len(self.muestras)}/{MUESTRAS}")
        if len(self.muestras) >= MUESTRAS:
            self.cam.detener()
            self.btn_rostro.setText("Repetir captura")
            self.lbl_rostro.setText("✓ Rostro capturado")

    # ---------- Huella (la lógica vive en huella.py) ----------
    def refrescar_huella(self):
        tiene = self.editando is not None and tiene_huella(self.con, self.editando)
        self.btn_huella.setText("Reemplazar huella" if tiene else "Agregar huella")
        self.btn_huella.setEnabled(True)
        self.lbl_huella.setText("Huella: registrada." if tiene else "Huella: sin registrar.")

    def alternar_huella(self):
        if self.huella.activo():                          # cancelar
            self.huella.cancelar()
            self.btn_huella.setEnabled(False)
            self.lbl_huella.setText("Cancelando...")
            return
        if not self.editando:
            return
        if self.cam.activa():
            QMessageBox.information(self, "Cámara activa", "Termina la captura del rostro primero.")
            return
        self.btn_huella.setText("Cancelar huella")
        self.lbl_huella.setText("Conectando con el lector...")
        self.huella.iniciar(self.editando)

    def huella_exito(self, slot):
        self.refrescar_huella()
        self.lbl_huella.setText(f"✓ Huella registrada de forma exitosa (ID {slot}).")
        QMessageBox.information(self, "Huella", "Huella registrada de forma exitosa.")

    def huella_fallo(self, motivo):
        self.refrescar_huella()
        self.lbl_huella.setText(f"✗ No se pudo registrar la huella: {motivo}")
        QMessageBox.warning(self, "Huella", f"No se pudo registrar la huella.\n\n{motivo}")