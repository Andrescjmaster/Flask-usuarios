# facial_utils.py
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"       # Suprime logs de TensorFlow
os.environ["DEEPFACE_BACKEND"] = "torch"       # Forzar backend PyTorch
os.environ["KERAS_BACKEND"] = "torch"
os.environ["NO_MTCNN"] = "1"                   # Evita uso de MTCNN
os.environ["FORCE_RELOAD_BACKENDS"] = "1"

import numpy as np
import base64
from io import BytesIO
from PIL import Image
from deepface import DeepFace

# ======================================
# 🔧 Carga única del modelo de reconocimiento
# ======================================
_model = None

def cargar_modelo():
    """
    Carga el modelo facial (Facenet512) solo una vez para mejorar rendimiento.
    """
    global _model
    if _model is None:
        try:
            _model = DeepFace.build_model("Facenet512")
            print("✅ Modelo 'Facenet512' (PyTorch) cargado correctamente.")
        except Exception as e:
            print(f"❌ Error cargando el modelo Facenet512: {e}")
            _model = None
    return _model


# ======================================
# 🧠 Generación de embeddings
# ======================================
def obtener_embedding(imagen_base64):
    """
    Convierte una imagen en formato Base64 en un embedding facial
    usando RetinaFace como detector y Facenet512 como extractor de rasgos.
    """
    try:
        if not imagen_base64 or "," not in imagen_base64:
            print("⚠️ Imagen Base64 inválida o vacía.")
            return None

        # Decodificar la imagen Base64 a un objeto PIL
        imagen_bytes = base64.b64decode(imagen_base64.split(",")[1])
        img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        img_np = np.array(img)

        model = cargar_modelo()
        if model is None:
            print("⚠️ No se pudo cargar el modelo facial.")
            return None

        # Usar RetinaFace como detector facial
        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            model=model,
            detector_backend="retinaface",   # 🔥 Solo RetinaFace
            enforce_detection=True
        )

        # Extraer el vector de embedding (128D o 512D)
        emb = np.array(embedding_obj[0]["embedding"], dtype=np.float32)
        print("✅ Embedding facial generado correctamente.")
        return emb

    except Exception as e:
        print(f"⚠️ Error al generar embedding facial: {e}")
        return None


# ======================================
# 🔍 Comparación de embeddings
# ======================================
def comparar_embeddings(embedding1, embedding2, threshold=0.35):
    """
    Compara dos embeddings faciales.
    Devuelve True si la distancia euclidiana < threshold (rostros coinciden).
    """
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
