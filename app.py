from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
from config import Config
from models import db, Usuario, Programa, LicenseRequest, License
from functools import wraps
import os
import secrets
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

PROGRAMAS_FOLDER = os.path.join(os.path.dirname(__file__), "programas")
os.makedirs(PROGRAMAS_FOLDER, exist_ok=True)

# ------------------ INICIALIZACIÓN ------------------
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(usuario="KokuGod").first():
        admin = Usuario(usuario="KokuGod", rol="admin")
        admin.set_password("250310")  # ⚠️ Cambiar por una contraseña segura
        db.session.add(admin)
        db.session.commit()

# ------------------ DECORADORES ------------------
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

# ------------------ RUTAS PÚBLICAS ------------------
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
    return send_from_directory(PROGRAMAS_FOLDER, prog.archivo, as_attachment=True)

# ------------------ LOGIN / REGISTER ------------------
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

# ------------------ PANEL ADMIN ------------------
@app.route("/admin")
@admin_requerido
def admin():
    usuarios = Usuario.query.all()
    return render_template("admin.html", usuarios=usuarios, usuario=session.get("usuario"))

# ADMIN PROGRAMAS
@app.route("/admin/programas")
@admin_requerido
def admin_programas():
    programas_db = Programa.query.all()
    archivos = sorted([f for f in os.listdir(PROGRAMAS_FOLDER) if os.path.isfile(os.path.join(PROGRAMAS_FOLDER, f))])
    archivos_en_db = {p.archivo for p in programas_db}
    archivos_no_indexados = [f for f in archivos if f not in archivos_en_db]
    return render_template("admin_programas.html", programas=programas_db, archivos_no_indexados=archivos_no_indexados, usuario=session.get("usuario"))

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
    if Programa.query.filter_by(archivo=archivo).first():
        flash("El archivo ya está indexado.", "error")
        return redirect(url_for("admin_programas"))
    nuevo = Programa(nombre=nombre, descripcion=descripcion, archivo=archivo)
    db.session.add(nuevo)
    db.session.commit()
    flash(f"Programa '{nombre}' agregado.", "success")
    return redirect(url_for("admin_programas"))

@app.route("/admin/programas/eliminar/<int:id>", methods=["POST"])
@admin_requerido
def eliminar_programa(id):
    p = Programa.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash(f"Programa '{p.nombre}' eliminado de la base.", "success")
    return redirect(url_for("admin_programas"))

# ------------------ API LICENCIAS ------------------
@app.route("/api/ping", methods=["POST"])
def api_ping():
    data = request.get_json(force=True)
    hwid = data.get("hwid")
    program_code = data.get("program_code")
    if not hwid or not program_code:
        return jsonify({"authorized": False, "reason": "missing_parameters"}), 400

    lic = License.query.filter_by(hwid=hwid, program_code=program_code, active=True).first()
    if lic:
        lic.last_seen_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"authorized": bool(lic)}), 200

@app.route("/api/request_activation", methods=["POST"])
def api_request_activation():
    data = request.get_json(force=True)
    hwid = data.get("hwid")
    program_code = data.get("program_code")
    note = data.get("note", "")
    if not hwid or not program_code:
        return jsonify({"ok": False, "reason": "missing_parameters"}), 400

    req = LicenseRequest(hwid=hwid, program_code=program_code, note=note)
    db.session.add(req)
    db.session.commit()
    return jsonify({"ok": True, "message": "request_received"}), 200

# ------------------ ADMIN LICENCIAS ------------------
@app.route("/admin/licencias")
@admin_requerido
def admin_licencias():
    licenses = License.query.order_by(License.id.desc()).all()
    requests = LicenseRequest.query.order_by(LicenseRequest.id.desc()).all()
    return render_template("admin_licencia.html", licenses=licenses, requests=requests, usuario=session.get("usuario"))

@app.route("/admin/licencias/requests_json")
@admin_requerido
def requests_json():
    requests = LicenseRequest.query.order_by(LicenseRequest.id.desc()).all()
    return jsonify([{
        'id': r.id,
        'hwid': r.hwid,
        'program_code': r.program_code,
        'created_at': r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        'note': r.note
    } for r in requests])

