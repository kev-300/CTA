import cv2
import os

#creacion de la carpeta cpor medio del nombre del trabajador
person_name = input("nombre del trabajador")
person_rol = input(f"Ingresa el rol de {person_name}: ")
base_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_dir, 'data')
person_path = os.path.join(data_path, person_name)

#si no existe la persona crea una carpeta nueva
if not os.path.exists(person_path):
    os.makedirs(person_path)

#modulo para abrir la camara y capturar fotos para entrenamiento
cap = cv2.VideoCapture(0)
face_classifier = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
count = 0
capturing = False
print("Presiona 'S' para comenzar a capturar 200 fotos | ESC para salir")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    #transformar a escala de grises
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_classifier.detectMultiScale(gray, 1.3, 5, minSize=(30, 30))
    
    #documentar los vectores faciales
    for (x, y, w, h) in faces:
        color = (0, 255, 0) if capturing else (255, 255, 0)
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
        cv2.putText(frame, person_name, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

        #guardar fotos en formato .jpg
        if capturing:
            rostro = gray[y:y+h, x:x+w]  # Guardar en escala de grises
            rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
            cv2.imwrite(os.path.join(person_path, f'rostro_{count}.jpg'), rostro)
            count += 1
            cv2.putText(frame, f'Capturando: {count}/200', (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

            #no sobrepasar las 200 capturas
            if count >= 200:
                capturing = False
                print(f"Captura completada: 200 fotos de {person_name} guardadas")

    #condicionales para inicializar o finalizar las capturas
    if not capturing and count == 0:
        cv2.putText(frame, "Presiona 'S' para capturar", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2, cv2.LINE_AA)
    elif not capturing and count >= 200:
        cv2.putText(frame, "Captura completada!", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

    cv2.imshow(f'Capturando - {person_name}', frame)

    key = cv2.waitKey(1)
    if key == 27:
        break
    elif key == ord('s') or key == ord('S'):
        if not capturing and count < 200:
            count = 0
            capturing = True
            print(f"Iniciando captura de {person_name}...")

roles_path = os.path.join(base_dir, 'roles.txt')

# Leer los que ya existen
existentes = {}
if os.path.exists(roles_path):
    with open(roles_path, 'r') as f:
        for line in f:
            n, r = line.strip().split(',')
            existentes[n] = r

# Actualizar o agregar
existentes[person_name] = person_rol

# Reescribir el archivo completo
with open(roles_path, 'w') as f:
    for n, r in existentes.items():
        f.write(f"{n},{r}\n")

cap.release()
cv2.destroyAllWindows()