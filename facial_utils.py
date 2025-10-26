# facial_utils.py
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # silencia TensorFlow
os.environ["DEEPFACE_BACKEND"] = "torch"  # fuerza backend PyTorch
os.environ["KERAS_BACKEND"] = "torch"     # evita carga de tf.keras

import numpy as np
import base64
from io import BytesIO
from PIL import Image
from deepface import DeepFace


def obtener_embedding(imagen_base64):
    """Convierte una imagen base64 en embedding facial usando DeepFace (Facenet512 + PyTorch)."""
    try:
        if not imagen_base64 or "," not in imagen_base64:
            print("⚠️ No se recibió imagen válida en base64.")
            return None

        # Decodificar imagen base64 → RGB array
        imagen_bytes = base64.b64decode(imagen_base64.split(",")[1])
        img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        img_np = np.array(img)

        # Cargar modelo con backend PyTorch
        model = DeepFace.build_model("Facenet512")

        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            detector_backend="retinaface",
            enforce_detection=False
        )

        return np.array(embedding_obj[0]["embedding"], dtype=np.float32)

    except Exception as e:
        print(f"⚠️ Error al obtener embedding facial: {e}")
        return None


def comparar_embeddings(embedding1, embedding2, threshold=0.4):
    """Compara dos embeddings faciales y determina si son del mismo rostro."""
    try:
        if embedding1 is None or embedding2 is None:
            print("⚠️ Uno de los embeddings es None.")
            return False

        distancia = np.linalg.norm(np.array(embedding1) - np.array(embedding2))
        print(f"📏 Distancia entre rostros: {distancia:.4f}")
        return distancia < threshold
    except Exception as e:
        print(f"⚠️ Error comparando embeddings: {e}")
        return False
