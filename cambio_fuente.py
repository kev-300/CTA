"""Pasa a MAYÚSCULAS los nombres de tablas y columnas de registros.db
sin perder datos. Haz una copia de registros.db antes de ejecutarlo."""
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registros.db")
con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys = OFF")

# Las vistas se quitan y se vuelven a crear al final
vistas = con.execute("SELECT name, sql FROM sqlite_master WHERE type='view'").fetchall()
for nombre, _ in vistas:
    con.execute(f'DROP VIEW "{nombre}"')

tablas = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
for t in tablas:
    for col in [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')]:
        if col != col.upper():
            con.execute(f'ALTER TABLE "{t}" RENAME COLUMN "{col}" TO "{col.upper()}"')
    if t != t.upper():
        # SQLite no permite renombrar solo cambiando mayúsculas: se hace en dos pasos
        con.execute(f'ALTER TABLE "{t}" RENAME TO "{t}_tmp"')
        con.execute(f'ALTER TABLE "{t}_tmp" RENAME TO "{t.upper()}"')

for _, sql in vistas:
    con.execute(sql)
con.commit()
con.close()
print("Listo: tablas y columnas en mayúsculas.")