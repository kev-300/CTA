"""Panel 'Exportar Datos' (vacío por ahora)."""
from panel_base import PanelBase


class PanelExportar(PanelBase):
    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con