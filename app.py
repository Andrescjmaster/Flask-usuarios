import os
import psycopg2
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# ============================================================== 
# ⚙️ CONFIGURACIÓN GLOBAL (variables de entorno para backends)
# ============================================================== 
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["DEEPFACE_BACKEND"] = "torch"
os.environ["KERAS_BACKEND"] = "torch"
os.environ["NO_MTCNN"] = "1"
os.environ["DETECTOR_BACKEND"] = "retinaface"
os.environ["FORCE_RELOAD_BACKENDS"] = "1"

# Evitamos que importaciones de mtcnn rompan el proceso si existe en entorno
import importlib.util
if importlib.util.find_spec("mtcnn"):
    import sys
    sys.modules["mtcnn"] = None

# ============================================================== 
# 🧠 UTILIDADES FACIALES (asumo que facial_utils.py está correcto)
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
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no está configurado en variables de entorno.")
    # sslmode="require" puede omitirse si no aplica; lo dejo por seguridad en hosts como Render
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ============================================================== 
# 🧾 FUNCIONES SQL (CRUD)
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
                cursor.execute(
                    "INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)",
                    (nombre, correo, contraseña)
                )
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
            cursor.execute("SELECT * FROM usuarios ORDER BY id ASC")
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
    print("✅ Tabla 'usuarios' verificada/creada.")
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
        correo = request.form.get("correo")
        contraseña = request.form.get("contraseña")
        usuario = obtener_usuario(correo)

        if usuario and usuario[3] == contraseña:
            session["usuario"] = usuario[1]
            session["correo"] = usuario[2]
            return redirect(url_for("home"))
        return "❌ Usuario o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a>"

    return render_template("login.html")

# ============================================================== 
# 🧠 LOGIN FACIAL (página + POST)
# ============================================================== 
@app.route("/login_face", methods=["GET"])
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
# 🧾 REGISTRO DE USUARIO (página + POST)
# ============================================================== 
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        correo = request.form.get("correo")
        contraseña = request.form.get("contraseña")
        rostro_base64 = request.form.get("rostro")

        rostro_embedding = obtener_embedding(rostro_base64) if rostro_base64 else None

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    if rostro_embedding is not None:
                        cursor.execute("""
                            INSERT INTO usuarios (nombre, correo, contraseña, rostro)
                            VALUES (%s, %s, %s, %s)
                        """, (nombre, correo, contraseña, psycopg2.Binary(rostro_embedding.tobytes())))
                    else:
                        cursor.execute("""
                            INSERT INTO usuarios (nombre, correo, contraseña)
                            VALUES (%s, %s, %s)
                        """, (nombre, correo, contraseña))
                conn.commit()
        except psycopg2.errors.UniqueViolation:
            return "⚠️ Este correo ya está registrado. <a href='/register'>Intenta con otro</a>"
        except Exception as e:
            print("❌ Error al registrar usuario:", e)
            return f"⚠️ Error al registrar usuario: {e}"

        return redirect(url_for("login"))

    return render_template("register.html")

# ============================================================== 
# 📸 ENDPOINTS PARA REGISTRO/VERIFICACIÓN FACIAL (API)
# ============================================================== 
@app.route("/api/registrar_rostro", methods=["POST"])
def api_registrar_rostro():
    if "correo" not in session:
        return jsonify({"success": False, "error": "Usuario no autenticado"}), 401

    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "No se envió la imagen"}), 400

    try:
        embedding = obtener_embedding(data["imagen"])
        if embedding is None:
            return jsonify({"success": False, "error": "No se detectó un rostro válido"}), 400

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET rostro = %s WHERE correo = %s",
                               (psycopg2.Binary(embedding.tobytes()), session["correo"]))
            conn.commit()

        print(f"✅ Rostro registrado para {session['correo']}")
        return jsonify({"success": True, "mensaje": "Rostro registrado con éxito"})

    except Exception as e:
        print("❌ Error api_registrar_rostro:", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/verificar_rostro", methods=["POST"])
def api_verificar_rostro():
    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "Imagen no recibida"}), 400

    try:
        embedding_actual = obtener_embedding(data["imagen"])
        if embedding_actual is None:
            return jsonify({"success": False, "error": "No se detectó rostro válido"}), 400

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
                print(f"✅ Usuario reconocido: {nombre}")
                return jsonify({"success": True, "usuario": nombre})

        return jsonify({"success": False, "error": "Rostro no reconocido"}), 401

    except Exception as e:
        print("❌ Error api_verificar_rostro:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================== 
# 🧩 FUNCIONALIDADES ADICIONALES (asegúrate de que templates existan)
# ============================================================== 
@app.route("/calculadora")
def calculadora():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("calculadora.html", usuario=session["usuario"])

@app.route("/recomendaciones")
def recomendaciones():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("recomendaciones.html")

@app.route("/rutinas")
def rutinas():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("rutinas.html", usuario=session["usuario"])

@app.route("/registro_rostro")
def registro_rostro_page():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("registro_rostro.html", usuario=session["usuario"])

# ============================================================== 
# 🔐 ADMIN
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
            request.form.get("nombre"),
            request.form.get("correo"),
            request.form.get("contraseña")
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
# 🚪 LOGOUT & HEALTH
# ============================================================== 
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/health")
def health():
    return {"status": "ok"}, 200

# ============================================================== 
# 🚀 MAIN
# ============================================================== 
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
