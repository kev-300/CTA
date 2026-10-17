import os
import sqlite3

DB = "registros.db"

if os.path.exists(DB):
    raise SystemExit(f"{DB} ya existe. Bórralo primero si quieres recrearlo.")

con = sqlite3.connect(DB)
con.executescript("""
CREATE TABLE rol (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE
);
CREATE TABLE persona (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL,
  identificacion TEXT NOT NULL UNIQUE,
  rol_id INTEGER NOT NULL REFERENCES rol(id),
  activo INTEGER DEFAULT 1
);
CREATE TABLE biometrico (
  id INTEGER PRIMARY KEY,
  persona_id INTEGER NOT NULL REFERENCES persona(id),
  tipo TEXT CHECK(tipo IN ('rostro','huella')),
  plantilla BLOB NOT NULL
);
CREATE TABLE asistencia (
  id INTEGER PRIMARY KEY,
  persona_id INTEGER NOT NULL REFERENCES persona(id),
  fecha TEXT NOT NULL,
  hora TEXT,
  estado TEXT CHECK(estado IN ('PRESENTE','AUSENTE','FUERA_DE_HORARIO')),
  metodo TEXT DEFAULT 'manual' CHECK(metodo IN ('manual','rostro','huella')),
  UNIQUE(persona_id, fecha)
);
""")
con.executemany("INSERT INTO rol (nombre) VALUES (?)",
                [(r,) for r in ("Malacatero", "Piquero", "Cochero",
                                "Administrador", "Patiero", "RRHH")])
con.commit()
con.close()
print(f"{DB} creado correctamente.")
