# facial_utils.py
import numpy as np
import cv2
from deepface import DeepFace
import base64
from io import BytesIO
from PIL import Image

def obtener_embedding(imagen_base64):
    # Decodificar imagen desde base64
    imagen_bytes = base64.b64decode(imagen_base64.split(',')[1])
    img = Image.open(BytesIO(imagen_bytes)).convert('RGB')
    img_np = np.array(img)
    
    # Obtener embedding con DeepFace
    embedding_obj = DeepFace.represent(img_np, model_name="Facenet512", enforce_detection=False)
    return np.array(embedding_obj[0]["embedding"], dtype=np.float32)

def comparar_embeddings(embedding1, embedding2, threshold=0.4):
    # Calcular distancia entre embeddings (menor distancia = más parecido)
    distancia = np.linalg.norm(np.array(embedding1) - np.array(embedding2))
    return distancia < threshold