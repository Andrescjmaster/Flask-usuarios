import os
import psycopg
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from facial_utils import obtener_embedding, comparar_embeddings
# 🔥 IMPORTANTE: Carga las variables de entorno, incluyendo DATABASE_URL
from dotenv import load_dotenv
load_dotenv() 

# ============================================================== 
# ⚙️ CONFIGURACIÓN GLOBAL (DeepFace - SOLO TORCH + RETINAFACE)
# ============================================================== 
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["DETECTOR_BACKEND"] = "retinaface"
os.environ["BACKEND"] = "torch"  # 🔥 Usa PyTorch en lugar de TensorFlow
os.environ["DISABLE_TF"] = "1"  # 🚫 Desactiva TensorFlow
os.environ["FORCE_RELOAD_BACKENDS"] = "1"

print("🧠 DeepFace optimizado para PyTorch + RetinaFace")

# ============================================================== 
# ⚙️ CONFIGURACIÓN FLASK
# ============================================================== 
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# ============================================================== 
# 🗄️ CONEXIÓN A LA BASE DE DATOS DE RENDER
# ============================================================== 
# La URL de Render incluye user, password, host, port y sslmode.
# Debe estar definida en tu archivo .env como:
# DATABASE_URL="postgres://user:password@host:port/dbname?ssl=true"
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL no está definida en el entorno.")
    try:
        # psycopg.connect() usa la URL de conexión completa.
        conn = psycopg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print("❌ Error de conexión a PostgreSQL:", e)
        # Se lanza la excepción para detener la aplicación si no hay conexión.
        raise

# ============================================================== 
# 🧾 FUNCIONES DE BASE DE DATOS
# ============================================================== 
def crear_tabla():
    try:
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
        print("✅ Tabla 'usuarios' lista.")
    except Exception as e:
        print("⚠️ Error al crear tabla:", e)

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

def agregar_usuario(nombre, correo, contraseña, rostro=None):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            if rostro is not None:
                rostro_bytes = np.array(rostro, dtype=np.float32).tobytes()
                cursor.execute("""
                    INSERT INTO usuarios (nombre, correo, contraseña, rostro)
                    VALUES (%s, %s, %s, %s)
                """, (nombre, correo, contraseña, psycopg.Binary(rostro_bytes)))
            else:
                cursor.execute("""
                    INSERT INTO usuarios (nombre, correo, contraseña)
                    VALUES (%s, %s, %s)
                """, (nombre, correo, contraseña))
        conn.commit()

