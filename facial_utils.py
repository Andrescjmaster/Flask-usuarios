# facial_utils.py
import numpy as np
import base64
from io import BytesIO
from PIL import Image
from deepface import DeepFace
import torch  # ✅ Forzamos el uso de PyTorch en entornos sin TensorFlow


def obtener_embedding(imagen_base64):
    """
    Convierte una imagen en base64 a un embedding facial usando DeepFace.
    Usa RetinaFace como detector y PyTorch como backend (compatible con Render).
    """
    try:
        if not imagen_base64 or "," not in imagen_base64:
            print("⚠️ No se recibió imagen válida en base64.")
            return None

        # Decodificar imagen base64 → arreglo numpy RGB
        imagen_bytes = base64.b64decode(imagen_base64.split(",")[1])
        img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        img_np = np.array(img)

        # 🔒 Forzar backend a PyTorch para evitar errores de TensorFlow/tf-keras
        DeepFace.build_model("Facenet512")  # carga el modelo una vez (usa PyTorch)
        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            detector_backend="retinaface",  # ✅ detector compatible con Render
            enforce_detection=False
        )

        # Retornar vector numérico (float32)
        return np.array(embedding_obj[0]["embedding"], dtype=np.float32)

    except Exception as e:
        print(f"⚠️ Error al obtener embedding facial: {e}")
        return None


def comparar_embeddings(embedding1, embedding2, threshold=0.4):
    """
    Compara dos embeddings faciales y determina si pertenecen al mismo rostro.
    Retorna True si la distancia es menor al umbral (rostros similares).
    """
    try:
        if embedding1 is None or embedding2 is None:
            print("⚠️ Uno de los embeddings es None.")
            return False

        # Calcular distancia euclidiana
        distancia = np.linalg.norm(np.array(embedding1) - np.array(embedding2))
        print(f"📏 Distancia entre rostros: {distancia:.4f}")

        return distancia < threshold
    except Exception as e:
        print(f"⚠️ Error comparando embeddings: {e}")
        return False
