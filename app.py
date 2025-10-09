from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, os

app = Flask(__name__)
app.secret_key = "clave_super_segura"

# ----------------- CONFIGURACIÓN BASE DE DATOS -----------------
# Se asegura de que la base esté dentro de 'instance', compatible con Render
os.makedirs(app.instance_path, exist_ok=True)
DB_PATH = os.path.join(app.instance_path, "usuarios.db")

# ----------------- FUNCIONES DE BD -----------------
def crear_tabla():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            contraseña TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def agregar_usuario(nombre, correo, contraseña):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (nombre, correo, contraseña) VALUES (?, ?, ?)",
                       (nombre, correo, contraseña))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False  # Correo duplicado
    conn.close()
    return True

def obtener_usuario(correo):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE correo = ?", (correo,))
    usuario = cursor.fetchone()
    conn.close()
    return usuario

def obtener_todos_usuarios():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def modificar_usuario(id_usuario, nombre, correo, contraseña):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE usuarios 
        SET nombre = ?, correo = ?, contraseña = ?
        WHERE id = ?
    """, (nombre, correo, contraseña, id_usuario))
    conn.commit()
    conn.close()

def eliminar_usuario(id_usuario):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = ?", (id_usuario,))
    conn.commit()
    conn.close()

# Crear tabla si no existe
crear_tabla()

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
        if usuario and usuario[3] == contraseña:  # usuario[3] = contraseña
            session['usuario'] = usuario[1]       # usuario[1] = nombre
            session['correo'] = usuario[2]        # usuario[2] = correo
            return redirect(url_for('home'))
        else:
            return "❌ Usuario o contraseña incorrectos. <a href='/login'>Intentar de nuevo</a>"
    return render_template('login.html')

# ----------------- REGISTER -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']

        if not agregar_usuario(nombre, correo, contraseña):
            return "⚠️ Este correo ya está registrado. <a href='/register'>Intenta con otro</a>"

        return redirect(url_for('login'))
    return render_template('register.html')

# ----------------- CALCULADORA -----------------
@app.route('/calculadora')
def calculadora():
    if "usuario" not in session:
        return redirect(url_for('login'))
    return render_template("calculadora.html", usuario=session['usuario'])

# ----------------- PANEL ADMIN (SOLO PARA TI) -----------------
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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE id = ?", (id_usuario,))
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
# Esto es importante para Render
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))