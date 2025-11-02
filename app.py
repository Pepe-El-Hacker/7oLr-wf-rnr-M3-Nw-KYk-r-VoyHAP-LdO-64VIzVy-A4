from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from config import Config
from models import db, Usuario, Programa
from functools import wraps
import os

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Carpeta donde estarían los archivos que subís al repo (commiteás)
PROGRAMAS_FOLDER = os.path.join(os.path.dirname(__file__), "programas")
os.makedirs(PROGRAMAS_FOLDER, exist_ok=True)

# Crear DB y usuario admin por defecto si no existen
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(usuario="admin").first():
        admin = Usuario(usuario="KokuGod", rol="admin")
        admin.set_password("250310")  # ⚠️ CAMBIALA por una segura
        db.session.add(admin)
        db.session.commit()

# Decoradores
def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorador

def admin_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if session.get("rol") != "admin":
            return "No tenés permisos para acceder aquí.", 403
        return f(*args, **kwargs)
    return decorador

# Rutas públicas
@app.route("/")
def index():
    return render_template("index.html", usuario=session.get("usuario"))

@app.route("/programas")
def programas():
    lista = Programa.query.all()
    return render_template("programas.html", programas=lista, usuario=session.get("usuario"))

@app.route("/descargar/<int:id>")
@login_requerido
def descargar(id):
    prog = Programa.query.get_or_404(id)
    # Enviamos el archivo desde la carpeta /programas
    return send_from_directory(PROGRAMAS_FOLDER, prog.archivo, as_attachment=True)

# Autenticación
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        password = request.form["password"]
        u = Usuario.query.filter_by(usuario=usuario).first()
        if u and u.check_password(password):
            session["usuario"] = u.usuario
            session["rol"] = u.rol
            flash("Sesión iniciada.", "success")
            return redirect(url_for("index"))
        return render_template("login.html", error="Usuario o contraseña incorrectos.")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        password = request.form["password"]
        if not usuario or not password:
            return render_template("register.html", error="Completa usuario y contraseña.")
        if Usuario.query.filter_by(usuario=usuario).first():
            return render_template("register.html", error="El usuario ya existe.")
        nuevo = Usuario(usuario=usuario)
        nuevo.set_password(password)
        db.session.add(nuevo)
        db.session.commit()
        flash("Cuenta creada. Iniciá sesión.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("index"))

# Panel admin general
@app.route("/admin")
@admin_requerido
def admin():
    usuarios = Usuario.query.all()
    return render_template("admin.html", usuarios=usuarios, usuario=session.get("usuario"))

# Panel para gestionar programas: lista DB + archivos físicos no indexados
@app.route("/admin/programas")
@admin_requerido
def admin_programas():
    programas_db = Programa.query.all()
    archivos = sorted([f for f in os.listdir(PROGRAMAS_FOLDER) if os.path.isfile(os.path.join(PROGRAMAS_FOLDER, f))])
    archivos_en_db = {p.archivo for p in programas_db}
    archivos_no_indexados = [f for f in archivos if f not in archivos_en_db]
    return render_template("admin_programas.html", programas=programas_db, archivos_no_indexados=archivos_no_indexados, usuario=session.get("usuario"))

# Agregar a la base un archivo que ya esté en /programas (no sube archivo)
@app.route("/admin/programas/agregar", methods=["POST"])
@admin_requerido
def agregar_programa():
    archivo = request.form.get("archivo")
    nombre = request.form.get("nombre") or archivo
    descripcion = request.form.get("descripcion") or ""
    if not archivo:
        flash("No se indicó archivo.", "error")
        return redirect(url_for("admin_programas"))
    ruta = os.path.join(PROGRAMAS_FOLDER, archivo)
    if not os.path.exists(ruta):
        flash("El archivo no existe en la carpeta programas.", "error")
        return redirect(url_for("admin_programas"))
    # Evitar duplicados en DB
    if Programa.query.filter_by(archivo=archivo).first():
        flash("El archivo ya está indexado.", "error")
        return redirect(url_for("admin_programas"))
    nuevo = Programa(nombre=nombre, descripcion=descripcion, archivo=archivo)
    db.session.add(nuevo)
    db.session.commit()
    flash(f"Programa '{nombre}' agregado.", "success")
    return redirect(url_for("admin_programas"))

# Eliminar entrada de DB (no borra el archivo físico)
@app.route("/admin/programas/eliminar/<int:id>", methods=["POST"])
@admin_requerido
def eliminar_programa(id):
    p = Programa.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash(f"Programa '{p.nombre}' eliminado de la base.", "success")
    return redirect(url_for("admin_programas"))

if __name__ == "__main__":
    # Para desarrollo local
    app.run(debug=True)