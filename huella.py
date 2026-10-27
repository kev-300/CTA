"""Toda la lógica de huella dactilar (AS608 vía ESP32).

Capas de este archivo:
  1. Serial          : abrir_lector() y los hilos privados _HiloEnrolar / _HiloEscuchar
  2. Base de datos   : slot_de, slot_libre, tiene_huella, guardar_huella, persona_por_slot
  3. Controladores   : RegistroHuella (enrolar) y LectorAsistencia (reconocer)

Los paneles solo crean botones y llaman a los controladores.
Requiere:  pip install pyserial
"""
import socket
import time
import serial
from serial.tools import list_ports
from PySide6.QtCore import QObject, QThread, Signal

BAUD = 115200
PUERTO = None          # fija un puerto (p. ej. "COM5") o déjalo en None para autodetectar
ESPERA_HOLA = 4.0      # s esperando el PONG de cada puerto
TIEMPO_MAX = 90.0      # s máximos para enrolar
MAX_SLOT = 127         # IDs 1..127 (deben coincidir con el firmware)

# --- WiFi por router (se intenta primero; si falla, se usa el cable USB) ---
USAR_WIFI = True
HOST_WIFI = None                   # None = descubrir la ESP32 automáticamente; o fija la IP, p. ej. "192.168.1.50"
PUERTO_WIFI = 8080                 # = PUERTO_TCP en config.h
PUERTO_DESCUBRIMIENTO = 8081       # = PUERTO_DESCUBRIMIENTO en config.h
CLAVE_WIFI = "12345678"            # = TOKEN_LECTOR en config.h


# =====================================================================
# 1. SERIAL
# =====================================================================
_ultimo_puerto = None   # puerto USB que funcionó la última vez: se prueba primero
_ultima_ip = None       # IP de la ESP32 que funcionó la última vez


class _ConexionTCP:
    """Imita la parte de serial.Serial que usa este módulo, pero sobre WiFi."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def write(self, datos):
        try:
            self.sock.sendall(datos)
        except OSError as e:
            raise serial.SerialException(str(e))

    def readline(self):
        fin = time.time() + 0.3
        while b"\n" not in self.buf:
            restante = fin - time.time()
            if restante <= 0:
                return b""
            self.sock.settimeout(restante)
            try:
                datos = self.sock.recv(1024)
            except socket.timeout:
                return b""
            except OSError as e:
                raise serial.SerialException(str(e))
            if not datos:
                raise serial.SerialException("la ESP32 cerró la conexión")
            self.buf += datos
        linea, self.buf = self.buf.split(b"\n", 1)
        return linea + b"\n"

    def reset_input_buffer(self):
        self.buf = b""
        self.sock.settimeout(0.05)
        try:
            while self.sock.recv(1024):
                pass
        except OSError:
            pass

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _abrir(nombre):
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = nombre, BAUD, 0.3
    s.dtr = False      # evita reiniciar la ESP32 al abrir el puerto
    s.rts = False
    s.open()
    return s


def _linea(s):
    return s.readline().decode("utf-8", errors="replace").strip()


def _saludar(s):
    """Envía PING hasta recibir respuesta. Devuelve 'ok', 'sin_sensor' o None."""
    fin = time.time() + ESPERA_HOLA
    while time.time() < fin:
        s.write(b"PING\n")
        resp = _linea(s)
        if resp == "PONG":
            return "ok"
        if resp == "PONG:SIN_SENSOR":
            return "sin_sensor"
    return None


def _descubrir(espera=3.0):
    """Busca la ESP32 en la red local (broadcast UDP). Devuelve su IP o None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.5)
        fin = time.time() + espera
        while time.time() < fin:
            s.sendto(b"HUELLA?", ("255.255.255.255", PUERTO_DESCUBRIMIENTO))
            try:
                datos, (ip, _) = s.recvfrom(64)
            except socket.timeout:
                continue
            if datos.startswith(b"HUELLA!"):
                return ip
    except OSError:
        pass
    finally:
        s.close()
    return None


def _abrir_wifi(host):
    """Devuelve (conexion, None) o (None, motivo)."""
    try:
        sock = socket.create_connection((host, PUERTO_WIFI), timeout=3)
    except OSError:
        return None, f"no se alcanza {host}:{PUERTO_WIFI}"
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    con = _ConexionTCP(sock)
    try:
        con.write(f"AUTH:{CLAVE_WIFI}\n".encode())
        fin = time.time() + 3
        while time.time() < fin:
            r = _linea(con)
            if r == "OK:AUTH":
                return con, None
            if r.startswith("ERR:AUTH"):
                con.close()
                return None, "la ESP32 rechazó la clave"
    except serial.SerialException as e:
        con.close()
        return None, str(e)
    con.close()
    return None, "la ESP32 no respondió"