@app.route("/admin/licencias/licenses_json")
@admin_requerido
def licenses_json():
    licenses = License.query.order_by(License.id.desc()).all()
    return jsonify([{
        'id': l.id,
        'hwid': l.hwid,
        'program_code': l.program_code,
        'license_key': l.license_key,
        'active': l.active,
        'last_seen_at': l.last_seen_at.strftime("%Y-%m-%d %H:%M:%S") if l.last_seen_at else None
    } for l in licenses])

@app.route("/admin/licencias/crear", methods=["POST"])
@admin_requerido
def admin_create_license():
    hwid = request.form.get("hwid")
    program_code = request.form.get("program_code")
    if not hwid or not program_code:
        flash("HWID y Program code son requeridos.", "error")
        return redirect(url_for("admin_licencias"))
    license_key = secrets.token_hex(16)
    nueva = License(hwid=hwid, program_code=program_code, license_key=license_key, active=True)
    db.session.add(nueva)
    db.session.commit()
    flash(f"Licencia creada para HWID {hwid}.", "success")
    return redirect(url_for("admin_licencias"))

@app.route("/admin/licencias/aprobar/<int:req_id>", methods=["POST"])
@admin_requerido
def admin_approve_request(req_id):
    req = LicenseRequest.query.get_or_404(req_id)
    license_key = secrets.token_hex(16)
    nueva = License(hwid=req.hwid, program_code=req.program_code, license_key=license_key, active=True)
    db.session.add(nueva)
    db.session.delete(req)
    db.session.commit()
    flash(f"Solicitud ID {req.id} aprobada y licencia creada.", "success")
    return redirect(url_for("admin_licencias"))

@app.route("/admin/licencias/eliminar_request/<int:id>", methods=["POST"])
@admin_requerido
def admin_delete_request(id):
    req = LicenseRequest.query.get_or_404(id)
    db.session.delete(req)
    db.session.commit()
    flash(f"Solicitud ID {id} eliminada.", "success")
    return redirect(url_for("admin_licencias"))

@app.route("/admin/licencias/activar/<int:id>", methods=["POST"])
@admin_requerido
def admin_activate_license(id):
    lic = License.query.get_or_404(id)
    lic.active = True
    db.session.commit()
    flash(f"Licencia {lic.id} activada.", "success")
    return redirect(url_for("admin_licencias"))

@app.route("/admin/licencias/revocar/<int:id>", methods=["POST"])
@admin_requerido
def admin_revoke_license(id):
    lic = License.query.get_or_404(id)
    lic.active = False
    db.session.commit()
    flash(f"Licencia {lic.id} revocada.", "success")
    return redirect(url_for("admin_licencias"))

@app.route("/admin/licencias/eliminar/<int:id>", methods=["POST"])
@admin_requerido
def admin_delete_license(id):
    lic = License.query.get_or_404(id)
    db.session.delete(lic)
    db.session.commit()
    flash(f"Licencia {lic.id} eliminada.", "success")
    return redirect(url_for("admin_licencias"))

# Descargar DB
@app.route("/admin/licencias/descargar")
@admin_requerido
def admin_download_db():
    db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    return send_from_directory(os.path.dirname(db_path), os.path.basename(db_path), as_attachment=True)

@app.route("/admin/licencias/subir", methods=["GET", "POST"])
@admin_requerido
def admin_upload_db():
    db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    if request.method == "POST":
        file = request.files.get("dbfile")
        if not file:
            return "Error: no se subió ningún archivo.", 400
        if not file.filename.endswith(".db"):
            return "Error: el archivo debe tener extensión .db", 400

        # Backup de la base actual
        backup_path = db_path + ".backup"
        if os.path.exists(db_path):
            os.rename(db_path, backup_path)

        # Guardar la nueva base
        file.save(db_path)
        return f"✅ Base de datos reemplazada correctamente.<br>Backup creado en: {backup_path}"

    # Si es GET, mostramos un formulario HTML básico inline (sin plantilla)
    return """
        <h2>Subir nueva base de datos (.db)</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="dbfile" accept=".db" required>
            <button type="submit">Subir</button>
        </form>
        <p>Se reemplazará la base de datos actual y se creará un backup automáticamente.</p>
    """

# ------------------ EJECUTAR ------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)