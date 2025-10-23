# facial_utils.py
import numpy as np
import cv2
from deepface import DeepFace
import base64
from io import BytesIO
from PIL import Image

def obtener_embedding(imagen_base64):
    """
    Convierte una imagen en base64 a un embedding facial usando DeepFace.
    Usa RetinaFace como detector (compatible con Render y sin TensorFlow pesado).
    """
    try:
        # Decodificar imagen desde base64
        imagen_bytes = base64.b64decode(imagen_base64.split(',')[1])
        img = Image.open(BytesIO(imagen_bytes)).convert('RGB')
        img_np = np.array(img)

        # Obtener embedding con RetinaFace (más liviano y estable)
        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            detector_backend="retinaface",  # ⚠️ clave: reemplaza MTCNN
            enforce_detection=False
        )

        return np.array(embedding_obj[0]["embedding"], dtype=np.float32)

    except Exception as e:
        print(f"⚠️ Error al obtener embedding facial: {e}")
        return None


def comparar_embeddings(embedding1, embedding2, threshold=0.4):
    """
    Compara dos embeddings faciales. Retorna True si son similares.
    """
    if embedding1 is None or embedding2 is None:
        return False
    distancia = np.linalg.norm(np.array(embedding1) - np.array(embedding2))
    return distancia < threshold