def _conectar_wifi():
    """Prueba la IP fija, la última conocida y, si hace falta, el descubrimiento.
    Devuelve (conexion, None) o (None, motivo)."""
    global _ultima_ip
    candidatas = [HOST_WIFI] if HOST_WIFI else ([_ultima_ip] if _ultima_ip else [])
    motivo = "no se encontró la ESP32 en la red"
    for host in candidatas:
        con, motivo = _abrir_wifi(host)
        if con:
            _ultima_ip = host
            return con, None
    if not HOST_WIFI:
        ip = _descubrir()
        if ip and ip not in candidatas:
            con, motivo = _abrir_wifi(ip)
            if con:
                _ultima_ip = ip
                return con, None
    return None, motivo


def _puertos():
    if PUERTO:
        return [PUERTO]
    todos = list_ports.comports()
    usb = [p.device for p in todos if p.vid is not None]      # chips USB-serie reales
    lista = usb or [p.device for p in todos]                   # Bluetooth etc. solo si no hay USB
    if _ultimo_puerto in lista:
        lista.remove(_ultimo_puerto)
        lista.insert(0, _ultimo_puerto)
    return lista


def abrir_lector():
    """Abre la conexión con la ESP32: primero WiFi, luego USB.
    Devuelve (conexion, None) o (None, motivo_del_error)."""
    global _ultimo_puerto
    sin_sensor, motivo_wifi = False, None

    if USAR_WIFI:
        con, motivo_wifi = _conectar_wifi()
        if con:
            try:
                r = _saludar(con)
            except serial.SerialException:
                r = None
            if r == "ok":
                return con, None
            sin_sensor = sin_sensor or r == "sin_sensor"
            con.close()

    for nombre in _puertos():
        try:
            s = _abrir(nombre)
        except serial.SerialException:
            continue                      # ocupado (¿monitor de PlatformIO abierto?) o inválido
        r = _saludar(s)
        if r == "ok":
            _ultimo_puerto = nombre
            return s, None
        sin_sensor = sin_sensor or r == "sin_sensor"
        s.close()

    if sin_sensor:
        return None, "La ESP32 responde pero el lector AS608 no. Revisa el cableado."
    if USAR_WIFI:
        return None, (f"No se pudo conectar por WiFi ({motivo_wifi}) ni por USB. "
                      "Verifica que el PC y la ESP32 estén en la misma red del router.")
    return None, "No se encontró la ESP32. Cierra el monitor serie de PlatformIO e inténtalo de nuevo."


class _HiloEnrolar(QThread):
    mensaje = Signal(str)
    terminado = Signal(bool, str)     # (éxito, detalle)

    def __init__(self, slot, parent=None):
        super().__init__(parent)
        self.slot = slot
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        ser, error = abrir_lector()
        if ser is None:
            self.terminado.emit(False, error)
            return
        try:
            ser.reset_input_buffer()
            ser.write(f"ENROLL:{self.slot}\n".encode())
            cancel_enviado = False
            fin = time.time() + TIEMPO_MAX
            while time.time() < fin:
                if self._cancelar and not cancel_enviado:
                    ser.write(b"CANCEL\n")
                    cancel_enviado = True
                l = _linea(ser)
                if l.startswith("MSG:"):
                    self.mensaje.emit(l[4:])
                elif l.startswith("OK:ENROLL:"):
                    self.terminado.emit(True, l.split(":")[2])
                    return
                elif l.startswith("ERR:ENROLL:"):
                    self.terminado.emit(False, l[len("ERR:ENROLL:"):])
                    return
            self.terminado.emit(False, "tiempo agotado")
        except serial.SerialException as e:
            self.terminado.emit(False, f"error de comunicación ({e})")
        finally:
            ser.close()


class _HiloEscuchar(QThread):
    mensaje = Signal(str)
    coincidencia = Signal(int, int)    # (id del slot, confianza)
    no_reconocida = Signal()
    terminado = Signal(bool, str)      # (éxito, detalle)
    ESPERA_LISTO = 4.0                 # s para que el firmware confirme el modo asistencia

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        ser, error = abrir_lector()
        if ser is None:
            self.terminado.emit(False, error)
            return
        try:
            ser.reset_input_buffer()
            ser.write(b"MATCH\n")
            t_inicio, listo, t_cancel = time.time(), False, None
            while True:
                if self._cancelar and t_cancel is None:
                    ser.write(b"CANCEL\n")
                    t_cancel = time.time()
                if t_cancel and time.time() - t_cancel > 3:
                    break
                if not listo and t_cancel is None and time.time() - t_inicio > self.ESPERA_LISTO:
                    self.terminado.emit(False, "El lector no respondió al modo asistencia. "
                                               "Sube de nuevo el firmware a la ESP32.")
                    return
                l = _linea(ser)
                if l.startswith("MSG:"):
                    listo = True
                    self.mensaje.emit(l[4:])
                elif l.startswith("MATCH:"):
                    listo = True
                    _, slot, conf = l.split(":")
                    self.coincidencia.emit(int(slot), int(conf))
                elif l == "NOMATCH":
                    listo = True
                    self.no_reconocida.emit()
                elif l == "OK:MATCH:FIN":
                    break
            self.terminado.emit(True, "")
        except serial.SerialException as e:
            self.terminado.emit(False, f"error de comunicación ({e})")
        finally:
            ser.close()


