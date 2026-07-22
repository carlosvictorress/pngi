from flask import Blueprint, render_template
from app.models import Municipio

# Instancia o blueprint público mestre para a raiz absoluta
publico_bp = Blueprint('publico', __name__)

@publico_bp.route('/')
def landing_page():
    """Renderiza a Landing Page institucional mestre na raiz absoluta do SaaS."""
    municipios = Municipio.query.order_by(Municipio.nome).all()
    return render_template('publico/landing.html', municipios=municipios)