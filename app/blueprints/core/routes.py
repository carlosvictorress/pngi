from flask import Blueprint, render_template, request, redirect, url_for, g, abort
from flask_login import login_required, current_user
from app.models import Municipio, Aluno 

core_bp = Blueprint('core', __name__)

@core_bp.before_app_request
def carregar_contexto_municipio():
    """Garante o carregamento correto do município no contexto global 'g' para Multitenancy."""
    # Ignora arquivos estáticos e rotas globais de autenticação administrativa
    if request.path.startswith('/static/') or request.path.startswith('/auth/login-admin-global') or request.path.startswith('/auth/admin-global'):
        return

    # Extrai o slug do município direto da URL (primeira parte da rota)
    parts = request.path.strip('/').split('/')
    slug_da_url = parts[0] if parts else None

    if not slug_da_url:
        return

    # BUSCA O MUNICÍPIO NO BANCO
    municipio = Municipio.query.filter_by(slug=slug_da_url).first()
    
    if municipio:
        g.municipio = municipio
        g.municipio_slug = municipio.slug
    else:
        if not request.path.startswith('/auth/'):
            abort(404, description="Município não cadastrado na plataforma.")
        return

    # CONTROLE DE ACESSO INTEGRADO (Bypass do SuperAdmin)
    if current_user.is_authenticated:
        if current_user.perfil == 'superadmin':
            return 
            
        if current_user.municipio_id != g.municipio.id:
            abort(403, description="Acesso negado: Você não pertence a esta instância municipal.")

# -------------------------------------------------------------------------
# INDEX / DASHBOARD DO MUNICÍPIO INDIVIDUAL (CORRIGIDO)
# -------------------------------------------------------------------------
@core_bp.route('/dashboard')
@login_required
def index(municipio_slug=None):
    """Dashboard principal isolada de cada prefeitura."""
    if not g.municipio:
        abort(404)

    # Coleta indicadores específicos APENAS desta cidade
    total_alunos = Aluno.query.filter_by(municipio_id=g.municipio.id).count()

    # Definimos um caminho real e limpo para o template
    return render_template(
        'publico/dashboard_municipio.html', 
        municipio=g.municipio,
        total_alunos=total_alunos
    )