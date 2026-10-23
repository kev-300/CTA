"""Base común de los paneles. gestor_local solo usa al_mostrar() y parar()."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PanelBase(QWidget):
    def al_mostrar(self):
        """Se llama cada vez que se entra al panel."""

    def parar(self):
        """Se llama al salir del panel o cerrar la app (apagar cámaras, etc.)."""

    @staticmethod
    def encabezado(titulo, sub):
        v = QVBoxLayout()
        t = QLabel(titulo)
        t.setObjectName("title")
        s = QLabel(sub)
        s.setObjectName("subtitle")
        v.addWidget(t)
        v.addWidget(s)
        return v