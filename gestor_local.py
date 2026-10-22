import os
import sys
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QStackedWidget, QButtonGroup, QMessageBox, QAbstractItemView,
    QFrame,
)
from rostro import Camara, guardar_muestras   # Importar la camara del dispositivo para rostro
from asistencia_panel import PanelAsistencia   # ASISTENCIA

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registros.db") # Conexion con la base de datos (registros.db)
MUESTRAS = 8   # ROSTRO: fotos del rostro que se guardan por persona

QSS = """
* { font-family: 'Segoe UI'; font-size: 13px; color: #000; }
QMainWindow, #content { background: #fff; }
QMenuBar { background: #fff; color: #000; }
QMenuBar::item:selected { background: #e5e7eb; }
QMenu { background: #fff; border: 1px solid #d1d5db; }
QMenu::item:selected { background: #d1d5db; color: #000; }
#sidebar { background: #fff; border-right: 1px solid #d1d5db; }
#sectionLabel { color: #000; font-size: 11px; font-weight: bold; }
#nav { background: transparent; border: none; text-align: left;
       padding: 10px 12px; border-radius: 8px; color: #000; }
#nav:hover { background: #f3f4f6; }
#nav:checked { background: #d1d5db; color: #000; font-weight: bold; }
#dbStatus { background: #fff; border: 1px solid #d1d5db; border-radius: 8px; }
#dbOk { color: #000; font-weight: bold; }
#title { font-size: 20px; font-weight: bold; color: #000; }
#subtitle { color: #000; font-size: 12px; }
QLineEdit, QComboBox { background: #fff; border: 1px solid #9ca3af;
                       border-radius: 8px; padding: 9px 12px; color: #000; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #4b5563; }
QComboBox QAbstractItemView { background: #fff; color: #000;
                              selection-background-color: #d1d5db; selection-color: #000; }
#primary { background: #d1d5db; color: #000; border: 1px solid #9ca3af;
           border-radius: 8px; padding: 9px 18px; font-weight: bold; }
#primary:hover { background: #9ca3af; }
#small { background: #e5e7eb; color: #000; border: 1px solid #d1d5db;
         border-radius: 6px; padding: 7px 12px; }
#small:hover { background: #d1d5db; }
QTableWidget { background: #fff; border: 1px solid #d1d5db; border-radius: 10px;
               gridline-color: transparent; outline: 0; }
QTableWidget::item { padding: 6px; border-bottom: 1px solid #e5e7eb; color: #000; }
QTableWidget::item:selected { background: #e5e7eb; color: #000; }
QHeaderView::section { background: #fff; color: #000; border: none;
                       border-bottom: 1px solid #9ca3af;
                       padding: 12px 8px; font-weight: bold; text-align: left; }
#fieldLabel { color: #000; }
""" # Estilos y visuales del aplicativo


def conectar(): #coneccion con la base de datos
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con


