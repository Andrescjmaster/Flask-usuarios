# app.py
import os
import base64
import numpy as np
import psycopg
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import cv2
from deepface import DeepFace

# -------------------------
# Flask / App config
# -------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# -------------------------
# DB connection helper
# -------------------------
def get_connection():
    """Intenta conectar usando DATABASE_URL (Render) o fallback local."""
    db_url = os.getenv("DATABASE_URL")
    try:
        if db_url:
            return psycopg.connect(db_url, autocommit=False)
        else:
            return psycopg.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME", "fitness"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "postgres"),
                autocommit=False
            )
    except Exception as e:
        print("❌ Error al conectar a la base de datos:", e)
        raise

# -------------------------
# DB helpers
# -------------------------
def crear_tabla():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    correo VARCHAR(100) UNIQUE NOT NULL,
                    contrasena VARCHAR(200) NOT NULL,
                    rostro BYTEA
                );
            """)
        conn.commit()

def obtener_usuario(correo):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
            return cur.fetchone()

def obtener_todos_usuarios():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios ORDER BY id ASC")
            return cur.fetchall()

def agregar_usuario(nombre, correo, contrasena, rostro_bytes=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if rostro_bytes:
                cur.execute(
                    "INSERT INTO usuarios (nombre, correo, contrasena, rostro) VALUES (%s, %s, %s, %s)",
                    (nombre, correo, contrasena, rostro_bytes),
                )
            else:
                cur.execute(
                    "INSERT INTO usuarios (nombre, correo, contrasena) VALUES (%s, %s, %s)",
                    (nombre, correo, contrasena),
                )
        conn.commit()

def actualizar_rostro_por_correo(correo, rostro_bytes):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET rostro = %s WHERE correo = %s", (rostro_bytes, correo))
        conn.commit()

# -------------------------
# Funciones de reconocimiento facial (DeepFace)
# -------------------------
def base64_to_rgb_image(base64_str):
    """Convierte base64 a imagen RGB."""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return None
        return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    except Exception as e:
        print("⚠️ Error al decodificar imagen:", e)
        return None

def obtener_embedding_desde_base64(base64_str):
    """Obtiene embedding facial usando DeepFace (modelo FaceNet)."""
    img_rgb = base64_to_rgb_image(base64_str)
    if img_rgb is None:
        return None
    try:
        embedding = DeepFace.represent(
            img_path=img_rgb,
            model_name="Facenet",
            enforce_detection=False
        )[0]["embedding"]
        return np.array(embedding, dtype=np.float32)
    except Exception as e:
        print("⚠️ Error al generar embedding:", e)
        return None

def comparar_embeddings(emb1, emb2, umbral=10.0):
    """Compara embeddings con DeepFace (distancia Euclidiana)."""
    try:
        dist = np.linalg.norm(emb1 - emb2)
        return dist < umbral
    except Exception as e:
        print("⚠️ Error comparando embeddings:", e)
        return False

# -------------------------
# Inicialización
# -------------------------
try:
    crear_tabla()
    print("✅ Tabla 'usuarios' lista.")
except Exception as e:
    print("⚠️ Error creando tabla:", e)

# Crear admin si no existe
try:
    if not obtener_usuario("andresfelipeaguasaco@gmail.com"):
        agregar_usuario("Administrador", "andresfelipeaguasaco@gmail.com", "123456789")
        print("👤 Usuario administrador creado.")
except Exception as e:
    print("⚠️ Error creando admin:", e)

# -------------------------
# Rutas web
# -------------------------
@app.route("/")
def root():
    return redirect(url_for("home") if "usuario" in session else url_for("login"))

@app.route("/home")
def home():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("home.html", usuario=session["usuario"])

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo")
        contrasena = request.form.get("contrasena")
        user = obtener_usuario(correo)
        if user and user[3] == contrasena:
            session["usuario"] = user[1]
            session["correo"] = user[2]
            return redirect(url_for("home"))
        return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/registro_rostro")
def registro_rostro_page():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("registro_rostro.html", usuario=session["usuario"])

# -------------------------
# API: registrar rostro
# -------------------------
@app.route("/api/registrar_rostro", methods=["POST"])
def api_registrar_rostro():
    if "correo" not in session:
        return jsonify({"success": False, "error": "No hay sesión activa"}), 403

    data = request.get_json()
    emb = obtener_embedding_desde_base64(data.get("imagen", ""))
    if emb is None:
        return jsonify({"success": False, "error": "No se detectó rostro"}), 400

    try:
        actualizar_rostro_por_correo(session["correo"], emb.tobytes())
        return jsonify({"success": True, "mensaje": "Rostro registrado con éxito"})
    except Exception as e:
        print("❌ Error guardando rostro:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------
# API: login facial
# -------------------------
@app.route("/api/login_face", methods=["POST"])
def api_login_face():
    data = request.get_json()
    emb_actual = obtener_embedding_desde_base64(data.get("imagen", ""))
    if emb_actual is None:
        return jsonify({"success": False, "error": "No se detectó rostro"}), 400

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nombre, correo, rostro FROM usuarios WHERE rostro IS NOT NULL")
                filas = cur.fetchall()

        for nombre, correo, rostro_guardado in filas:
            if not rostro_guardado:
                continue
            emb_guardado = np.frombuffer(rostro_guardado, dtype=np.float32)
            if comparar_embeddings(emb_guardado, emb_actual):
                session["usuario"], session["correo"] = nombre, correo
                return jsonify({"success": True, "usuario": nombre})

        return jsonify({"success": False, "error": "Rostro no reconocido"}), 401
    except Exception as e:
        print("❌ Error login facial:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------
# Admin
# -------------------------
@app.route("/admin/usuarios")
def admin_usuarios():
    if session.get("correo") != os.getenv("ADMIN_EMAIL", "andresfelipeaguasaco@gmail.com"):
        return "🚫 Acceso denegado", 403
    usuarios = obtener_todos_usuarios()
    return render_template("admin_usuarios.html", usuarios=usuarios)

# -------------------------
# Health check
# -------------------------
@app.route("/health")
def health():
    return {"status": "ok"}, 200

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
