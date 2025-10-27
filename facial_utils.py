# facial_utils.py
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["DEEPFACE_BACKEND"] = "torch"
os.environ["KERAS_BACKEND"] = "torch"
os.environ["NO_MTCNN"] = "1"
os.environ["FORCE_RELOAD_BACKENDS"] = "1"

import numpy as np
import base64
from io import BytesIO
from PIL import Image
from deepface import DeepFace

# ============================
# 🔧 Cargar modelo una sola vez
# ============================
_model = None

def cargar_modelo():
    """Carga el modelo Facenet512 (PyTorch) solo una vez."""
    global _model
    if _model is None:
        try:
            _model = DeepFace.build_model("Facenet512")
            print("✅ Modelo 'Facenet512' (PyTorch) cargado correctamente.")
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            _model = None
    return _model


def obtener_embedding(imagen_base64):
    """Convierte imagen Base64 a embedding facial usando RetinaFace + Facenet512."""
    try:
        if not imagen_base64 or "," not in imagen_base64:
            print("⚠️ Imagen Base64 inválida o vacía.")
            return None

        # Decodificar imagen Base64 → RGB
        imagen_bytes = base64.b64decode(imagen_base64.split(",")[1])
        img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        img_np = np.array(img)

        model = cargar_modelo()
        if model is None:
            print("⚠️ Modelo facial no disponible.")
            return None

        # Generar embedding facial
        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            model=model,
            detector_backend="retinaface",
            enforce_detection=True
        )

        emb = np.array(embedding_obj[0]["embedding"], dtype=np.float32)
        print("✅ Embedding facial generado correctamente.")
        return emb

    except Exception as e:
        print(f"⚠️ Error al generar embedding facial: {e}")
        return None


def comparar_embeddings(embedding1, embedding2, threshold=0.35):
    """Compara dos embeddings faciales y devuelve True si son del mismo rostro."""
    try:
        if embedding1 is None or embedding2 is None:
            print("⚠️ Uno de los embeddings está vacío.")
            return False

        distancia = np.linalg.norm(np.array(embedding1) - np.array(embedding2))
        print(f"📏 Distancia entre rostros: {distancia:.4f}")
        return distancia < threshold
    except Exception as e:
        print(f"⚠️ Error comparando embeddings: {e}")
        return False