def modificar_usuario(id_usuario, nombre, correo, contraseña):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE usuarios SET nombre=%s, correo=%s, contraseña=%s WHERE id=%s
            """, (nombre, correo, contraseña, id_usuario))
        conn.commit()

def eliminar_usuario(id_usuario):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM usuarios WHERE id=%s", (id_usuario,))
        conn.commit()

# ============================================================== 
# 🔧 INICIALIZACIÓN DE LA BD Y ADMIN
# ============================================================== 
try:
    crear_tabla()
except Exception as e:
    print("⚠️ Error al crear tabla:", e)

try:
    if not obtener_usuario("andresfelipeaguasaco@gmail.com"):
        agregar_usuario("Administrador", "andresfelipeaguasaco@gmail.com", "123456789")
        print("👤 Usuario administrador creado.")
except Exception as e:
    print("⚠️ Error creando admin:", e)

# ============================================================== 
# 🌐 RUTAS PRINCIPALES
# ============================================================== 
@app.route('/')
def root():
    if "usuario" in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template('home.html', usuario=session['usuario'])

# ============================================================== 
# 🔐 LOGIN TRADICIONAL
# ============================================================== 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        usuario = obtener_usuario(correo)
        if usuario and usuario[3] == contraseña:
            session['usuario'] = usuario[1]
            session['correo'] = usuario[2]
            return redirect(url_for('home'))
        else:
            return "❌ Usuario o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a>"
    return render_template('login.html')

# ============================================================== 
# 🧠 LOGIN FACIAL (para iniciar sesión con cámara)
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
        return jsonify({"success": False, "error": "No se detectó rostro"}), 400

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT nombre, correo, rostro FROM usuarios WHERE rostro IS NOT NULL")
                filas = cursor.fetchall()

        for nombre, correo, rostro_guardado in filas:
            if rostro_guardado:
                embedding_guardado = np.frombuffer(rostro_guardado, dtype=np.float32)
                if comparar_embeddings(embedding_guardado, embedding_actual):
                    session["usuario"] = nombre
                    session["correo"] = correo
                    print(f"✅ Rostro reconocido: {nombre}")
                    return jsonify({"success": True, "usuario": nombre})

        return jsonify({"success": False, "error": "Rostro no reconocido"}), 401

    except Exception as e:
        print("❌ Error en login facial:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================== 
# 🆔 RUTA NUEVA: registro_rostro_nav
# ============================================================== 
# Si el usuario ya está logueado (session['correo']), lo llevamos a la página
# para registrar/gestionar su rostro. Si NO está logueado, lo llevamos a la
# página de login facial para que pueda iniciar sesión con la cámara.
@app.route('/registro_rostro_nav')
def registro_rostro_nav():
    if session.get("correo"):
        # Usuario logueado -> abrir la UI de registro/gestión de rostro
        return redirect(url_for('registro_rostro'))
    else:
        # No logueado -> abrir la UI de login facial (para iniciar sesión por rostro)
        return redirect(url_for('login_face_page'))

# ============================================================== 
# 🧾 REGISTRO DE USUARIOS
# ============================================================== 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if data:  # registro facial
            nombre = data.get("nombre")
            correo = data.get("correo")
            contraseña = data.get("contraseña")
            rostro_base64 = data.get("rostro")
            try:
                rostro_embedding = obtener_embedding(rostro_base64) if rostro_base64 else None
                agregar_usuario(nombre, correo, contraseña, rostro_embedding)
                return jsonify({"success": True, "mensaje": "Usuario registrado con éxito"})
            except psycopg.errors.UniqueViolation:
                return jsonify({"success": False, "error": "Correo ya registrado"}), 400
            except Exception as e:
                print("❌ Error al registrar usuario facial:", e)
                return jsonify({"success": False, "error": str(e)}), 500
        else:  # registro tradicional
            nombre = request.form['nombre']
            correo = request.form['correo']
            contraseña = request.form['contraseña']
            try:
                agregar_usuario(nombre, correo, contraseña)
                return redirect(url_for('login'))
            except Exception:
                return "⚠️ Este correo ya está registrado. <a href='/register'>Intenta con otro</a>"
    return render_template('register.html')

# ============================================================== 
# 🧩 FUNCIONALIDADES ADICIONALES
# ============================================================== 
@app.route('/calculadora')
def calculadora():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template("calculadora.html", usuario=session['usuario'])

@app.route('/recomendaciones')
def recomendaciones():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template("recomendaciones.html")

@app.route('/rutinas')
def rutinas():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template("rutinas.html", usuario=session["usuario"])

@app.route("/registro_rostro")
def registro_rostro():
    # Página donde el usuario logueado puede capturar y registrar/actualizar su rostro
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("registro_rostro.html", usuario=session["usuario"])

# ============================================================== 
# 📸 API PARA REGISTRAR ROSTRO
# ============================================================== 
@app.route("/api/registrar_rostro", methods=["POST"])
def api_registrar_rostro():
    if "correo" not in session:
        return jsonify({"success": False, "error": "No hay sesión activa"}), 403

    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "No se recibió la imagen"}), 400

    try:
        rostro_embedding = obtener_embedding(data["imagen"])
        if rostro_embedding is None:
            return jsonify({"success": False, "error": "No se detectó rostro"}), 400

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE usuarios SET rostro = %s WHERE correo = %s
                """, (psycopg.Binary(rostro_embedding.tobytes()), session["correo"]))
            conn.commit()

        return jsonify({"success": True, "mensaje": "Rostro registrado con éxito"})

    except Exception as e:
        print("❌ Error al registrar rostro:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================== 
# 🔐 PANEL ADMIN
# ============================================================== 
ADMIN_EMAIL = "andresfelipeaguasaco@gmail.com"

@app.route('/admin/usuarios')
def admin_usuarios():
    if "correo" not in session or session["correo"] != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    usuarios = obtener_todos_usuarios()
    return render_template("admin_usuarios.html", usuarios=usuarios)

@app.route('/admin/modificar/<int:id_usuario>', methods=['GET', 'POST'])
def admin_modificar(id_usuario):
    if "correo" not in session or session["correo"] != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        modificar_usuario(id_usuario, nombre, correo, contraseña)
        return redirect(url_for('admin_usuarios'))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id_usuario,))
            usuario = cursor.fetchone()
    return render_template("admin_modificar.html", usuario=usuario)

@app.route('/admin/eliminar/<int:id_usuario>')
def admin_eliminar(id_usuario):
    if "correo" not in session or session["correo"] != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    eliminar_usuario(id_usuario)
    return redirect(url_for('admin_usuarios'))

# ============================================================== 
# 🚪 LOGOUT Y HEALTHCHECK
# ============================================================== 
@app.route('/logout')
def logout():
    session.pop("usuario", None)
    session.pop("correo", None)
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return {"status": "ok"}, 200

# ============================================================== 
# 🗜️ CONTEXT PROCESSOR PARA INYECTAR VARIABLES GLOBALES
# ============================================================== 
@app.context_processor
def inject_global_vars():
    return dict(ADMIN_EMAIL=ADMIN_EMAIL, session=session)

# ============================================================== 
# 🚀 MAIN
# ============================================================== 
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)