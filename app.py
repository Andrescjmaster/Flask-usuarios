from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2, os
import psycopg2.extras
import numpy as np

# Importar utilidades faciales
from facial_utils import obtener_embedding, comparar_embeddings

app = Flask(__name__)
app.secret_key = "clave_super_segura"

# ----------------- CONEXIÓN A POSTGRES -----------------
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    # Espera que DATABASE_URL esté en formato de conexión compatible con psycopg2.
    # En Render, DATABASE_URL suele estar definido como variable de entorno.
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
    cursor.close()
    conn.close()

def agregar_usuario(nombre, correo, contraseña):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)",
                       (nombre, correo, contraseña))
        conn.commit()
    except psycopg2.Error as e:
        # Si falla (por ejemplo duplicado), devolvemos False
        print("Error agregar_usuario:", e)
        conn.rollback()
        cursor.close()
        conn.close()
        return False
    cursor.close()
    conn.close()
    return True

def obtener_usuario(correo):
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

# Crear tabla si no existe
try:
    crear_tabla()
except Exception as e:
    print("⚠️ Error al crear la tabla:", e)

# Crear usuario admin si no existe
try:
    if not obtener_usuario("andresfelipeaguasaco@gmail.com"):
        agregar_usuario("Administrador", "andresfelipeaguasaco@gmail.com", "123456789")
except Exception as e:
    print("⚠️ Error comprobando/creando admin:", e)

# ----------------- RUTAS -----------------
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

# ----------------- LOGIN (normal) -----------------
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

# ----------------- PAGINA: LOGIN FACIAL -----------------
@app.route('/login_face', methods=['GET'])
def login_face_page():
    # muestra la plantilla que abre la cámara y captura
    return render_template('login_face.html')

# ----------------- ENDPOINT: LOGIN FACIAL (POST JSON) -----------------
@app.route('/login_face', methods=['POST'])
def login_face_post():
    """
    Espera JSON: { "imagen": "<dataurl>" }
    Retorna JSON: { "success": True/False, "usuario": nombre OR "error": mensaje }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No se recibió JSON"}), 400

    imagen = data.get("imagen")
    if not imagen:
        return jsonify({"success": False, "error": "No se envió imagen"}), 400

    # Obtener embedding del frame recibido
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

        # comparar con cada rostro guardado
        for nombre, correo, rostro_guardado in filas:
            if rostro_guardado is None:
                continue
            try:
                # reconstruir embedding guardado
                embedding_guardado = np.frombuffer(rostro_guardado, dtype=np.float32)
                if comparar_embeddings(embedding_guardado, embedding_actual):
                    session['usuario'] = nombre
                    session['correo'] = correo
                    return jsonify({"success": True, "usuario": nombre})
            except Exception as e:
                print("Error comparando embeddings:", e)
                continue

        return jsonify({"success": False, "error": "Rostro no reconocido"}), 401

    except Exception as e:
        print("Error en login_face POST:", e)
        return jsonify({"success": False, "error": "Error interno"}), 500

# ----------------- (Compatibilidad) antigua ruta POST si alguna página la usa -----------------
@app.route('/login_facial', methods=['POST'])
def login_facial_compat():
    """
    Compatibilidad con endpoints antiguos que envían form-urlencoded (campo 'imagen').
    Aquí aceptamos tanto form como JSON; delegamos a login_face_post para lógica.
    """
    # si viene multipart/form o form-urlencoded
    imagen = request.form.get('imagen') or request.values.get('imagen')
    if imagen:
        # emular JSON y llamar directamente al handler
        request_json = {"imagen": imagen}
        # Llamamos a la misma lógica reutilizable:
        return login_face_post()
    else:
        # si no vino por form, intentamos JSON
        return login_face_post()

# ----------------- REGISTER -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        rostro_base64 = request.form.get('rostro')  # puede ser None

        rostro_embedding = None
        if rostro_base64:
            # obtener embedding (numpy array)
            rostro_embedding = obtener_embedding(rostro_base64)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            if rostro_embedding is not None:
                # convertir a bytes antes de guardar
                cursor.execute(
                    "INSERT INTO usuarios (nombre, correo, contraseña, rostro) VALUES (%s, %s, %s, %s)",
                    (nombre, correo, contraseña, psycopg2.Binary(rostro_embedding.tobytes()))
                )
            else:
                cursor.execute(
                    "INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)",
                    (nombre, correo, contraseña)
                )
            conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            cursor.close()
            conn.close()
            # Si es error por duplicado
            if getattr(e, 'pgcode', None) == '23505':
                return "⚠️ Este correo ya está registrado. <a href='/register'>Intenta con otro</a>"
            print("Error al insertar usuario:", e)
            return f"⚠️ Error al registrar usuario: {e}"
        finally:
            try:
                cursor.close()
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

# ----------------- REGISTRO FACIAL -----------------
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

        embedding_bytes = embedding.tobytes()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET rostro = %s WHERE correo = %s", (psycopg2.Binary(embedding_bytes), correo))
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True}
    except Exception as e:
        print("Error al guardar rostro:", e)
        return {"success": False, "error": str(e)}

@app.route('/verificar_rostro', methods=['POST'])
def verificar_rostro():
    data = request.get_json(silent=True)
    if not data:
        return {"success": False, "error": "No se envió JSON"}
    imagen = data.get("imagen")
    correo = data.get("correo")

    if not imagen or not correo:
        return {"success": False, "error": "Datos incompletos"}

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, rostro FROM usuarios WHERE correo = %s", (correo,))
        fila = cursor.fetchone()
        cursor.close()
        conn.close()

        if not fila or fila[1] is None:
            return {"success": False, "error": "No hay rostro registrado"}

        nombre, rostro_guardado = fila
        embedding_guardado = np.frombuffer(rostro_guardado, dtype=np.float32)
        embedding_actual = obtener_embedding(imagen)

        if embedding_actual is None:
            return {"success": False, "error": "No se detectó rostro válido"}

        if comparar_embeddings(embedding_actual, embedding_guardado):
            session["usuario"] = nombre
            session["correo"] = correo
            return {"success": True}
        else:
            return {"success": False, "error": "Rostro no coincide"}
    except Exception as e:
        print("Error en verificar_rostro:", e)
        return {"success": False, "error": str(e)}

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
    cursor.close()
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
