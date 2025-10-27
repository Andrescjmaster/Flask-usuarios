import os
import psycopg2
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# ==============================================================
# ⚙️ CONFIGURACIÓN GLOBAL
# ==============================================================
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["DEEPFACE_BACKEND"] = "torch"
os.environ["KERAS_BACKEND"] = "torch"
os.environ["NO_MTCNN"] = "1"
os.environ["DETECTOR_BACKEND"] = "retinaface"
os.environ["FORCE_RELOAD_BACKENDS"] = "1"

# Desactiva TensorFlow si no es necesario (solo PyTorch)
import importlib.util
if importlib.util.find_spec("mtcnn"):
    import sys
    sys.modules["mtcnn"] = None

# ==============================================================
# 🧠 IMPORTA UTILIDADES FACIALES
# ==============================================================
from facial_utils import obtener_embedding, comparar_embeddings

# ==============================================================
# 🧩 CONFIGURACIÓN FLASK
# ==============================================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# ==============================================================
# 🗄️ CONEXIÓN BASE DE DATOS
# ==============================================================
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Conecta de forma segura a PostgreSQL."""
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ==============================================================
# 🧾 FUNCIONES SQL
# ==============================================================
def crear_tabla():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    correo VARCHAR(100) UNIQUE NOT NULL,
                    contraseña VARCHAR(100) NOT NULL,
                    rostro BYTEA
                )
            """)
        conn.commit()

def agregar_usuario(nombre, correo, contraseña):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (nombre, correo, contraseña)
                    VALUES (%s, %s, %s)
                """, (nombre, correo, contraseña))
            conn.commit()
        return True
    except psycopg2.Error as e:
        print("⚠️ Error al agregar usuario:", e)
        return False

def obtener_usuario(correo):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
            return cursor.fetchone()

def obtener_todos_usuarios():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM usuarios")
            return cursor.fetchall()

def modificar_usuario(id_usuario, nombre, correo, contraseña):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE usuarios
                SET nombre = %s, correo = %s, contraseña = %s
                WHERE id = %s
            """, (nombre, correo, contraseña, id_usuario))
        conn.commit()

def eliminar_usuario(id_usuario):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (id_usuario,))
        conn.commit()

# ==============================================================
# 🔧 INICIALIZACIÓN
# ==============================================================
try:
    crear_tabla()
    print("✅ Tabla 'usuarios' verificada o creada correctamente.")
except Exception as e:
    print("⚠️ Error al crear tabla:", e)

try:
    if not obtener_usuario("andresfelipeaguasaco@gmail.com"):
        agregar_usuario("Administrador", "andresfelipeaguasaco@gmail.com", "123456789")
        print("👤 Usuario administrador creado.")
except Exception as e:
    print("⚠️ Error comprobando/creando admin:", e)

# ==============================================================
# 🌐 RUTAS PRINCIPALES
# ==============================================================
@app.route("/")
def root():
    return redirect(url_for("home") if "usuario" in session else url_for("login"))

@app.route("/home")
def home():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("home.html", usuario=session["usuario"])

# ==============================================================
# 🔐 LOGIN NORMAL
# ==============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"]
        contraseña = request.form["contraseña"]
        usuario = obtener_usuario(correo)

        if usuario and usuario[3] == contraseña:
            session["usuario"] = usuario[1]
            session["correo"] = usuario[2]
            return redirect(url_for("home"))
        return "❌ Usuario o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a>"

    return render_template("login.html")

# ==============================================================
# 🧠 LOGIN FACIAL
# ==============================================================
@app.route("/login_face")
def login_face_page():
    return render_template("login_face.html")

@app.route("/login_face", methods=["POST"])
def login_face_post():
    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "Imagen no recibida"}), 400

    embedding_actual = obtener_embedding(data["imagen"])
    if embedding_actual is None:
        return jsonify({"success": False, "error": "No se detectó rostro válido"}), 400

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT nombre, correo, rostro FROM usuarios WHERE rostro IS NOT NULL")
                filas = cursor.fetchall()

        for nombre, correo, rostro_guardado in filas:
            if rostro_guardado is None:
                continue
            embedding_guardado = np.frombuffer(rostro_guardado, dtype=np.float32)
            if comparar_embeddings(embedding_guardado, embedding_actual):
                session["usuario"] = nombre
                session["correo"] = correo
                return jsonify({"success": True, "usuario": nombre})

        return jsonify({"success": False, "error": "Rostro no reconocido"}), 401

    except Exception as e:
        print("❌ Error en login facial:", e)
        return jsonify({"success": False, "error": "Error interno"}), 500

# ==============================================================
# 📸 REGISTRO Y GUARDADO DE ROSTRO
# ==============================================================
@app.route("/registro_rostro")
def registro_rostro():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("registro_rostro.html", usuario=session["usuario"])

@app.route("/guardar_rostro", methods=["POST"])
def guardar_rostro():
    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "No se envió la imagen"})

    correo = session.get("correo")
    if not correo:
        return jsonify({"success": False, "error": "Usuario no autenticado"})

    try:
        embedding = obtener_embedding(data["imagen"])
        if embedding is None:
            return jsonify({"success": False, "error": "No se detectó un rostro válido"})

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE usuarios SET rostro = %s WHERE correo = %s
                """, (psycopg2.Binary(embedding.tobytes()), correo))
            conn.commit()

        print(f"✅ Rostro guardado correctamente para {correo}")
        return jsonify({"success": True})

    except Exception as e:
        print("❌ Error al guardar rostro:", e)
        return jsonify({"success": False, "error": str(e)})

# ==============================================================
# 🔐 ADMINISTRADOR
# ==============================================================
ADMIN_EMAIL = "andresfelipeaguasaco@gmail.com"

@app.route("/admin/usuarios")
def admin_usuarios():
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    usuarios = obtener_todos_usuarios()
    return render_template("admin_usuarios.html", usuarios=usuarios)

@app.route("/admin/modificar/<int:id_usuario>", methods=["GET", "POST"])
def admin_modificar(id_usuario):
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado"

    if request.method == "POST":
        modificar_usuario(
            id_usuario,
            request.form["nombre"],
            request.form["correo"],
            request.form["contraseña"]
        )
        return redirect(url_for("admin_usuarios"))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id_usuario,))
            usuario = cursor.fetchone()

    return render_template("admin_modificar.html", usuario=usuario)

@app.route("/admin/eliminar/<int:id_usuario>")
def admin_eliminar(id_usuario):
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    eliminar_usuario(id_usuario)
    return redirect(url_for("admin_usuarios"))

# ==============================================================
# 🚪 LOGOUT
# ==============================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==============================================================
# 🩺 HEALTH CHECK
# ==============================================================
@app.route("/health")
def health():
    return {"status": "ok"}, 200

# ==============================================================
# 🚀 MAIN
# ==============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
