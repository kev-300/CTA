import sqlite3
con = sqlite3.connect("registros.db")
con.execute("""
    CREATE VIEW IF NOT EXISTS v_asistencia AS
    SELECT a.id, p.nombre, p.identificacion, r.nombre AS rol,
           a.fecha, a.hora, a.estado, a.metodo
    FROM asistencia a
    JOIN persona p ON p.id = a.persona_id
    JOIN rol r ON r.id = p.rol_id
""")
con.commit()