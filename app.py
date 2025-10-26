from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2, os
import numpy as np

# Importar utilidades faciales optimizadas
from facial_utils import obtener_embedding, comparar_embeddings

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_super_segura")

# ----------------- CONEXIÓN A POSTGRES -----------------
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Conecta a la base de datos PostgreSQL de forma segura."""
    return psycopg2.connect(DATABASE_URL, sslmode="require")

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
    cursor.close()
    conn.close()

def agregar_usuario(nombre, correo, contraseña):
    """Agrega un usuario nuevo sin rostro (por defecto)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)",
            (nombre, correo, contraseña)
        )
        conn.commit()
        return True
    except psycopg2.Error as e:
        print("⚠️ Error al agregar usuario:", e)
        return False
    finally:
        if conn:
            conn.close()

def obtener_usuario(correo):
    """Obtiene un usuario por su correo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()
    return usuario

def obtener_todos_usuarios():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.close()
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
    cursor.close()
    conn.close()

def eliminar_usuario(id_usuario):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = %s", (id_usuario,))
    conn.commit()
    cursor.close()
    conn.close()

# ----------------- CREACIÓN INICIAL -----------------
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

# ----------------- RUTAS -----------------
@app.route('/')
def root():
    return redirect(url_for('home') if "usuario" in session else url_for('login'))

@app.route('/home')
def home():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template('home.html', usuario=session['usuario'])

# ----------------- LOGIN (Normal) -----------------
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
        return "❌ Usuario o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a>"
    return render_template('login.html')

# ----------------- LOGIN FACIAL -----------------
@app.route('/login_face', methods=['GET'])
def login_face_page():
    return render_template('login_face.html')

@app.route('/login_face', methods=['POST'])
def login_face_post():
    data = request.get_json(silent=True)
    if not data or "imagen" not in data:
        return jsonify({"success": False, "error": "Imagen no recibida"}), 400

    imagen = data["imagen"]
    embedding_actual = obtener_embedding(imagen)
    if embedding_actual is None:
        return jsonify({"success": False, "error": "No se detectó un rostro válido"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, correo, rostro FROM usuarios WHERE rostro IS NOT NULL")
        filas = cursor.fetchall()
        cursor.close()
        conn.close()

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
        print("❌ Error en login_face POST:", e)
        return jsonify({"success": False, "error": "Error interno"}), 500

# ----------------- REGISTER -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        rostro_base64 = request.form.get('rostro')

        rostro_embedding = obtener_embedding(rostro_base64) if rostro_base64 else None

        try:
            conn = get_connection()
            cursor = conn.cursor()
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
            conn.rollback()
            return "⚠️ Este correo ya está registrado. <a href='/register'>Intenta con otro</a>"
        except Exception as e:
            print("❌ Error al registrar usuario:", e)
            return f"⚠️ Error al registrar usuario: {e}"
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('login'))
    return render_template('register.html')

# ----------------- FUNCIONALIDADES ADICIONALES -----------------
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

@app.route('/registro_rostro')
def registro_rostro():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template('registro_rostro.html', usuario=session["usuario"])

@app.route('/guardar_rostro', methods=['POST'])
def guardar_rostro():
    data = request.get_json(silent=True)
    if not data:
        return {"success": False, "error": "No se envió JSON"}

    imagen = data.get("imagen")
    correo = session.get("correo")

    if not imagen or not correo:
        return {"success": False, "error": "Datos incompletos"}

    try:
        embedding = obtener_embedding(imagen)
        if embedding is None:
            return {"success": False, "error": "No se detectó rostro válido"}

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET rostro = %s WHERE correo = %s",
                       (psycopg2.Binary(embedding.tobytes()), correo))
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True}
    except Exception as e:
        print("❌ Error al guardar rostro:", e)
        return {"success": False, "error": str(e)}

# ----------------- ADMIN -----------------
ADMIN_EMAIL = "andresfelipeaguasaco@gmail.com"

@app.route('/admin/usuarios')
def admin_usuarios():
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    usuarios = obtener_todos_usuarios()
    return render_template("admin_usuarios.html", usuarios=usuarios)

@app.route('/admin/modificar/<int:id_usuario>', methods=['GET', 'POST'])
def admin_modificar(id_usuario):
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado"

    if request.method == 'POST':
        modificar_usuario(
            id_usuario,
            request.form['nombre'],
            request.form['correo'],
            request.form['contraseña']
        )
        return redirect(url_for('admin_usuarios'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (id_usuario,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template("admin_modificar.html", usuario=usuario)

@app.route('/admin/eliminar/<int:id_usuario>')
def admin_eliminar(id_usuario):
    if session.get("correo") != ADMIN_EMAIL:
        return "🚫 Acceso denegado"
    eliminar_usuario(id_usuario)
    return redirect(url_for('admin_usuarios'))

# ----------------- LOGOUT -----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ----------------- MAIN -----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
