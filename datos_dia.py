"""Panel 'Exportar Datos' (vacío por ahora)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from panel_base import PanelBase

class PanelDatosDia(PanelBase):
    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)


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

    def cambiar_estado(self, pid):
        self.con.execute("UPDATE persona SET activo = 1 - activo WHERE id = ?", (pid,))
        self.con.commit()
        self.cargar()

