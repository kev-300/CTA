import pyodbc
import pandas as pd
import os

nombre = input("Ingresa el nombre del trabajador: ")

conexion = pyodbc.connect(
    "DRIVER={SQL Server};"
    "SERVER=LAPTOP-C5CHORHI\\SQLEXPRESS;"
    "DATABASE=CTA;"
    "UID=sa;PWD=1234;"
)

query = "SELECT nombre, rol, fecha, hora FROM asistencia WHERE nombre = ?"
df = pd.read_sql(query, conexion, params=[nombre])

if df.empty:
    print(f"No se encontraron registros para '{nombre}'")
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    archivo = os.path.join(base_dir, f"asistencia_{nombre}.xlsx")
    df.to_excel(archivo, index=False)
    print(f"Archivo exportado: {archivo}")

conexion.close()