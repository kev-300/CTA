"""Panel 'Lista del Día': asistencia de todas las personas en la fecha elegida."""
from datetime import date, datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
)
from panel_base import PanelBase
from registrar import FIN
from cerrar_dia import DIAS_LABORALES

# estado -> (texto visible, fondo pastel, color de letra oscuro)
ESTILOS = {
    "PRESENTE":         ("En horario",       "#d1fae5", "#065f46"),   # verde
    "FUERA_DE_HORARIO": ("Fuera de horario", "#fef3c7", "#92400e"),   # amarillo
    "AUSENTE":          ("Ausente",          "#fee2e2", "#991b1b"),   # rojo
    "PENDIENTE":        ("Pendiente",        "#f3f4f6", "#4b5563"),   # gris
    "SIN_JORNADA":      ("Sin jornada",      "#f3f4f6", "#4b5563"),   # gris
}


class PanelListaDia(PanelBase):
    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)

        # --- Fila superior: título + buscador de fecha ---
        top = QHBoxLayout()
        top.addLayout(self.encabezado(
            "Lista del Día", "Asistencia de todas las personas en la fecha elegida."))
        top.addStretch()
        self.sp_dia = self._spin(1, 31, 60)
        self.sp_mes = self._spin(1, 12, 60)
        self.sp_anio = self._spin(2020, 2100, 85)
        for texto, sp in (("Día", self.sp_dia), ("Mes", self.sp_mes), ("Año", self.sp_anio)):
            et = QLabel(texto)
            et.setObjectName("fieldLabel")
            top.addWidget(et)
            top.addWidget(sp)
            top.addSpacing(8)
        buscar = QPushButton("Buscar")
        buscar.setObjectName("primary")
        buscar.setCursor(Qt.PointingHandCursor)
        buscar.clicked.connect(self.cargar)
        hoy = QPushButton("Hoy")
        hoy.setObjectName("small")
        hoy.setCursor(Qt.PointingHandCursor)
        hoy.clicked.connect(self.ir_a_hoy)
        top.addWidget(buscar)
        top.addWidget(hoy)
        v.addLayout(top)

        self.resumen = QLabel("")
        self.resumen.setObjectName("subtitle")
        v.addWidget(self.resumen)

        # --- Tabla ---
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["ID", "NOMBRE", "ROL", "ESTADO", "HORA"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setShowGrid(False)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        h = self.tabla.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        v.addWidget(self.tabla, 1)

    @staticmethod
    def _spin(minimo, maximo, ancho):
        sp = QSpinBox()
        sp.setRange(minimo, maximo)
        sp.setFixedWidth(ancho)
        return sp

    # ---------- API que usa gestor_local ----------
    def al_mostrar(self):
        self.ir_a_hoy()

    def ir_a_hoy(self, *_):
        hoy = date.today()
        self.sp_dia.setValue(hoy.day)
        self.sp_mes.setValue(hoy.month)
        self.sp_anio.setValue(hoy.year)
        self.cargar()

    # ---------- Lógica ----------
    def estado_sin_registro(self, fecha):
        """Estado de quien no tiene fila ese día."""
        if fecha.weekday() not in DIAS_LABORALES:
            return "SIN_JORNADA"
        hoy = date.today()
        if fecha > hoy or (fecha == hoy and datetime.now().time() <= FIN):
            return "PENDIENTE"          # el día aún no termina de contar
        return "AUSENTE"

    def cargar(self, *_):
        try:
            fecha = date(self.sp_anio.value(), self.sp_mes.value(), self.sp_dia.value())
        except ValueError:
            QMessageBox.warning(self, "Fecha inválida", "Ese día no existe en el mes elegido.")
            return
        filas = self.con.execute(
            """SELECT p.id, p.nombre, r.nombre, a.estado, a.hora
               FROM persona p
               JOIN rol r ON r.id = p.rol_id
               LEFT JOIN asistencia a ON a.persona_id = p.id AND a.fecha = ?
               WHERE p.activo = 1 OR a.id IS NOT NULL
               ORDER BY p.nombre""", (fecha.isoformat(),)).fetchall()

        sin_registro = self.estado_sin_registro(fecha)
        cuenta = {}
        self.tabla.setRowCount(len(filas))
        for r, (pid, nombre, rol, estado, hora) in enumerate(filas):
            estado = estado or sin_registro
            texto, fondo, tinta = ESTILOS[estado]
            cuenta[estado] = cuenta.get(estado, 0) + 1
            for c, val in enumerate((pid, nombre, rol, texto, hora or "—")):
                it = QTableWidgetItem(str(val))
                it.setBackground(QColor(fondo))
                it.setForeground(QColor(tinta))
                if c == 3:                      # el estado va en negrita
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.tabla.setItem(r, c, it)
            self.tabla.setRowHeight(r, 40)

        self.resumen.setText(
            f"{fecha.strftime('%d/%m/%Y')}   ·   "
            f"En horario: {cuenta.get('PRESENTE', 0)}   ·   "
            f"Fuera de horario: {cuenta.get('FUERA_DE_HORARIO', 0)}   ·   "
            f"Ausentes: {cuenta.get('AUSENTE', 0)}   ·   Total: {len(filas)}")