from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(20), default="guest")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Programa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    archivo = db.Column(db.String(200), unique=True, nullable=False)
    descripcion = db.Column(db.String(300), default="")

class LicenseRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hwid = db.Column(db.String(100), nullable=False)
    program_code = db.Column(db.String(50), nullable=False)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hwid = db.Column(db.String(100), nullable=False)
    program_code = db.Column(db.String(50), nullable=False)
    license_key = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=False)
    last_seen_at = db.Column(db.DateTime)