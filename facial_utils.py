# facial_utils.py (versión optimizada para Render)
import numpy as np
import base64
from io import BytesIO
from PIL import Image
from deepface import DeepFace


# ⚡ Cargamos el modelo una sola vez (esto evita el consumo masivo de RAM en Render)
try:
    print("🚀 Cargando modelo facial (Facenet512 con backend PyTorch)...")
    MODEL = DeepFace.build_model("Facenet512")
    print("✅ Modelo facial cargado correctamente.")
except Exception as e:
    MODEL = None
    print(f"❌ Error al cargar modelo facial: {e}")


def obtener_embedding(imagen_base64):
    """
    Convierte una imagen en base64 a un embedding facial usando el modelo precargado.
    """
    try:
        if not imagen_base64 or "," not in imagen_base64:
            print("⚠️ No se recibió imagen válida en base64.")
            return None

        # Decodificar base64 → imagen RGB
        imagen_bytes = base64.b64decode(imagen_base64.split(",")[1])
        img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        img_np = np.array(img)

        if MODEL is None:
            print("⚠️ El modelo no está cargado en memoria.")
            return None

        # Obtener representación facial (embedding)
        embedding_obj = DeepFace.represent(
            img_path=img_np,
            model_name="Facenet512",
            detector_backend="retinaface",
            enforce_detection=False,
            model=MODEL  # ✅ Reutiliza el modelo ya cargado
        )

        return np.array(embedding_obj[0]["embedding"], dtype=np.float32)

    except Exception as e:
        print(f"⚠️ Error al obtener embedding facial: {e}")
        return None


def comparar_embeddings(embedding1, embedding2, threshold=0.4):
    """
    Compara dos embeddings y determina si son del mismo rostro.
    """
    try:
        if embedding1 is None or embedding2 is None:
            return False

        distancia = np.linalg.norm(np.array(embedding1) - np.array(embedding2))
        print(f"📏 Distancia facial: {distancia:.4f}")
        return distancia < threshold
    except Exception as e:
        print(f"⚠️ Error comparando embeddings: {e}")
        return False
