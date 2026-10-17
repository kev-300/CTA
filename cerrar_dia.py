"""Marca AUSENTE a quien no se registró. Se ejecuta solo, sin ventana,
con el Programador de tareas de Windows (ver instrucciones)."""
import os
import sqlite3
from datetime import datetime, date, time, timedelta

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registros.db")
FIN = time(7, 30)
DIAS_LABORALES = {0, 1, 2, 3, 4}   # 0=lunes ... 6=domingo; ajusta a tu caso


def cerrar_dias(con):
    ahora = datetime.now()
    hoy = ahora.date()
    ultimo = con.execute("SELECT MAX(fecha) FROM asistencia").fetchone()[0]
    dia = date.fromisoformat(ultimo) if ultimo else hoy
    limite = hoy if ahora.time() > FIN else hoy - timedelta(days=1)
    while dia <= limite:
        if dia.weekday() in DIAS_LABORALES:
            con.execute("""INSERT OR IGNORE INTO asistencia (persona_id, fecha, estado)
                           SELECT id, ?, 'AUSENTE' FROM persona WHERE activo = 1""",
                        (dia.isoformat(),))
        dia += timedelta(days=1)
    con.commit()


if __name__ == "__main__":
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    cerrar_dias(con)
    con.close()
