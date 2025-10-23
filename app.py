from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2, os
from urllib.parse import urlparse
import psycopg2.extras

# Importar utilidades faciales (asegúrate de tener facial_utils.py en la misma carpeta)
from facial_utils import obtener_embedding, comparar_embeddings

app = Flask(__name__)
app.secret_key = "clave_super_segura"

# ----------------- CONEXIÓN A POSTGRES -----------------
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# ----------------- FUNCIONES DE BD -----------------
def crear_tabla():
    conn = get_connection()
    cursor = conn.cursor()
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
    conn.close()

def agregar_usuario(nombre, correo, contraseña):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)",
                       (nombre, correo, contraseña))
        conn.commit()
    except psycopg2.Error:
        conn.close()
        return False
    conn.close()
    return True

def obtener_usuario(correo):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
    usuario = cursor.fetchone()
    conn.close()
    return usuario

def obtener_todos_usuarios():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def modificar_usuario(id_usuario, nombre, correo, contraseña):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE usuarios 
        SET nombre = %s, correo = %s, contraseña = %s
        WHERE id = %s
    """, (nombre, correo, contraseña, id_usuario))
    conn.commit()
    conn.close()

def eliminar_usuario(id_usuario):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = %s", (id_usuario,))
    conn.commit()
    conn.close()

# Crear tabla si no existe
try:
    crear_tabla()
except Exception as e:
    print("⚠️ Error al crear la tabla:", e)

# Crear usuario admin si no existe
if not obtener_usuario("andresfelipeaguasaco@gmail.com"):
    agregar_usuario("Administrador", "andresfelipeaguasaco@gmail.com", "123456789")

# ----------------- ROOT -----------------
@app.route('/')
def root():
    if "usuario" in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

# ----------------- HOME -----------------
@app.route('/home')
def home():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template('home.html', usuario=session['usuario'])

# ----------------- LOGIN -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        usuario = obtener_usuario(correo)
        # usuario: (id, nombre, correo, contraseña, rostro)
        if usuario and usuario[3] == contraseña:
            session['usuario'] = usuario[1]
            session['correo'] = usuario[2]
            return redirect(url_for('home'))
        else:
            return "❌ Usuario o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a>"
    return render_template('login.html')

# ----------------- LOGIN FACIAL -----------------
@app.route('/login_facial', methods=['POST'])
def login_facial():
    imagen = request.form.get('imagen')
    if not imagen:
        return "⚠️ No se envió imagen", 400

    embedding_actual = obtener_embedding(imagen)
    if embedding_actual is None:
        return "⚠️ No se detectó un rostro válido.", 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Traer solo usuarios con rostro no nulo
        cursor.execute("SELECT nombre, correo, rostro FROM usuarios WHERE rostro IS NOT NULL")
        filas = cursor.fetchall()
        conn.close()

        for nombre, correo, rostro_guardado in filas:
            if rostro_guardado is None:
                continue
            try:
                if comparar_embeddings(rostro_guardado, embedding_actual):
                    session['usuario'] = nombre
                    session['correo'] = correo
                    return "✅ OK"
            except Exception as e:
                print("Error comparando embeddings:", e)
                continue

        return "🚫 Rostro no reconocido.", 401
    except Exception as e:
        print("Error login_facial:", e)
        return "❌ Error interno", 500

# ----------------- REGISTER -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        rostro_base64 = request.form.get('rostro')  # campo oculto del form (dataURL)

        rostro_embedding = None
        if rostro_base64:
            rostro_embedding = obtener_embedding(rostro_base64)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            if rostro_embedding is not None:
                cursor.execute(
                    "INSERT INTO usuarios (nombre, correo, contraseña, rostro) VALUES (%s, %s, %s, %s)",
                    (nombre, correo, contraseña, psycopg2.Binary(rostro_embedding))
                )
            else:
                cursor.execute(
                    "INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)",
                    (nombre, correo, contraseña)
                )
            conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            conn.close()
            # Si es error por duplicado
            if getattr(e, 'pgcode', None) == '23505':
                return "⚠️ Este correo ya está registrado. <a href='/register'>Intenta con otro</a>"
            print("Error al insertar usuario:", e)
            return f"⚠️ Error al registrar usuario: {e}"
        finally:
            try:
                conn.close()
            except:
                pass

        return redirect(url_for('login'))
    return render_template('register.html')

# ----------------- CALCULADORA -----------------
@app.route('/calculadora')
def calculadora():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template("calculadora.html", usuario=session['usuario'])

# ----------------- RECOMENDACIONES -----------------
@app.route('/recomendaciones')
def recomendaciones():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template("recomendaciones.html")

# ----------------- RUTINAS -----------------
@app.route('/rutinas')
def rutinas():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template("rutinas.html", usuario=session["usuario"])


# ----------------- PANEL ADMIN -----------------
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

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id_usuario,))
    usuario = cursor.fetchone()
    conn.close()
    return render_template("admin_modificar.html", usuario=usuario)

@app.route('/admin/eliminar/<int:id_usuario>')
def admin_eliminar(id_usuario):
    if "correo" not in session or session["correo"] != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    eliminar_usuario(id_usuario)
    return redirect(url_for('admin_usuarios'))

# ----------------- LOGOUT -----------------
@app.route('/logout')
def logout():
    session.pop("usuario", None)
    session.pop("correo", None)
    return redirect(url_for('login'))

# ----------------- MAIN -----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
