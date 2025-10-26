# facial_utils.py
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"      # Silencia logs de TensorFlow si existieran
os.environ["DEEPFACE_BACKEND"] = "torch"      # Fuerza backend PyTorch
os.environ["KERAS_BACKEND"] = "torch"         # Evita que intente usar tf.keras
os.environ["NO_MTCNN"] = "1"                  # Evita uso de MTCNN en RetinaFace

import numpy as np
import base64
from io import BytesIO
from PIL import Image

# 🚫 DeepFace puede traer dependencias pesadas al importarse,
# por eso lo importamos después de ajustar variables.
from deepface import DeepFace


# ⚙️ Carga del modelo una sola vez
_model = None
def cargar_modelo():
    global _model
    if _model is None:
        try:
            _model = DeepFace.build_model("Facenet512")
            print("✅ Modelo Facenet512 (PyTorch) cargado correctamente.")
        except Exception as e:
            print(f"❌ Error cargando modelo facial: {e}")
            _model = None
    return _model


def obtener_embedding(imagen_base64):
    """Convierte una imagen base64 en un vector facial con DeepFace (PyTorch)."""
    try:
        if not imagen_base64 or "," not in imagen_base64:
            print("⚠️ Imagen base64 inválida o vacía.")
            return None

        # Convertir base64 → RGB array
        imagen_bytes = base64.b64decode(imagen_base64.split(",")[1])
        img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        img_np = np.array(img)

        model = cargar_modelo()
        if model is None:
            print("⚠️ Modelo facial no cargado.")
            return None

        # Obtener embedding (sin detección forzada)
        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            model=model,
            detector_backend="retinaface",  # Usa RetinaFace, no MTCNN
            enforce_detection=False
        )

        emb = np.array(embedding_obj[0]["embedding"], dtype=np.float32)
        return emb

    except Exception as e:
        print(f"⚠️ Error al generar embedding facial: {e}")
        return None


def comparar_embeddings(embedding1, embedding2, threshold=0.4):
    """Compara dos embeddings faciales para determinar si son del mismo rostro."""
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