class Ventana(QMainWindow): #clase de la ventana pricipal
    def __init__(self):
        super().__init__()
        self.con = conectar()
        self.setWindowTitle("GestorLocal v1.0.0") #nombre de la ventana
        self.resize(1200, 700)

        for nombre in ("Archivo", "Editar", "Ayuda"):#barra de menus con archivo, editar y ayuda
            self.menuBar().addMenu(nombre)

        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._crear_sidebar())

        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        self.stack.addWidget(self._pagina_registros())
        self.stack.addWidget(self._pagina_agregar())
        self.stack.addWidget(self._pagina_exportar())
        self.panel_asist = PanelAsistencia(self.con)      # ASISTENCIA
        self.stack.addWidget(self.panel_asist)
        lay.addWidget(self.stack, 1)

        self.cargar_registros()

    # ---------- Sidebar ----------
    def _crear_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(215)
        v = QVBoxLayout(side)
        v.setContentsMargins(10, 16, 10, 10)

        lbl = QLabel("MÓDULOS")
        lbl.setObjectName("sectionLabel")
        v.addWidget(lbl)

        self.grupo = QButtonGroup(self)
        for i, texto in enumerate(("Registros", "Agregar Nuevo", "Exportar Datos", "Registrar Asistencia")):
            b = QPushButton(texto)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.grupo.addButton(b, i)
            v.addWidget(b)
        self.grupo.button(0).setChecked(True)
        self.grupo.idClicked.connect(self.stack_set)

        v.addStretch()

        estado = QFrame()
        estado.setObjectName("dbStatus")
        ev = QVBoxLayout(estado)
        ok = QLabel("● BD Local Activa")
        ok.setObjectName("dbOk")
        ev.addWidget(ok)
        ev.addWidget(QLabel(f"SQLite ({os.path.basename(DB)})"))
        v.addWidget(estado)
        return side

    def stack_set(self, i):
        self.stack.setCurrentIndex(i)
        if i != 1:
            self.cancelar_captura()           # ROSTRO: apaga la cámara al salir
        if i != 3:
            self.panel_asist.parar()          # ASISTENCIA
        if i == 0:
            self.cargar_registros()
        elif i == 1:
            self.cargar_roles()
            self.modo_nuevo()                 # EDITAR
        elif i == 3:
            self.panel_asist.al_mostrar()     # ASISTENCIA

    def ir_a(self, i):
        self.grupo.button(i).setChecked(True)
        self.stack_set(i)

    # ---------- Página: Registros ----------
    def _encabezado(self, titulo, sub):
        v = QVBoxLayout()
        t = QLabel(titulo)
        t.setObjectName("title")
        s = QLabel(sub)
        s.setObjectName("subtitle")
        v.addWidget(t)
        v.addWidget(s)
        return v

    def _pagina_registros(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(24, 24, 24, 24)

        top = QHBoxLayout()
        top.addLayout(self._encabezado(
            "Gestión de Registros",
            "Visualiza, edita o elimina elementos almacenados localmente."))
        top.addStretch()
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar registro...")
        self.buscar.setFixedWidth(250)
        self.buscar.textChanged.connect(self.cargar_registros)
        top.addWidget(self.buscar)
        nuevo = QPushButton("+  Nuevo")
        nuevo.setObjectName("primary")
        nuevo.setCursor(Qt.PointingHandCursor)
        nuevo.clicked.connect(lambda: self.ir_a(1))
        top.addWidget(nuevo)
        v.addLayout(top)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["ID", "NOMBRE", "IDENTIFICACIÓN", "ROL", "ESTADO", "ACCIONES"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        h = self.tabla.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        v.addWidget(self.tabla, 1)
        return p

    def cargar_registros(self):
        q = f"%{self.buscar.text().strip()}%"
        filas = self.con.execute(
            """SELECT p.id, p.nombre, p.identificacion, r.nombre, p.activo
               FROM persona p JOIN rol r ON r.id = p.rol_id
               WHERE p.nombre LIKE ? OR p.identificacion LIKE ? OR r.nombre LIKE ?
               ORDER BY p.id DESC""", (q, q, q)).fetchall()
        self.tabla.setRowCount(len(filas))
        for r, (pid, nombre, ident, rol, activo) in enumerate(filas):
            for c, val in enumerate((pid, nombre, ident, rol,
                                     "Activo" if activo else "Inactivo")):
                self.tabla.setItem(r, c, QTableWidgetItem(str(val)))
            cont = QWidget()                                   # EDITAR
            h = QHBoxLayout(cont)
            h.setContentsMargins(4, 0, 4, 0)
            h.setSpacing(6)
            b_edit = QPushButton("Editar")
            b_edit.setObjectName("small")
            b_edit.setCursor(Qt.PointingHandCursor)
            b_edit.clicked.connect(lambda _=False, i=pid: self.abrir_edicion(i))
            btn = QPushButton("Desactivar" if activo else "Activar")
            btn.setObjectName("small")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=pid: self.cambiar_estado(i))
            h.addWidget(b_edit)
            h.addWidget(btn)
            self.tabla.setCellWidget(r, 5, cont)
            self.tabla.setRowHeight(r, 44)

    def cambiar_estado(self, pid):
        self.con.execute("UPDATE persona SET activo = 1 - activo WHERE id = ?", (pid,))
        self.con.commit()
        self.cargar_registros()

    # ---------- Página: Agregar ----------
    def _pagina_agregar(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(24, 24, 24, 24)
        self.editando, self.n_rostros = None, 0               # EDITAR
        enc = self._encabezado("Agregar Nuevo", "Registra un nuevo usuario.")
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

        # ROSTRO: panel de cámara en la misma ventana
        self.muestras, self.contador = [], 0
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
        fila.addLayout(panel)
        fila.addStretch()

        v.addLayout(fila)
        v.addStretch()
        return p

    def cargar_roles(self):
        self.in_rol.clear()
        for rid, nombre in self.con.execute("SELECT id, nombre FROM rol ORDER BY nombre"):
            self.in_rol.addItem(nombre, rid)

    # ---------- EDITAR ----------
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

    def abrir_edicion(self, pid):
        nombre, ident, rol_id = self.con.execute(
            "SELECT nombre, identificacion, rol_id FROM persona WHERE id = ?", (pid,)).fetchone()
        n = self.con.execute(
            "SELECT COUNT(*) FROM biometrico WHERE persona_id = ? AND tipo = 'rostro'",
            (pid,)).fetchone()[0]
        self.ir_a(1)                         # entra en modo nuevo...
        self.editando, self.n_rostros = pid, n   # ...y lo convierte en edición
        self.in_nombre.setText(nombre)
        self.in_ident.setText(ident)
        self.in_rol.setCurrentIndex(max(0, self.in_rol.findData(rol_id)))
        self.tit_agregar.setText("Editar usuario")
        self.sub_agregar.setText("Corrige los datos o vuelve a capturar el rostro.")
        self.btn_guardar.setText("Guardar cambios")
        self.btn_rostro.setText("Capturar rostro nuevo")
        self.lbl_rostro.setText(self.texto_rostro())

    # ---------- ROSTRO: captura ----------
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
        self.panel_asist.parar()   # ASISTENCIA
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
        try:
            if self.editando:                                     # EDITAR
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
                if self.muestras:                                 # ROSTRO
                    guardar_muestras(self.con, cur.lastrowid, self.muestras)
            self.con.commit()
        except sqlite3.IntegrityError:
            self.con.rollback()
            QMessageBox.warning(self, "Duplicado", "Ya existe una persona con esa identificación.")
            return
        self.modo_nuevo()
        self.ir_a(0)

    # ---------- Página: Exportar (vacía por ahora) ----------
    def _pagina_exportar(self):
        return QWidget()

    def closeEvent(self, e):
        self.cam.detener()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = Ventana()
    w.show()
    sys.exit(app.exec())