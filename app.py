# app.py
import os
import io
import base64
import numpy as np
import psycopg  # psycopg (v3)
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# --- Face recognition (dlib backend) ---
import cv2
import face_recognition

# -------------------------
# Flask / App config
# -------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# -------------------------
# DB connection helper
# -------------------------
def get_connection():
    """
    Intenta conectar usando DATABASE_URL (Render). Si no está definida,
    usa variables locales DB_* (útil para pruebas locales).
    Devuelve una conexión psycopg (autocommit disabled; se usa with).
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            conn = psycopg.connect(db_url, autocommit=False)
            return conn
        except Exception as e:
            print("❌ Error al conectar con DATABASE_URL:", e)

    # fallback local (cambiar las variables en .env o en Render)
    try:
        conn = psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "fitness"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            autocommit=False
        )
        return conn
    except Exception as e:
        print("❌ No se pudo conectar a PostgreSQL local:", e)
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
            if rostro_bytes is not None:
                cur.execute("""
                    INSERT INTO usuarios (nombre, correo, contrasena, rostro)
                    VALUES (%s, %s, %s, %s)
                """, (nombre, correo, contrasena, rostro_bytes))
            else:
                cur.execute("""
                    INSERT INTO usuarios (nombre, correo, contrasena)
                    VALUES (%s, %s, %s)
                """, (nombre, correo, contrasena))
        conn.commit()

def actualizar_rostro_por_correo(correo, rostro_bytes):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET rostro = %s WHERE correo = %s", (rostro_bytes, correo))
        conn.commit()

# -------------------------
# Util: base64 -> embedding
# -------------------------
def base64_to_rgb_image(base64_str):
    """
    Recibe data URL o base64 puro y retorna imagen RGB (numpy array) o None.
    """
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)  # BGR
        if img_bgr is None:
            return None
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return img_rgb
    except Exception as e:
        print("⚠️ Error al convertir base64 a imagen:", e)
        return None

def obtener_embedding_desde_base64(base64_str):
    """
    Devuelve embedding (np.array dtype=float32) o None.
    Usa face_recognition.face_encodings (dlib) -> 128-D vector.
    """
    img_rgb = base64_to_rgb_image(base64_str)
    if img_rgb is None:
        return None

    # face_recognition espera imágenes RGB
    try:
        encs = face_recognition.face_encodings(img_rgb)
        if not encs:
            # intentamos detectar con un tamaño reducido por si la imagen es grande:
            small = cv2.resize(img_rgb, (0,0), fx=0.5, fy=0.5)
            encs = face_recognition.face_encodings(small)
            if not encs:
                return None
        emb = np.array(encs[0], dtype=np.float32)  # 128 floats
        return emb
    except Exception as e:
        print("⚠️ Error extrayendo embedding:", e)
        return None

def comparar_embeddings(emb1, emb2, umbral=0.6):
    """
    emb1 y emb2 as numpy arrays (float32). Retorna True si son del mismo rostro.
    Umbral por defecto 0.6 (ajustable).
    """
    try:
        dist = np.linalg.norm(emb1 - emb2)
        return float(dist) < umbral
    except Exception as e:
        print("⚠️ Error comparando embeddings:", e)
        return False

# -------------------------
# Inicialización DB
# -------------------------
try:
    crear_tabla()
    print("✅ Tabla 'usuarios' lista.")
except Exception as e:
    print("⚠️ Error al crear tabla:", e)

# Crear admin si no existe (opcional)
try:
    if not obtener_usuario("andresfelipeaguasaco@gmail.com"):
        agregar_usuario("Administrador", "andresfelipeaguasaco@gmail.com", "123456789")
        print("👤 Usuario administrador creado.")
except Exception as e:
    print("⚠️ Error creando admin:", e)

# -------------------------
# Rutas web (templates esperados en templates/)
# -------------------------
@app.route("/")
def root():
    if "usuario" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/home")
def home():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("home.html", usuario=session.get("usuario"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo")
        contrasena = request.form.get("contrasena")
        user = obtener_usuario(correo)
        if user and user[3] == contrasena:
            session["usuario"] = user[1]  # nombre
            session["correo"] = user[2]
            return redirect(url_for("home"))
        return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    session.pop("correo", None)
    return redirect(url_for("login"))

# Página para registro facial (usa la cámara del navegador)
@app.route("/registro_rostro")
def registro_rostro_page():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("registro_rostro.html", usuario=session.get("usuario"))

# -------------------------
# API: registrar rostro (usuario debe estar en sesión)
# -------------------------
@app.route("/api/registrar_rostro", methods=["POST"])
def api_registrar_rostro():
    if "correo" not in session:
        return jsonify({"success": False, "error": "No hay sesión activa"}), 403

    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "No se recibió la imagen"}), 400

    emb = obtener_embedding_desde_base64(data["imagen"])
    if emb is None:
        return jsonify({"success": False, "error": "No se detectó rostro"}), 400

    try:
        rostro_bytes = emb.tobytes()
        actualizar_rostro_por_correo(session["correo"], rostro_bytes)
        return jsonify({"success": True, "mensaje": "Rostro registrado con éxito"})
    except Exception as e:
        print("❌ Error al guardar rostro:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------
# API: login facial (compara con todos los rostros guardados)
# -------------------------
@app.route("/api/login_face", methods=["POST"])
def api_login_face():
    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "No se recibió la imagen"}), 400

    emb_actual = obtener_embedding_desde_base64(data["imagen"])
    if emb_actual is None:
        return jsonify({"success": False, "error": "No se detectó rostro"}), 400

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nombre, correo, rostro FROM usuarios WHERE rostro IS NOT NULL")
                filas = cur.fetchall()

        for nombre, correo, rostro_guardado in filas:
            if rostro_guardado:
                # reconstruir array float32 (128)
                emb_guardado = np.frombuffer(rostro_guardado.tobytes() if hasattr(rostro_guardado, "tobytes") else rostro_guardado, dtype=np.float32)
                if emb_guardado.size == 0:
                    continue
                if comparar_embeddings(emb_guardado, emb_actual, umbral=0.6):
                    # login exitoso
                    session["usuario"] = nombre
                    session["correo"] = correo
                    return jsonify({"success": True, "usuario": nombre})

        return jsonify({"success": False, "error": "Rostro no reconocido"}), 401
    except Exception as e:
        print("❌ Error en login facial:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------
# Rutas admin (ejemplo)
# -------------------------
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "andresfelipeaguasaco@gmail.com")

@app.route("/admin/usuarios")
def admin_usuarios():
    if "correo" not in session or session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado", 403
    usuarios = obtener_todos_usuarios()
    return render_template("admin_usuarios.html", usuarios=usuarios)

# -------------------------
# Health
# -------------------------
@app.route("/health")
def health():
    return {"status": "ok"}, 200

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # En Render (production) se sirve con gunicorn; en local puedes usar app.run
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
