import base64
import numpy as np
import cv2
from deepface import DeepFace

# ===========================================
# 🚀 Función: convertir imagen base64 a array
# ===========================================
def base64_to_image(base64_str):
    try:
        base64_str = base64_str.split(",")[1] if "," in base64_str else base64_str
        img_bytes = base64.b64decode(base64_str)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print("⚠️ Error convirtiendo imagen base64:", e)
        return None

# ===========================================
# 🧠 Función: obtener embedding facial
# ===========================================
def obtener_embedding(imagen_base64):
    try:
        img = base64_to_image(imagen_base64)
        if img is None:
            return None

        # 🔥 Cargar DeepFace de forma perezosa (solo cuando se llama)
        embedding = DeepFace.represent(
            img_path=img,
            model_name="Facenet512",
            detector_backend="retinaface",
            enforce_detection=True
        )[0]["embedding"]

        return np.array(embedding, dtype=np.float32)
    except Exception as e:
        print("⚠️ Error al obtener embedding:", e)
        return None

# ===========================================
# 🤝 Función: comparar dos embeddings
# ===========================================
def comparar_embeddings(emb1, emb2, umbral=0.6):
    try:
        distancia = np.linalg.norm(emb1 - emb2)
        return distancia < umbral
    except Exception as e:
        print("⚠️ Error al comparar embeddings:", e)
        return False
