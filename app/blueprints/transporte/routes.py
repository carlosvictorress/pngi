from flask import Blueprint

transporte_bp = Blueprint('transporte', __name__)

@transporte_bp.route('/')
def home():
    return "Gestão de Transporte"