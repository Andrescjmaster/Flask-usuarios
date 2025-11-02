# app.py
import os
import base64
import numpy as np
import psycopg  # psycopg v3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
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

def obtener_usuario_por_id(id_usuario):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE id = %s", (id_usuario,))
            return cur.fetchone()

def obtener_todos_usuarios():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios ORDER BY id ASC")
            return cur.fetchall()

def agregar_usuario(nombre, correo, contrasena, rostro_bytes=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                if rostro_bytes:
                    cur.execute(
                        "INSERT INTO usuarios (nombre, correo, contrasena, rostro) VALUES (%s, %s, %s, %s)",
                        (nombre, correo, contrasena, psycopg.Binary(rostro_bytes)),
                    )
                else:
                    cur.execute(
                        "INSERT INTO usuarios (nombre, correo, contrasena) VALUES (%s, %s, %s)",
                        (nombre, correo, contrasena),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

def modificar_usuario(id_usuario, nombre, correo, contrasena):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE usuarios SET nombre=%s, correo=%s, contrasena=%s WHERE id=%s
            """, (nombre, correo, contrasena, id_usuario))
        conn.commit()

def eliminar_usuario(id_usuario):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE id=%s", (id_usuario,))
        conn.commit()

def actualizar_rostro_por_correo(correo, rostro_bytes):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET rostro = %s WHERE correo = %s", (psycopg.Binary(rostro_bytes), correo))
        conn.commit()

# -------------------------
# Funciones de reconocimiento facial (DeepFace)
# -------------------------
def base64_to_rgb_image(base64_str):
    """Convierte una cadena base64 (data URL o puro) a imagen RGB (numpy array)."""
    try:
        if not base64_str:
            return None
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return None
        return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    except Exception as e:
        print("⚠️ Error al decodificar imagen:", e)
        return None

def obtener_embedding_desde_base64(base64_str):
    """Obtiene embedding facial usando DeepFace (modelo FaceNet). Retorna np.array float32 o None."""
    img_rgb = base64_to_rgb_image(base64_str)
    if img_rgb is None:
        return None
    try:
        # DeepFace.represent acepta numpy arrays como img_path
        rep = DeepFace.represent(img_path=img_rgb, model_name="Facenet", enforce_detection=True)
        # DeepFace.represent puede devolver lista de dicts; tomamos el primer embedding
        if isinstance(rep, list) and len(rep) > 0 and "embedding" in rep[0]:
            embedding = rep[0]["embedding"]
            return np.array(embedding, dtype=np.float32)
        # fallback simple si no trae estructura esperada
        return None
    except Exception as e:
        # Si enforce_detection falla, intentamos con enforce_detection=False una vez
        try:
            rep = DeepFace.represent(img_path=img_rgb, model_name="Facenet", enforce_detection=False)
            if isinstance(rep, list) and len(rep) > 0 and "embedding" in rep[0]:
                embedding = rep[0]["embedding"]
                return np.array(embedding, dtype=np.float32)
        except Exception:
            pass
        print("⚠️ Error al generar embedding:", e)
        return None

def comparar_embeddings(emb1, emb2, umbral=10.0):
    """Compara dos embeddings (euclidiana). Umbral por defecto 10.0 (ajustable según tu modelo)."""
    try:
        dist = np.linalg.norm(emb1 - emb2)
        return float(dist) < float(umbral)
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
# Helpers de rutas
# -------------------------
def login_required(view_func):
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper

# -------------------------
# Rutas web (según templates en tu carpeta)
# -------------------------
@app.route("/")
def root():
    return redirect(url_for("home") if "usuario" in session else url_for("login"))

@app.route("/home")
@login_required
def home():
    return render_template("home.html", usuario=session.get("usuario"))

@app.route("/base")
@login_required
def base_page():
    # si tienes "base.html" como plantilla, la mostramos
    return render_template("base.html", usuario=session.get("usuario"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", usuario=session.get("usuario"))

@app.route("/calculadora")
@login_required
def calculadora():
    return render_template("calculadora.html", usuario=session.get("usuario"))

@app.route("/recomendaciones")
@login_required
def recomendaciones():
    return render_template("recomendaciones.html", usuario=session.get("usuario"))

@app.route("/rutinas")
@login_required
def rutinas():
    return render_template("rutinas.html", usuario=session.get("usuario"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # soporta registro tradicional por formulario
        nombre = request.form.get("nombre")
        correo = request.form.get("correo")
        contrasena = request.form.get("contrasena")
        try:
            agregar_usuario(nombre, correo, contrasena)
            return redirect(url_for("login"))
        except Exception as e:
            print("❌ Error registrando usuario:", e)
            return render_template("register.html", error="Error registrando usuario")
    return render_template("register.html")

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

@app.route("/login_face")
def login_face_page():
    return render_template("login_face.html")

@app.route("/registro_rostro")
@login_required
def registro_rostro_page():
    return render_template("registro_rostro.html", usuario=session.get("usuario"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

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
            if not rostro_guardado:
                continue
            # rostro_guardado viene como bytes (BYTEA)
            emb_guardado = np.frombuffer(rostro_guardado, dtype=np.float32)
            if emb_guardado.size == 0:
                continue
            if comparar_embeddings(emb_guardado, emb_actual):
                session["usuario"] = nombre
                session["correo"] = correo
                return jsonify({"success": True, "usuario": nombre})

        return jsonify({"success": False, "error": "Rostro no reconocido"}), 401
    except Exception as e:
        print("❌ Error en login facial:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------
# Admin: listar, modificar, eliminar
# -------------------------
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "andresfelipeaguasaco@gmail.com")

@app.route("/admin/usuarios")
def admin_usuarios():
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado", 403
    usuarios = obtener_todos_usuarios()
    return render_template("admin_usuarios.html", usuarios=usuarios)

@app.route("/admin/modificar/<int:id_usuario>", methods=["GET", "POST"])
def admin_modificar(id_usuario):
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado", 403
    user = obtener_usuario_por_id(id_usuario)
    if not user:
        abort(404)
    if request.method == "POST":
        nombre = request.form.get("nombre")
        correo = request.form.get("correo")
        contrasena = request.form.get("contrasena")
        modificar_usuario(id_usuario, nombre, correo, contrasena)
        return redirect(url_for("admin_usuarios"))
    return render_template("admin_modificar.html", usuario=user)

@app.route("/admin/eliminar/<int:id_usuario>", methods=["POST", "GET"])
def admin_eliminar(id_usuario):
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado", 403
    eliminar_usuario(id_usuario)
    return redirect(url_for("admin_usuarios"))

# -------------------------
# Health
# -------------------------
@app.route("/health")
def health():
    return {"status": "ok"}, 200

# -------------------------
# Error handlers (opcional, más amigables)
# -------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