# =====================================================================
# 2. BASE DE DATOS
# En 'biometrico' (tipo='huella') la plantilla guarda el ID del slot del
# sensor como texto en bytes (p. ej. b"5"). La plantilla real vive en el AS608.
# =====================================================================
def slot_de(con, pid):
    """Slot del sensor asignado a la persona, o None."""
    fila = con.execute(
        "SELECT plantilla FROM biometrico WHERE persona_id = ? AND tipo = 'huella'",
        (pid,)).fetchone()
    return int(bytes(fila[0]).decode()) if fila else None


def tiene_huella(con, pid):
    return slot_de(con, pid) is not None


def slot_libre(con):
    """Primer slot sin usar (1..MAX_SLOT), o None si el lector está lleno."""
    usados = {int(bytes(r[0]).decode()) for r in con.execute(
        "SELECT plantilla FROM biometrico WHERE tipo = 'huella'")}
    return next((i for i in range(1, MAX_SLOT + 1) if i not in usados), None)


def guardar_huella(con, pid, slot):
    """Asocia el slot a la persona (reemplaza la huella anterior si la había)."""
    con.execute("DELETE FROM biometrico WHERE persona_id = ? AND tipo = 'huella'", (pid,))
    con.execute("INSERT INTO biometrico (persona_id, tipo, plantilla) VALUES (?, 'huella', ?)",
                (pid, str(slot).encode()))
    con.commit()


def persona_por_slot(con, slot):
    """(persona_id, nombre, rol) de la persona ACTIVA dueña del slot, o None."""
    return con.execute(
        """SELECT p.id, p.nombre, r.nombre FROM biometrico b
           JOIN persona p ON p.id = b.persona_id
           JOIN rol r ON r.id = p.rol_id
           WHERE b.tipo = 'huella' AND b.plantilla = ? AND p.activo = 1""",
        (str(slot).encode(),)).fetchone()


# =====================================================================
# 3. CONTROLADORES (lo único que usan los paneles)
# =====================================================================
class RegistroHuella(QObject):
    """Enrola la huella de una persona y la guarda en la BD.

    Uso:  self.huella = RegistroHuella(con, self)
          conectar señales; self.huella.iniciar(persona_id)
    """
    mensaje = Signal(str)      # progreso: "Coloca el dedo...", etc.
    exito = Signal(int)        # huella guardada (slot)
    fallo = Signal(str)        # motivo
    cancelado = Signal()       # el usuario canceló

    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self._hilo, self._pid, self._slot = None, None, None

    def activo(self):
        return bool(self._hilo and self._hilo.isRunning())

    def iniciar(self, pid):
        if self.activo():
            return
        slot = slot_de(self.con, pid) or slot_libre(self.con)   # reutiliza el slot si ya tenía
        if slot is None:
            self.fallo.emit("No quedan espacios libres en el lector.")
            return
        self._pid, self._slot = pid, slot
        self._hilo = _HiloEnrolar(slot, self)
        self._hilo.mensaje.connect(self.mensaje)
        self._hilo.terminado.connect(self._fin)
        self._hilo.start()

    def cancelar(self):
        if self.activo():
            self._hilo.cancelar()

    def detener(self):
        """Cancela y espera a que se libere el puerto (al cambiar de panel o cerrar)."""
        if self.activo():
            self._hilo.cancelar()
            self._hilo.blockSignals(True)
            self._hilo.wait(4000)

    def _fin(self, ok, detalle):
        if ok:
            guardar_huella(self.con, self._pid, self._slot)
            self.exito.emit(self._slot)
        elif detalle == "cancelado":
            self.cancelado.emit()
        else:
            self.fallo.emit(detalle)


class LectorAsistencia(QObject):
    """Escucha el lector de forma continua e identifica a la persona.

    Uso:  self.lector = LectorAsistencia(con, self)
          conectar señales; self.lector.iniciar() / self.lector.detener()
    """
    mensaje = Signal(str)
    persona = Signal(int, str, str)     # persona_id, nombre, rol
    desconocida = Signal(int)           # el sensor la reconoce, pero no hay usuario activo
    no_reconocida = Signal()            # el sensor no la reconoce
    terminado = Signal(bool, str)       # (éxito, detalle) cuando el lector se detiene

    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self._hilo = None

    def activo(self):
        return bool(self._hilo and self._hilo.isRunning())

    def iniciar(self):
        if self.activo():
            return
        self._hilo = _HiloEscuchar(self)
        self._hilo.mensaje.connect(self.mensaje)
        self._hilo.no_reconocida.connect(self.no_reconocida)
        self._hilo.coincidencia.connect(self._coincidencia)
        self._hilo.terminado.connect(self.terminado)
        self._hilo.start()

    def detener(self):
        if self.activo():
            self._hilo.cancelar()
            self._hilo.blockSignals(True)   # evita mensajes tardíos tras detenerlo
            self._hilo.wait(4000)

    def _coincidencia(self, slot, confianza):
        fila = persona_por_slot(self.con, slot)
        if fila:
            self.persona.emit(*fila)
        else:
            self.desconocida.emit(slot)