import os
import psycopg
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
# ❌ Eliminado: from facial_utils import obtener_embedding, comparar_embeddings

# 🔥 Carga las variables del archivo .env al entorno
from dotenv import load_dotenv
load_dotenv() 

# ==============================================================
# ⚙️ CONFIGURACIÓN GLOBAL (DEEPFACE - ELIMINADA)
# ==============================================================
# ❌ Eliminadas todas las variables de entorno de DeepFace
# os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# os.environ["DETECTOR_BACKEND"] = "retinaface"
# os.environ["BACKEND"] = "torch"
# os.environ["DISABLE_TF"] = "1"
# os.environ["FORCE_RELOAD_BACKENDS"] = "1"

# ❌ Eliminado: print("🧠 DeepFace optimizado para PyTorch + RetinaFace")

# ==============================================================
# ⚙️ CONFIGURACIÓN FLASK
# ==============================================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# ==============================================================
# 🗄️ CONEXIÓN A LA BASE DE DATOS (psycopg moderno)
# ==============================================================

def get_connection():
    """
    Crea una conexión PostgreSQL. Prioriza DATABASE_URL (Render), 
    y añade el parámetro sslmode=require si no está en la URL.
    """
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        try:
            # Añadimos 'sslmode=require' si no está explícito en la URL de Render.
            if 'sslmode' not in db_url.lower():
                db_url += '?sslmode=require'
            
            return psycopg.connect(db_url)
        except Exception as e:
            # Si falla la conexión remota, mostramos el error y lanzamos la excepción.
            print("❌ Error al conectar con DATABASE_URL (Render):", e)
            raise 

    # 🔹 Fallback local (si DATABASE_URL no está definida)
    try:
        print("⚠️ DATABASE_URL no definida. Intentando conectar localmente...")
        return psycopg.connect(
            dbname=os.getenv("DB_NAME", "fitness"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "tu_clave"), # ⚠️ Cambia por tu contraseña
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
    except Exception as e:
        print("❌ No se pudo conectar a PostgreSQL local:", e)
        raise

# ==============================================================
# 🧾 FUNCIONES DE BASE DE DATOS
# ==============================================================
def crear_tabla():
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # La columna 'rostro BYTEA' se mantiene en la tabla por ahora,
                # pero ya no se usará. Se puede eliminar después de limpiar datos.
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

def agregar_usuario(nombre, correo, contraseña): # 💡 Se eliminó el parámetro 'rostro=None'
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # 💡 Se eliminó la lógica de insertar el rostro. Ahora solo se registran datos básicos.
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
# 🔧 INICIALIZACIÓN
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
# ❌ LOGIN FACIAL (ELIMINADO)
# ==============================================================
# ❌ Eliminada la ruta /login_face (GET y POST)

# ==============================================================
# 🧾 REGISTRO DE USUARIOS
# ==============================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 💡 Se eliminó la lógica de registro facial (if data:...)
        
        # registro tradicional
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

# ❌ Eliminada la ruta /registro_rostro
# @app.route("/registro_rostro")
# def registro_rostro():
#     if "usuario" not in session:
#         return redirect(url_for("login"))
#     return render_template("registro_rostro.html", usuario=session["usuario"])


# ==============================================================
# ❌ API PARA REGISTRAR ROSTRO (ELIMINADA)
# ==============================================================
# ❌ Eliminada la ruta /api/registrar_rostro

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
# 🚀 MAIN
# ==============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)