# app.py
import os
import base64
import numpy as np
import psycopg  # psycopg v3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import cv2
from deepface import DeepFace

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# ------------------------- DB connection -------------------------
def get_connection():
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

# ------------------------- DB helpers -------------------------
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

def actualizar_rostro_por_correo(correo, rostro_bytes):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET rostro = %s WHERE correo = %s", (psycopg.Binary(rostro_bytes), correo))
        conn.commit()

# ------------------------- DeepFace helpers -------------------------
def base64_to_rgb_image(base64_str):
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
    img_rgb = base64_to_rgb_image(base64_str)
    if img_rgb is None:
        return None
    try:
        rep = DeepFace.represent(img_path=img_rgb, model_name="Facenet", enforce_detection=True)
        if isinstance(rep, list) and len(rep) > 0 and "embedding" in rep[0]:
            return np.array(rep[0]["embedding"], dtype=np.float32)
        return None
    except Exception as e:
        try:
            rep = DeepFace.represent(img_path=img_rgb, model_name="Facenet", enforce_detection=False)
            if isinstance(rep, list) and len(rep) > 0 and "embedding" in rep[0]:
                return np.array(rep[0]["embedding"], dtype=np.float32)
        except Exception:
            pass
        print("⚠️ Error al generar embedding:", e)
        return None

def comparar_embeddings(emb1, emb2, umbral=10.0):
    try:
        return np.linalg.norm(emb1 - emb2) < umbral
    except Exception as e:
        print("⚠️ Error comparando embeddings:", e)
        return False

# ------------------------- Inicialización -------------------------
try:
    crear_tabla()
    print("✅ Tabla 'usuarios' lista.")
except Exception as e:
    print("⚠️ Error al crear tabla:", e)

try:
    if not obtener_usuario("andresfelipeaguasaco@gmail.com"):
        agregar_usuario("Administrador", "andresfelipeaguasaco@gmail.com", "123456789")
        print("👤 Usuario administrador creado.")
except Exception as e:
    print("⚠️ Error creando admin:", e)

# ------------------------- Decorador -------------------------
def login_required(view_func):
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper

# ------------------------- Rutas -------------------------
@app.route("/")
def root():
    if "usuario" in session:
        return redirect(url_for("home"))  # ✅ Cambiado a home
    return redirect(url_for("login"))

@app.route("/home")
@login_required
def home():
    return render_template("home.html", usuario=session.get("usuario"))  # ✅ Home es el centro

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", usuario=session.get("usuario"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo")
        contrasena = request.form.get("contrasena")

        print(f"🟡 Intento de login con: {correo}")

        user = obtener_usuario(correo)
        if user and user[3] == contrasena:
            session["usuario"] = user[1]
            session["correo"] = user[2]
            print(f"✅ Login correcto para {user[1]}")
            return redirect(url_for("home"))  # ✅ Redirige al centro (home.html)

        print("❌ Login fallido.")
        return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
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

@app.route("/login_face")
def login_face_page():
    return render_template("login_face.html")

@app.route("/registro_rostro")
@login_required
def registro_rostro_page():
    return render_template("registro_rostro.html", usuario=session.get("usuario"))

# ------------------------- APIs -------------------------
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

# ------------------------- Admin -------------------------
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "andresfelipeaguasaco@gmail.com")

@app.route("/admin/usuarios")
def admin_usuarios():
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado", 403
    usuarios = obtener_todos_usuarios()
    return render_template("admin_usuarios.html", usuarios=usuarios)

# ------------------------- Health y errores -------------------------
@app.route("/health")
def health():
    return {"status": "ok"}, 200

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# ------------------------- Main -------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
