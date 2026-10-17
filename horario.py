import sqlite3
from datetime import datetime, time

INICIO, FIN = time(6, 40), time(7, 30)

def registrar_asistencia(con, persona_id, metodo='manual'):
    ahora = datetime.now()
    estado = 'PRESENTE' if INICIO <= ahora.time() <= FIN else 'FUERA_DE_HORARIO'
    con.execute("""INSERT OR IGNORE INTO asistencia
                   (persona_id, fecha, hora, estado, metodo)
                   VALUES (?,?,?,?,?)""",
                (persona_id, ahora.date().isoformat(),
                 ahora.strftime('%H:%M:%S'), estado, metodo))
    con.commit()


def agregar_persona(con, nombre, identificacion, rol):
    try:
        cur = con.execute(
            "INSERT INTO persona (nombre, identificacion, rol) VALUES (?,?,?)",
            (nombre.strip(), identificacion.strip(), rol))
        con.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Identificación duplicada o rol inválido")