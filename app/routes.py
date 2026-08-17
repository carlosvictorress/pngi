from flask import Blueprint, render_template, send_from_directory, current_app, request, jsonify
from app.models import Municipio

# Instancia o blueprint público mestre para a raiz absoluta
publico_bp = Blueprint('publico', __name__)

@publico_bp.route('/')
def landing_page():
    """Renderiza a Landing Page institucional mestre na raiz absoluta do SaaS."""
    municipios = Municipio.query.order_by(Municipio.nome).all()
    return render_template('publico/landing.html', municipios=municipios)

@publico_bp.route('/solicitar-implantacao', methods=['POST'])
def solicitar_implantacao():
    """Recebe e registra a solicitação de implantação do município."""
    data = request.get_json() or request.form
    # Retorna confirmação de recebimento para o front-end
    return jsonify({
        'status': 'sucesso',
        'mensagem': 'O município deu o primeiro passo para uma gestão inclusiva e transparente.'
    })

@publico_bp.route('/manifest.json')
def manifest():
    """Serve o manifesto PWA na raiz absoluta."""
    return send_from_directory(current_app.static_folder, 'manifest.json', mimetype='application/json')

@publico_bp.route('/sw.js')
def service_worker():
    """Serve o Service Worker PWA na raiz absoluta."""
    return send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')