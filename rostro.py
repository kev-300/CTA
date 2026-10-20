"""Lógica de rostro compartida por gestor_local.py y registrar.py.
Requiere: pip install opencv-contrib-python numpy"""
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel

TAM = 100       # tamaño de la cara normalizada (px)
UMBRAL = 70     # LBPH: menor = más parecido. Sube si no te reconoce, baja si confunde personas

_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def detectar(frame):
    """Devuelve ((x, y, w, h), cara_normalizada) del rostro más grande, o (None, None)."""
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    caras = _cascade.detectMultiScale(gris, 1.2, 5, minSize=(80, 80))
    if len(caras) == 0:
        return None, None
    x, y, w, h = max(caras, key=lambda c: c[2] * c[3])
    cara = cv2.resize(gris[y:y + h, x:x + w], (TAM, TAM))
    return (x, y, w, h), cv2.equalizeHist(cara)


def guardar_muestras(con, persona_id, muestras):
    """Guarda cada muestra como PNG en biometrico.plantilla (no hace commit)."""
    for img in muestras:
        ok, buf = cv2.imencode(".png", img)
        con.execute(
            "INSERT INTO biometrico (persona_id, tipo, plantilla) VALUES (?,?,?)",
            (persona_id, "rostro", buf.tobytes()))


def cargar_reconocedor(con):
    """Entrena LBPH con los rostros de personas activas. None si no hay ninguno."""
    filas = con.execute(
        """SELECT b.persona_id, b.plantilla FROM biometrico b
           JOIN persona p ON p.id = b.persona_id
           WHERE b.tipo = 'rostro' AND p.activo = 1""").fetchall()
    if not filas:
        return None
    imgs = [cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_GRAYSCALE)
            for _, b in filas]
    ids = np.array([p for p, _ in filas], dtype=np.int32)
    rec = cv2.face.LBPHFaceRecognizer_create()
    rec.train(imgs, ids)
    return rec


class Camara(QLabel):
    """Panel de cámara dentro de la misma ventana.
    Llama a on_cara(cara_normalizada) en cada frame donde detecta un rostro."""

    def __init__(self, on_cara, parent=None):
        super().__init__(parent)
        self.on_cara = on_cara
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.setFixedSize(480, 360)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #000; border-radius: 8px; color: #6b7280;")
        self.setText("Cámara apagada")

    def activa(self):
        return self.timer.isActive()

    def iniciar(self):
        if self.cap is None:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)      # DSHOW: arranque rápido en Windows
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                cap.release()
                return False
            self.cap = cap
        self.timer.start(30)
        return True

    def detener(self):
        self.timer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.clear()
        self.setText("Cámara apagada")

    def _tick(self):
        ok, frame = self.cap.read()
        if not ok:
            return
        frame = cv2.flip(frame, 1)                         # efecto espejo
        caja, cara = detectar(frame)
        if caja is not None:
            x, y, w, h = caja
            cv2.rectangle(frame, (x, y), (x + w, y + h), (153, 211, 52), 2)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        alto, ancho = rgb.shape[:2]
        img = QImage(rgb.data, ancho, alto, 3 * ancho, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(img).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if cara is not None:
            self.on_cara(cara)     # debe ser lo último: puede detener la cámara
