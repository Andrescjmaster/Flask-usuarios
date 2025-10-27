# facial_utils.py
import os
import sys
import types
import numpy as np
import base64
from io import BytesIO
from PIL import Image

# ======================================================
# 🧩 FIX: Evitar que DeepFace intente importar MTCNN
# ======================================================
# Creamos un módulo vacío para "engañar" a DeepFace y evitar el error:
#   ModuleNotFoundError: import of mtcnn halted; None in sys.modules
sys.modules['mtcnn'] = types.ModuleType("mtcnn")
sys.modules['mtcnn.MTCNN'] = types.ModuleType("MTCNN")

# ======================================================
# ⚙️ Configuración del entorno
# ======================================================
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"       # Suprime logs de TensorFlow
os.environ["DEEPFACE_BACKEND"] = "torch"       # Forzar backend PyTorch
os.environ["KERAS_BACKEND"] = "torch"
os.environ["NO_MTCNN"] = "1"                   # Evita uso de MTCNN
os.environ["FORCE_RELOAD_BACKENDS"] = "1"

# Importamos DeepFace después de definir el mock
from deepface import DeepFace

# ======================================================
# 🔧 Carga única del modelo de reconocimiento
# ======================================================
_model = None

def cargar_modelo():
    """
    Carga el modelo facial (Facenet512) solo una vez para optimizar rendimiento.
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


# ======================================================
# 🧠 Generación de embeddings
# ======================================================
def obtener_embedding(imagen_base64):
    """
    Convierte una imagen Base64 a embedding facial usando RetinaFace + Facenet512.
    """
    try:
        if not imagen_base64 or "," not in imagen_base64:
            print("⚠️ Imagen Base64 inválida o vacía.")
            return None

        # Decodificar Base64 → RGB
        imagen_bytes = base64.b64decode(imagen_base64.split(",")[1])
        img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        img_np = np.array(img)

        model = cargar_modelo()
        if model is None:
            print("⚠️ Modelo facial no disponible.")
            return None

        # Generar embedding facial con RetinaFace
        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            model=model,
            detector_backend="retinaface",  # Solo RetinaFace
            enforce_detection=True
        )

        emb = np.array(embedding_obj[0]["embedding"], dtype=np.float32)
        print("✅ Embedding facial generado correctamente.")
        return emb

    except Exception as e:
        print(f"⚠️ Error al generar embedding facial: {e}")
        return None


# ======================================================
# 🔍 Comparación de embeddings
# ======================================================
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
