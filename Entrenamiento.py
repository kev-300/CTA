import cv2
import os
import numpy as np

base_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_dir, 'data')
model_path = os.path.join(base_dir, 'modeloLBPHFace.xml')
names_path = os.path.join(base_dir, 'personas.txt')

people_list = []
labels = []
faces_data = []

# Recorre cada carpeta (una por persona)
for label, person_name in enumerate(sorted(os.listdir(data_path))):
    person_path = os.path.join(data_path, person_name)
    if not os.path.isdir(person_path):
        continue

    people_list.append(person_name.strip())

    for img_file in os.listdir(person_path):
        img_path = os.path.join(person_path, img_file)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        img = cv2.resize(img, (150, 150))
        faces_data.append(img)
        labels.append(label)

if len(faces_data) == 0:
    print("No se encontraron imágenes. Ejecuta primero captura.py")
    exit()

print(f"Entrenando con {len(faces_data)} imágenes de {len(people_list)} personas...")

# Entrenar modelo LBPH
face_recognizer = cv2.face.LBPHFaceRecognizer_create()
face_recognizer.train(faces_data, np.array(labels))
face_recognizer.save(model_path)

# Guardar lista de personas (mismo orden que los labels)
with open(names_path, 'w') as f:
    for name in people_list:
        f.write(f"{name}\n")

print(f" Modelo guardado en: {model_path}")
print(f" Personas registradas: {people_list}")