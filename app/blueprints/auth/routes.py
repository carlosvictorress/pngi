from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from app.models import Usuario, Municipio
from app import db
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.url_value_preprocessor
def pull_slug(endpoint, values):
    if values:
        g.municipio_slug = values.pop('municipio_slug', None)

# -------------------------------------------------------------------------
# LOGIN DO SUPERADMIN GLOBAL
# -------------------------------------------------------------------------
@auth_bp.route('/login-admin-global', methods=['GET', 'POST'])
def login_admin_global():
    """Tela de login para o administrador geral da plataforma SaaS."""
    erro = None
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email, perfil='superadmin').first()
        
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            return redirect(url_for('auth.superadmin_dashboard'))
        else:
            erro = "E-mail ou senha de administrador incorretos."

    return render_template('publico/login_admin_global.html', erro=erro)

# -------------------------------------------------------------------------
# SETUP GLOBAL
# -------------------------------------------------------------------------
@auth_bp.route('/setup-sistema-global')
def setup_inicial():
    """Gera o SuperAdmin Global da plataforma diretamente no banco de dados."""
    admin_existente = Usuario.query.filter_by(perfil='superadmin').first()
    
    if not admin_existente:
        global_admin = Usuario(
            nome="Carlos Admin Global", 
            email="carlos@plataforma.com", 
            perfil="superadmin",
            municipio_id=None
        )
        global_admin.set_senha("master123")
        db.session.add(global_admin)
        db.session.commit()
    
    return render_template('publico/setup_sucesso.html')

# -------------------------------------------------------------------------
# PAINEL DO SUPERADMIN GLOBAL (Multi-Tenant Central)
# -------------------------------------------------------------------------
@auth_bp.route('/admin-global', methods=['GET', 'POST'])
@login_required
def superadmin_dashboard():
    """Painel mestre independente de qualquer município."""
    if current_user.perfil != 'superadmin':
        abort(403)
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'cadastrar_municipio':
            nome = request.form.get('nome')
            estado = request.form.get('estado').upper()
            slug = request.form.get('slug').lower().strip()
            limite = request.form.get('limite_alunos', 500)
            
            if Municipio.query.filter_by(slug=slug).first():
                flash("Este slug de município já existe!", "erro")
            else:
                novo_mun = Municipio(nome=nome, estado=estado, slug=slug, limite_alunos=int(limite))
                db.session.add(novo_mun)
                db.session.commit()
                
        elif action == 'cadastrar_usuario':
            municipio_id = request.form.get('municipio_id')
            nome_user = request.form.get('nome_usuario')
            email_user = request.form.get('email_usuario')
            senha_user = request.form.get('senha_usuario', 'admin123')
            
            if Usuario.query.filter_by(email=email_user).first():
                flash("Este e-mail já está cadastrado!", "erro")
            else:
                novo_usuario = Usuario(nome=nome_user, email=email_user, perfil="secretaria", municipio_id=municipio_id)
                novo_usuario.set_senha(senha_user)
                db.session.add(novo_usuario)
                db.session.commit()
                
        return redirect(url_for('auth.superadmin_dashboard'))

    municipios = Municipio.query.order_by(Municipio.nome).all()
    todos_usuarios = Usuario.query.filter(Usuario.perfil != 'superadmin').order_by(Usuario.nome).all()
    
    total_municipios = len(municipios)
    total_operadores = len(todos_usuarios)
    
    from app.models import Aluno
    total_alunos_global = Aluno.query.count()

    return render_template(
        'publico/admin_global_dashboard.html', 
        municipios=municipios,
        usuarios=todos_usuarios,
        total_municipios=total_municipios,
        total_operadores=total_operadores,
        total_alunos_global=total_alunos_global
    )

# -------------------------------------------------------------------------
# LOGIN DOS MUNICÍPIOS (Tenant)
# -------------------------------------------------------------------------
@auth_bp.route('/<municipio_slug>/login', methods=['GET', 'POST'])
def login():
    municipio_slug = g.municipio_slug
    municipio = Municipio.query.filter_by(slug=municipio_slug).first()
    if not municipio:
        abort(404, description="Município não cadastrado na plataforma.")

    erro = None
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email, municipio_id=municipio.id).first()
        
        if usuario and usuario.verificar_senha(senha):
            if not usuario.ativo:
                return "Esta conta de servidor foi desativada pela coordenação."
            login_user(usuario)
            return redirect(url_for('core.index', municipio_slug=municipio_slug))
        else:
            erro = "Usuário ou senha inválidos para este ambiente municipal."

    return render_template('publico/login_municipio.html', municipio=municipio, erro=erro)

# -------------------------------------------------------------------------
# GESTÃO GLOBAL DE USUÁRIOS E SEGURANÇA BYPASS
# -------------------------------------------------------------------------
@auth_bp.route('/admin-global/excluir-usuario/<int:user_id>')
@login_required
def excluir_usuario_global(user_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    usuario = Usuario.query.get_or_404(user_id)
    db.session.delete(usuario)
    db.session.commit()
    return redirect(url_for('auth.superadmin_dashboard'))

@auth_bp.route('/admin-global/entrar-como/<int:municipio_id>')
@login_required
def entrar_como_municipio(municipio_id):
    """Permite ao SuperAdmin entrar diretamente no ecossistema de qualquer município."""
    if current_user.perfil != 'superadmin':
        abort(403)
    municipio = Municipio.query.get_or_404(municipio_id)
    return redirect(url_for('core.index', municipio_slug=municipio.slug))

@auth_bp.route('/criar-usuario-teste/<slug_municipio>')
def criar_usuario_municipio_dinamico(slug_municipio):
    municipio = Municipio.query.filter_by(slug=slug_municipio).first()
    if not municipio:
        return f"<h3>Erro: O município '{slug_municipio}' não foi encontrado!</h3>"
        
    email_teste = f"secretaria@{slug_municipio}.gov.br"
    usuario_existe = Usuario.query.filter_by(email=email_teste).first()
    if usuario_existe:
        return redirect(url_for('auth.login', municipio_slug=slug_municipio))
        
    novo_usuario = Usuario(nome=f"Secretaria de {municipio.nome}", email=email_teste, perfil="secretaria", municipio_id=municipio.id)
    novo_usuario.set_senha("admin123")
    db.session.add(novo_usuario)
    db.session.commit()
    return redirect(url_for('auth.superadmin_dashboard'))

# -------------------------------------------------------------------------
# SESSÃO E LANDING
# -------------------------------------------------------------------------
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.landing_page'))

@auth_bp.route('/')
def landing_page():
    municipios = Municipio.query.order_by(Municipio.nome).all()
    return render_template('publico/landing.html', municipios=municipios)