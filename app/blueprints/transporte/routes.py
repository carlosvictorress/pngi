from flask import Blueprint, render_template, g, abort
from flask_login import login_required
from app.models import Municipio, Aluno, TransporteAlunado

transporte_bp = Blueprint('transporte', __name__)

@transporte_bp.url_value_preprocessor
def get_municipio_slug(endpoint, values):
    """Captura o <municipio_slug> da URL e o injeta no contexto global 'g'."""
    if values and 'municipio_slug' in values:
        g.municipio = Municipio.query.filter_by(slug=values.pop('municipio_slug')).first()
    if not g.municipio:
        abort(404)

@transporte_bp.route('/')
@login_required
def home():
    """Painel principal do transporte escolar inclusivo."""
    alunos_transporte = Aluno.query.join(TransporteAlunado).filter(Aluno.municipio_id == g.municipio.id).all()
    return render_template('publico/dashboard_municipio.html', municipio=g.municipio, total_alunos=len(alunos_transporte))