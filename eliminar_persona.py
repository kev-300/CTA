import os
import shutil
import pyodbc

base_dir = os.path.dirname(os.path.abspath(__file__))

nombre = input("Ingresa el nombre de la persona a eliminar: ")

# 1. Eliminar de SQL Server
conexion = pyodbc.connect(
    "DRIVER={SQL Server};"
    "SERVER=LAPTOP-C5CHORHI\\SQLEXPRESS;"
    "DATABASE=CTA;"
    "UID=sa;PWD=1234;"
)
cursor = conexion.cursor()
cursor.execute("DELETE FROM asistencia WHERE nombre = ?", (nombre,))
conexion.commit()
print(f"Registros de {nombre} eliminados de la BD")

# 2. Eliminar carpeta de fotos
data_path = os.path.join(base_dir, 'data')
person_path = None
for carpeta in os.listdir(data_path):
    if carpeta.lower().strip() == nombre.lower().strip():
        person_path = os.path.join(data_path, carpeta)
        break

if person_path and os.path.exists(person_path):
    shutil.rmtree(person_path)
    print(f"Fotos de {nombre} eliminadas")
else:
    print(f"No se encontró carpeta de fotos para {nombre}")

# 3. Eliminar del roles.txt
roles_path = os.path.join(base_dir, 'roles.txt')
if os.path.exists(roles_path):
    with open(roles_path, 'r') as f:
        lineas = f.readlines()
    with open(roles_path, 'w') as f:
        for linea in lineas:
            if not linea.startswith(nombre + ','):
                f.write(linea)
    print(f" {nombre} eliminado de roles.txt")

# 4. Eliminar del personas.txt
names_path = os.path.join(base_dir, 'personas.txt')
if os.path.exists(names_path):
    with open(names_path, 'r') as f:
        lineas = f.readlines()
    with open(names_path, 'w') as f:
        for linea in lineas:
            if linea.strip() != nombre:
                f.write(linea)
    print(f" {nombre} eliminado de personas.txt")

print(f"\nRecuerda volver a ejecutar entrenamiento.py para actualizar el modelo")
conexion.close()