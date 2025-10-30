import base64
import numpy as np
import cv2
from deepface import DeepFace
import torch

# ===========================================
# 🚀 Función: convertir imagen base64 a array
# ===========================================
def base64_to_image(base64_str):
    """Convierte una imagen en formato base64 a un array OpenCV."""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print("⚠️ Error convirtiendo imagen base64:", e)
        return None

# ===========================================
# 🧠 Función: obtener embedding facial (PyTorch)
# ===========================================
def obtener_embedding(imagen_base64):
    """
    Convierte una imagen base64 en un embedding facial usando DeepFace.
    Usa el modelo 'Facenet512' (PyTorch) con detector RetinaFace.
    """
    try:
        img = base64_to_image(imagen_base64)
        if img is None:
            print("⚠️ Imagen no válida.")
            return None

        # ⚙️ Usar 'enforce_detection=False' para evitar errores si no detecta rostro
        resultado = DeepFace.represent(
            img_path=img,
            model_name="Facenet512",
            detector_backend="retinaface",
            enforce_detection=False
        )

        if not resultado or "embedding" not in resultado[0]:
            print("⚠️ No se pudo obtener el embedding facial.")
            return None

        embedding = np.array(resultado[0]["embedding"], dtype=np.float32)
        return embedding

    except Exception as e:
        print("⚠️ Error al obtener embedding:", e)
        return None

# ===========================================
# 🤝 Función: comparar dos embeddings
# ===========================================
def comparar_embeddings(emb1, emb2, umbral=0.6):
    """
    Compara dos embeddings faciales usando la distancia euclidiana.
    Retorna True si los rostros son similares.
    """
    try:
        if emb1 is None or emb2 is None:
            print("⚠️ Uno de los embeddings está vacío.")
            return False

        # Si hay GPU disponible, usarla
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        emb1_tensor = torch.tensor(emb1, dtype=torch.float32, device=device)
        emb2_tensor = torch.tensor(emb2, dtype=torch.float32, device=device)

        distancia = torch.norm(emb1_tensor - emb2_tensor).item()
        return distancia < umbral
    except Exception as e:
        print("⚠️ Error al comparar embeddings:", e)
        return False
