"""Panel 'Registros': tabla de personas con búsqueda, editar y activar/desactivar."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from panel_base import PanelBase


class PanelRegistros(PanelBase):
    nuevo = Signal()        # se pulsó "+ Nuevo"
    editar = Signal(int)    # se pulsó "Editar" (persona_id)

    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)

        top = QHBoxLayout()
        top.addLayout(self.encabezado(
            "Gestión de Registros",
            "Visualiza, edita o elimina elementos almacenados localmente."))
        top.addStretch()
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar registro...")
        self.buscar.setFixedWidth(250)
        self.buscar.textChanged.connect(self.cargar)
        top.addWidget(self.buscar)
        nuevo = QPushButton("+  Nuevo")
        nuevo.setObjectName("primary")
        nuevo.setCursor(Qt.PointingHandCursor)
        nuevo.clicked.connect(self.nuevo.emit)
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

    def al_mostrar(self):
        self.cargar()

    def cargar(self, *_):
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
            cont = QWidget()
            h = QHBoxLayout(cont)
            h.setContentsMargins(4, 0, 4, 0)
            h.setSpacing(6)
            b_edit = QPushButton("Editar")
            b_edit.setObjectName("small")
            b_edit.setCursor(Qt.PointingHandCursor)
            b_edit.clicked.connect(lambda _=False, i=pid: self.editar.emit(i))
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
        self.cargar()