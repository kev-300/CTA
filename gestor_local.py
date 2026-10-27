import os
import sys
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QButtonGroup, QFrame,
)
from panel_registros import PanelRegistros
from panel_agregar import PanelAgregar
from panel_exportar import PanelExportar
from asistencia_panel import PanelAsistencia
from datos_dia import PanelListaDia

import time
T0 = time.perf_counter()

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registros.db")  # Conexión con la base de datos (registros.db)

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
"""  # Estilos y visuales del aplicativo

# Orden del menú lateral = orden de las páginas en el stack (mismo índice)
MENU = ("Registros", "Agregar Nuevo", "Exportar Datos", "Registrar Asistencia", "Lista del Día")


def conectar():  # conexión con la base de datos
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con


class Ventana(QMainWindow):  # ventana principal: solo navegación
    def __init__(self):
        super().__init__()
        self.con = conectar()
        self.setWindowTitle("GestorLocal v1.0.0")
        self.resize(1200, 700)

        for nombre in ("Archivo", "Editar", "Ayuda"):  # barra de menús
            self.menuBar().addMenu(nombre)

        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._crear_sidebar())

        # Paneles: el orden de esta tupla debe coincidir con MENU
        self.registros = PanelRegistros(self.con)
        self.agregar = PanelAgregar(self.con)
        self.exportar = PanelExportar(self.con)
        self.asistencia = PanelAsistencia(self.con)
        self.datos_dia = PanelListaDia(self.con)
        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        for panel in (self.registros, self.agregar, self.exportar, self.asistencia, self.datos_dia):
            self.stack.addWidget(panel)
        lay.addWidget(self.stack, 1)

        # Comunicación entre paneles
        self.registros.nuevo.connect(lambda: self.ir_a(1))
        self.registros.editar.connect(self.editar_persona)
        self.agregar.guardado.connect(lambda: self.ir_a(0))

        self.registros.al_mostrar()

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
        for i, texto in enumerate(MENU):
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

    # ---------- Navegación ----------
    def stack_set(self, i):
        if i >= self.stack.count():      # opción del menú sin panel todavía
            return
        self.stack.setCurrentIndex(i)
        for j in range(self.stack.count()):
            if j != i:
                self.stack.widget(j).parar()
        self.stack.widget(i).al_mostrar()

    def ir_a(self, i):
        self.grupo.button(i).setChecked(True)
        self.stack_set(i)

    def editar_persona(self, pid):
        self.ir_a(1)                     # entra en modo nuevo...
        self.agregar.editar(pid)         # ...y lo convierte en edición

    def closeEvent(self, e):
        for i in range(self.stack.count()):
            self.stack.widget(i).parar()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = Ventana()
    w.show()
    print(f"Arranque: {(time.perf_counter() - T0)*1000:.0f} ms")
    sys.exit(app.exec())