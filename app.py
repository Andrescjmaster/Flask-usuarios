import os
import psycopg
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
load_dotenv()

# ==============================================================
#⚙️ CONFIGURACIÓN FLASK
# ==============================================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# ==============================================================
# 🗄️ CONEXIÓN A LA BASE DE DATOS DE RENDER
# ==============================================================
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL no está definida en el entorno.")
    try:
        conn = psycopg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print("❌ Error de conexión a PostgreSQL:", e)
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
                        contraseña VARCHAR(100) NOT NULL
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

def agregar_usuario(nombre, correo, contraseña):
    with get_connection() as conn:
        with conn.cursor() as cursor:
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
ADMIN_EMAIL = "andresfelipeaguasaco@gmail.com"

@app.route('/')
def root():
    # Redirige siempre a home.
    return redirect(url_for('home'))

@app.route('/home')
def home():
    # Permite el acceso sin sesión.
    return render_template('home.html', usuario=session.get('usuario'))

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
            return render_template('login.html', error="Usuario o contraseña incorrectos.")
    return render_template('login.html')

# ==============================================================
# 🧾 REGISTRO DE USUARIOS
# ==============================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        try:
            agregar_usuario(nombre, correo, contraseña)
            return redirect(url_for('login'))
        except Exception:
            return render_template('register.html', error="Este correo ya está registrado. Intenta con otro.")
    return render_template('register.html')

# ==============================================================
# 🧩 FUNCIONALIDADES ADICIONALES (Protegidas)
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

# ==============================================================
# 🔐 PANEL ADMIN (Protegido)
# ==============================================================
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
    return redirect(url_for('home'))

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