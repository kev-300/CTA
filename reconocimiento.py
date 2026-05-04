import cv2
import os
import numpy as np
import pyodbc
from datetime import datetime

#conexion de python y sql-server
conexion = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=LAPTOP-C5CHORHI\\SQLEXPRESS;"
    "DATABASE=CTA;"
    "UID=sa;"
    "PWD=1234;"
)
cursor = conexion.cursor()

registros_hoy = set() 
base_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(base_dir, 'modeloLBPHFace.xml')
names_path = os.path.join(base_dir, 'personas.txt')

# Verificar que el modelo existe
if not os.path.exists(model_path):
    print(" No se encontró el modelo. Ejecuta primero entrenamiento.py")
    exit()

# Cargar lista de personas desde archivo (orden consistente)
with open(names_path, 'r') as f:
    people_list = [line.strip() for line in f.readlines()]

roles_path = os.path.join(base_dir, 'roles.txt')
roles = {}
with open(roles_path, 'r') as f:
    for line in f:
        nombre, rol = line.strip().split(',')
        roles[nombre] = rol


print(f"Personas registradas: {people_list}")

# Cargar modelo y detector
face_recognizer = cv2.face.LBPHFaceRecognizer_create()
face_recognizer.read(model_path)

face_classifier = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

cap = cv2.VideoCapture(0)
print("Iniciando reconocimiento Presiona ESC para salir")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_classifier.detectMultiScale(gray, 1.3, 5, minSize=(30, 30))

    for (x, y, w, h) in faces:
        rostro = cv2.resize(gray[y:y+h, x:x+w], (150, 150))
        label, confidence = face_recognizer.predict(rostro)

        if confidence < 70:
            name = people_list[label]
            color = (0, 255, 0)       # Verde = reconocido
            text = f"{name} ({confidence:.1f})"

            hoy = datetime.now().date()
            clave = (name, hoy)
            if clave not in registros_hoy:
                hora_actual = datetime.now().time()
                rol = roles.get(name, "desconocido")
                cursor.execute(
                "INSERT INTO asistencia (nombre, rol, fecha, hora) VALUES (?, ?, ?, ?)",
                (name, rol, hoy, hora_actual)
                )
                conexion.commit()
                registros_hoy.add(clave)
                print(f"Registrado: {name} a las {hora_actual}")
        else:
            name = "Desconocido"
            color = (0, 0, 255)       # Rojo = no reconocido
            text = f"Desconocido ({confidence:.1f})"

        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
        cv2.putText(frame, text, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

    cv2.imshow('Reconocimiento Facial', frame)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()