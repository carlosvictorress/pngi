from flask import Blueprint, render_template, request, redirect, url_for, g, abort
from flask_login import login_required, current_user
from app.models import Municipio, Aluno 

core_bp = Blueprint('core', __name__)

@core_bp.url_value_preprocessor
def pull_municipio_slug(endpoint, values):
    """Extrai e remove municipio_slug da URL para não causar TypeError nas views do Blueprint."""
    if values and 'municipio_slug' in values:
        g.municipio_slug = values.pop('municipio_slug')
        g.municipio = Municipio.query.filter_by(slug=g.municipio_slug).first()

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
# INDEX / DASHBOARD DO MUNICÍPIO INDIVIDUAL
# -------------------------------------------------------------------------
@core_bp.route('/dashboard')
@login_required
def index():
    """Dashboard principal isolada de cada prefeitura."""
    if not g.municipio:
        abort(404)

    from app.models import Usuario, Escola, Pei, Aluno

    total_alunos = Aluno.query.filter_by(municipio_id=g.municipio.id).count()
    total_equipe = Usuario.query.filter_by(municipio_id=g.municipio.id).count()
    total_escolas = Escola.query.filter_by(municipio_id=g.municipio.id).count()
    total_peis = Pei.query.join(Aluno).filter(Aluno.municipio_id == g.municipio.id).count()

    return render_template(
        'publico/dashboard_municipio.html', 
        municipio=g.municipio,
        total_alunos=total_alunos,
        total_equipe=total_equipe,
        total_escolas=total_escolas,
        total_peis=total_peis
    )

# -------------------------------------------------------------------------
# GESTÃO LOCAL DA EQUIPE MULTIDISCIPLINAR (SECRETARIA MUNICIPAL)
# -------------------------------------------------------------------------
@core_bp.route('/usuarios', methods=['GET', 'POST'])
@login_required
def gerenciar_usuarios():
    """Painel de gestão dos profissionais multidisciplinares da prefeitura."""
    if not g.municipio:
        abort(404)
        
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403, description="Apenas a Secretaria de Educação pode gerenciar a equipe multidisciplinar.")

    from app.models import Usuario
    from app import db
    from flask import flash

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'cadastrar_usuario':
            nome = request.form.get('nome', '').strip()
            email = request.form.get('email', '').strip()
            senha = request.form.get('senha', 'admin@2026')
            perfil = request.form.get('perfil', 'professor')

            if Usuario.query.filter_by(email=email).first():
                flash(f"O e-mail '{email}' já está cadastrado no sistema!", "erro")
            else:
                novo_usuario = Usuario(
                    nome=nome,
                    email=email,
                    perfil=perfil,
                    municipio_id=g.municipio.id
                )
                novo_usuario.set_senha(senha)
                db.session.add(novo_usuario)
                db.session.commit()
                flash(f"Profissional '{nome}' cadastrado com sucesso!", "sucesso")

        return redirect(url_for('core.gerenciar_usuarios', municipio_slug=g.municipio.slug))

    filtro_perfil = request.args.get('filtro_perfil', '')
    busca_usuario = request.args.get('busca_usuario', '').strip()

    query_usuarios = Usuario.query.filter_by(municipio_id=g.municipio.id)

    if filtro_perfil:
        query_usuarios = query_usuarios.filter(Usuario.perfil == filtro_perfil)
    if busca_usuario:
        query_usuarios = query_usuarios.filter(
            (Usuario.nome.ilike(f"%{busca_usuario}%")) | (Usuario.email.ilike(f"%{busca_usuario}%"))
        )

    usuarios = query_usuarios.order_by(Usuario.nome).all()

    return render_template(
        'core/usuarios.html',
        municipio=g.municipio,
        usuarios=usuarios,
        filtro_perfil=filtro_perfil,
        busca_usuario=busca_usuario
    )

@core_bp.route('/usuarios/<int:user_id>/editar', methods=['POST'])
@login_required
def editar_usuario_local(user_id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)

    from app.models import Usuario
    from app import db
    from flask import flash

    usuario = Usuario.query.get_or_404(user_id)
    if usuario.municipio_id != g.municipio.id and current_user.perfil != 'superadmin':
        abort(403)

    nome = request.form.get('nome', '').strip()
    email = request.form.get('email', '').strip()
    perfil = request.form.get('perfil')

    email_existente = Usuario.query.filter(Usuario.email == email, Usuario.id != user_id).first()
    if email_existente:
        flash(f"O e-mail '{email}' pertence a outro usuário.", "erro")
    else:
        usuario.nome = nome
        usuario.email = email
        usuario.perfil = perfil
        db.session.commit()
        flash(f"Cadastro do profissional '{usuario.nome}' atualizado!", "sucesso")

    return redirect(url_for('core.gerenciar_usuarios', municipio_slug=g.municipio.slug))

@core_bp.route('/usuarios/<int:user_id>/resetar-senha', methods=['POST'])
@login_required
def resetar_senha_usuario_local(user_id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)

    from app.models import Usuario
    from app import db
    from flask import flash

    usuario = Usuario.query.get_or_404(user_id)
    if usuario.municipio_id != g.municipio.id and current_user.perfil != 'superadmin':
        abort(403)

    nova_senha = request.form.get('nova_senha', '').strip()
    if not nova_senha:
        flash("Informe a nova senha!", "erro")
    else:
        usuario.set_senha(nova_senha)
        db.session.commit()
        flash(f"Senha do profissional '{usuario.nome}' redefinida!", "sucesso")

    return redirect(url_for('core.gerenciar_usuarios', municipio_slug=g.municipio.slug))

@core_bp.route('/usuarios/<int:user_id>/toggle-status')
@login_required
def toggle_status_usuario_local(user_id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)

    from app.models import Usuario
    from app import db
    from flask import flash

    usuario = Usuario.query.get_or_404(user_id)
    if usuario.municipio_id != g.municipio.id and current_user.perfil != 'superadmin':
        abort(403)

    usuario.ativo = not usuario.ativo
    db.session.commit()
    status_str = "ativado" if usuario.ativo else "bloqueado"
    flash(f"Acesso de '{usuario.nome}' foi {status_str}!", "sucesso")

    return redirect(url_for('core.gerenciar_usuarios', municipio_slug=g.municipio.slug))

@core_bp.route('/usuarios/<int:user_id>/excluir')
@login_required
def excluir_usuario_local(user_id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)

    from app.models import Usuario
    from app import db
    from flask import flash

    usuario = Usuario.query.get_or_404(user_id)
    if usuario.municipio_id != g.municipio.id and current_user.perfil != 'superadmin':
        abort(403)

    nome_u = usuario.nome
    db.session.delete(usuario)
    db.session.commit()
    flash(f"Profissional '{nome_u}' removido do cadastro municipal.", "sucesso")

    return redirect(url_for('core.gerenciar_usuarios', municipio_slug=g.municipio.slug))