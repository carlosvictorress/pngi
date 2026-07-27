from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort, session
from app.models import Usuario, Municipio, Aluno, Escola, Pei, AtendimentoAee
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
# PAINEL DO SUPERADMIN GLOBAL (Central de Comando Mestre)
# -------------------------------------------------------------------------
@auth_bp.route('/admin-global', methods=['GET', 'POST'])
@login_required
def superadmin_dashboard():
    """Painel mestre com controle total de todos os tenants e usuários."""
    if current_user.perfil != 'superadmin':
        superadmin_id = session.get('impersonator_id')
        if superadmin_id:
            superadmin_user = Usuario.query.get(superadmin_id)
            if superadmin_user and superadmin_user.perfil == 'superadmin':
                login_user(superadmin_user)
                session.pop('impersonator_id', None)
                flash("Você retornou automaticamente à Torre de Controle Mestre do SuperAdmin.", "sucesso")
                return redirect(url_for('auth.superadmin_dashboard'))
        abort(403)
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'cadastrar_municipio':
            nome = request.form.get('nome', '').strip()
            estado = request.form.get('estado', '').upper().strip()
            slug = request.form.get('slug', '').lower().strip()
            limite = request.form.get('limite_alunos', 500)
            brasao_url = request.form.get('brasao_url', '').strip()
            
            nome_secretario = request.form.get('nome_secretario', '').strip()
            email_secretario = request.form.get('email_secretario', '').strip()
            senha_prov = request.form.get('senha_provisoria_secretario', 'Mudar@123').strip()
            
            if Municipio.query.filter_by(slug=slug).first():
                flash(f"O slug '{slug}' já pertence a outro município!", "erro")
            elif Municipio.query.filter_by(nome=nome).first():
                flash(f"O município '{nome}' já está cadastrado!", "erro")
            elif email_secretario and Usuario.query.filter_by(email=email_secretario).first():
                flash(f"O e-mail da secretaria '{email_secretario}' já está cadastrado em outra conta!", "erro")
            else:
                novo_mun = Municipio(
                    nome=nome, 
                    estado=estado, 
                    slug=slug, 
                    limite_alunos=int(limite),
                    brasao_url=brasao_url if brasao_url else None
                )
                db.session.add(novo_mun)
                db.session.flush()

                msg_adicional = ""
                if email_secretario:
                    secretario = Usuario(
                        nome=nome_secretario if nome_secretario else f"Secretaria de Educação - {nome}",
                        email=email_secretario,
                        perfil='secretaria',
                        municipio_id=novo_mun.id,
                        senha_provisoria=True
                    )
                    secretario.set_senha(senha_prov if senha_prov else 'Mudar@123')
                    db.session.add(secretario)
                    msg_adicional = f" Conta da Secretaria de Educação criada para '{email_secretario}' com a senha provisória '{senha_prov if senha_prov else 'Mudar@123'}'."

                db.session.commit()
                flash(f"Município '{nome}' ativado com sucesso!{msg_adicional}", "sucesso")
                
        elif action == 'cadastrar_usuario':
            municipio_id = request.form.get('municipio_id')
            nome_user = request.form.get('nome_usuario', '').strip()
            email_user = request.form.get('email_usuario', '').strip()
            senha_user = request.form.get('senha_usuario', 'admin@2026')
            perfil_user = request.form.get('perfil_usuario', 'secretaria')
            is_provisoria = request.form.get('senha_provisoria') == 'on' or request.form.get('senha_provisoria') == 'true'
            
            if Usuario.query.filter_by(email=email_user).first():
                flash("Este e-mail já está cadastrado no sistema!", "erro")
            else:
                mun_id = int(municipio_id) if municipio_id and municipio_id != 'none' else None
                novo_usuario = Usuario(
                    nome=nome_user, 
                    email=email_user, 
                    perfil=perfil_user, 
                    municipio_id=mun_id,
                    senha_provisoria=is_provisoria
                )
                novo_usuario.set_senha(senha_user)
                db.session.add(novo_usuario)
                db.session.commit()
                flash(f"Usuário '{nome_user}' ({perfil_user}) cadastrado com sucesso!", "sucesso")
                
        return redirect(url_for('auth.superadmin_dashboard'))

    # Filtros para busca de usuários na tabela mestre
    filtro_municipio = request.args.get('filtro_municipio', '')
    filtro_perfil = request.args.get('filtro_perfil', '')
    busca_usuario = request.args.get('busca_usuario', '').strip()

    query_usuarios = Usuario.query.filter(Usuario.perfil != 'superadmin')

    if filtro_municipio:
        query_usuarios = query_usuarios.filter(Usuario.municipio_id == int(filtro_municipio))
    if filtro_perfil:
        query_usuarios = query_usuarios.filter(Usuario.perfil == filtro_perfil)
    if busca_usuario:
        query_usuarios = query_usuarios.filter(
            (Usuario.nome.ilike(f"%{busca_usuario}%")) | (Usuario.email.ilike(f"%{busca_usuario}%"))
        )

    todos_usuarios = query_usuarios.order_by(Usuario.nome).all()
    municipios = Municipio.query.order_by(Municipio.nome).all()

    # Estatísticas Globais
    total_municipios = len(municipios)
    total_municipios_ativos = len([m for m in municipios if m.ativo])
    total_operadores = Usuario.query.filter(Usuario.perfil != 'superadmin').count()
    total_alunos_global = Aluno.query.count()
    total_escolas_global = Escola.query.count()
    total_peis_global = Pei.query.count()

    return render_template(
        'publico/admin_global_dashboard.html', 
        municipios=municipios,
        usuarios=todos_usuarios,
        total_municipios=total_municipios,
        total_municipios_ativos=total_municipios_ativos,
        total_operadores=total_operadores,
        total_alunos_global=total_alunos_global,
        total_escolas_global=total_escolas_global,
        total_peis_global=total_peis_global,
        filtro_municipio=filtro_municipio,
        filtro_perfil=filtro_perfil,
        busca_usuario=busca_usuario
    )

# -------------------------------------------------------------------------
# AÇÕES DE CONTROLE DE MUNICÍPIOS (CRUD SUPERADMIN)
# -------------------------------------------------------------------------
@auth_bp.route('/admin-global/municipio/<int:mun_id>/editar', methods=['POST'])
@login_required
def editar_municipio(mun_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    municipio = Municipio.query.get_or_404(mun_id)
    
    nome = request.form.get('nome', '').strip()
    estado = request.form.get('estado', '').upper().strip()
    slug = request.form.get('slug', '').lower().strip()
    limite = request.form.get('limite_alunos', 500)
    brasao_url = request.form.get('brasao_url', '').strip()
    
    slug_existente = Municipio.query.filter(Municipio.slug == slug, Municipio.id != mun_id).first()
    if slug_existente:
        flash(f"O slug '{slug}' já está em uso por outro município.", "erro")
    else:
        municipio.nome = nome
        municipio.estado = estado
        municipio.slug = slug
        municipio.limite_alunos = int(limite)
        municipio.brasao_url = brasao_url if brasao_url else None
        db.session.commit()
        flash(f"Município '{municipio.nome}' atualizado com sucesso!", "sucesso")
        
    return redirect(url_for('auth.superadmin_dashboard'))

@auth_bp.route('/admin-global/municipio/<int:mun_id>/toggle-status')
@login_required
def toggle_status_municipio(mun_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    municipio = Municipio.query.get_or_404(mun_id)
    municipio.ativo = not municipio.ativo
    db.session.commit()
    status_str = "ativado" if municipio.ativo else "suspenso"
    flash(f"Município '{municipio.nome}' foi {status_str} com sucesso!", "sucesso")
    return redirect(url_for('auth.superadmin_dashboard'))

@auth_bp.route('/admin-global/municipio/<int:mun_id>/excluir', methods=['POST', 'GET'])
@login_required
def excluir_municipio(mun_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    municipio = Municipio.query.get_or_404(mun_id)
    nome_mun = municipio.nome
    
    from app.models import (
        Aluno, EstudoCaso, Pei, Paee, EvolucaoAEE, PlanoAEE, AgendaAEE, AtendimentoAee, 
        TransporteAlunado, DocumentoAEE, ComunicacaoAEE, TransferenciaAluno, 
        ProfissionalAEE, Escola, Usuario
    )
    
    # 1. Anula a referência municipio_origem_id de alunos em outros municípios
    Aluno.query.filter_by(municipio_origem_id=mun_id).update({'municipio_origem_id': None}, synchronize_session=False)

    # 2. Exclui documentos e comunicações diretas por município
    DocumentoAEE.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)
    ComunicacaoAEE.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)
    EvolucaoAEE.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)
    PlanoAEE.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)
    AgendaAEE.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)

    # 3. Busca IDs de alunos pertencentes a este município
    alunos_mun = Aluno.query.filter_by(municipio_id=mun_id).all()
    aluno_ids = [a.id for a in alunos_mun]
    
    # 4. Exclui documentos operacionais atrelados aos alunos do município
    if aluno_ids:
        DocumentoAEE.query.filter(DocumentoAEE.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        ComunicacaoAEE.query.filter(ComunicacaoAEE.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        EstudoCaso.query.filter(EstudoCaso.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        Pei.query.filter(Pei.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        Paee.query.filter(Paee.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        EvolucaoAEE.query.filter(EvolucaoAEE.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        PlanoAEE.query.filter(PlanoAEE.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        AgendaAEE.query.filter(AgendaAEE.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        AtendimentoAee.query.filter(AtendimentoAee.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
        TransporteAlunado.query.filter(TransporteAlunado.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)

    # 5. Exclui registros de transferências antes dos alunos
    if aluno_ids:
        TransferenciaAluno.query.filter((TransferenciaAluno.aluno_id.in_(aluno_ids)) | (TransferenciaAluno.municipio_origem_id == mun_id) | (TransferenciaAluno.municipio_destino_id == mun_id)).delete(synchronize_session=False)
    else:
        TransferenciaAluno.query.filter((TransferenciaAluno.municipio_origem_id == mun_id) | (TransferenciaAluno.municipio_destino_id == mun_id)).delete(synchronize_session=False)

    # 6. Exclui Alunos do município (antes das escolas)
    Aluno.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)
    
    # 7. Exclui Escolas do município
    Escola.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)

    # 8. Exclui Profissionais do município
    ProfissionalAEE.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)

    # 9. Exclui Usuários do município
    Usuario.query.filter_by(municipio_id=mun_id).delete(synchronize_session=False)
    
    # 10. Remove o município
    db.session.delete(municipio)
    db.session.commit()
    
    flash(f"Município '{nome_mun}' e todos os seus dados foram excluídos da plataforma com sucesso!", "sucesso")
    return redirect(url_for('auth.superadmin_dashboard'))

# -------------------------------------------------------------------------
# AÇÕES DE CONTROLE DE USUÁRIOS (CRUD SUPERADMIN)
# -------------------------------------------------------------------------
@auth_bp.route('/admin-global/usuario/<int:user_id>/editar', methods=['POST'])
@login_required
def editar_usuario(user_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    usuario = Usuario.query.get_or_404(user_id)
    
    nome = request.form.get('nome', '').strip()
    email = request.form.get('email', '').strip()
    perfil = request.form.get('perfil')
    municipio_id = request.form.get('municipio_id')
    
    email_existente = Usuario.query.filter(Usuario.email == email, Usuario.id != user_id).first()
    if email_existente:
        flash(f"O e-mail '{email}' já está em uso por outro usuário.", "erro")
    else:
        usuario.nome = nome
        usuario.email = email
        usuario.perfil = perfil
        usuario.municipio_id = int(municipio_id) if municipio_id and municipio_id != 'none' else None
        db.session.commit()
        flash(f"Dados do usuário '{usuario.nome}' atualizados!", "sucesso")
        
    return redirect(url_for('auth.superadmin_dashboard'))

@auth_bp.route('/admin-global/usuario/<int:user_id>/resetar-senha', methods=['POST'])
@login_required
def resetar_senha_usuario(user_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    usuario = Usuario.query.get_or_404(user_id)
    nova_senha = request.form.get('nova_senha', '').strip()
    
    if not nova_senha:
        flash("Informe a nova senha!", "erro")
    else:
        usuario.set_senha(nova_senha)
        db.session.commit()
        flash(f"Senha do usuário '{usuario.nome}' alterada com sucesso!", "sucesso")
        
    return redirect(url_for('auth.superadmin_dashboard'))

@auth_bp.route('/admin-global/usuario/<int:user_id>/toggle-status')
@login_required
def toggle_status_usuario(user_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    usuario = Usuario.query.get_or_404(user_id)
    usuario.ativo = not usuario.ativo
    db.session.commit()
    status_str = "ativado" if usuario.ativo else "desativado"
    flash(f"Usuário '{usuario.nome}' foi {status_str}!", "sucesso")
    return redirect(url_for('auth.superadmin_dashboard'))

@auth_bp.route('/admin-global/excluir-usuario/<int:user_id>')
@login_required
def excluir_usuario_global(user_id):
    if current_user.perfil != 'superadmin':
        abort(403)
    usuario = Usuario.query.get_or_404(user_id)
    nome_u = usuario.nome
    db.session.delete(usuario)
    db.session.commit()
    flash(f"Conta de '{nome_u}' excluída permanentemente.", "sucesso")
    return redirect(url_for('auth.superadmin_dashboard'))

# -------------------------------------------------------------------------
# IMPERSONAÇÃO DE SESSÃO & BYPASS SUPORTE
# -------------------------------------------------------------------------
@auth_bp.route('/admin-global/impersonar/<int:user_id>')
@login_required
def impersonar_usuario(user_id):
    """Permite ao SuperAdmin assumir instantaneamente o login de qualquer operador mantendo rastro para retornar."""
    if current_user.perfil != 'superadmin' and not session.get('impersonator_id'):
        abort(403)
        
    superadmin_id = session.get('impersonator_id') or current_user.id
    usuario_alvo = Usuario.query.get_or_404(user_id)
    
    login_user(usuario_alvo)
    session['impersonator_id'] = superadmin_id
    flash(f"🎭 Modo Impersonação Ativo: Você agora está navegando como '{usuario_alvo.nome}' ({usuario_alvo.perfil.upper()}).", "sucesso")
    
    if usuario_alvo.municipio:
        return redirect(url_for('core.index', municipio_slug=usuario_alvo.municipio.slug))
    return redirect(url_for('publico.index'))

@auth_bp.route('/admin-global/parar-impersonacao')
def parar_impersonacao():
    """Restaura a conta mestre do SuperAdmin e encerra o modo impersonação."""
    superadmin_id = session.pop('impersonator_id', None)
    if superadmin_id:
        superadmin_user = Usuario.query.get(superadmin_id)
        if superadmin_user:
            login_user(superadmin_user)
            flash("Modo Impersonação encerrado. Você retornou ao perfil de Administrador Geral.", "sucesso")
            return redirect(url_for('auth.superadmin_dashboard'))
    return redirect(url_for('publico.index'))

@auth_bp.route('/admin-global/entrar-como/<int:municipio_id>')
@login_required
def entrar_como_municipio(municipio_id):
    """Permite ao SuperAdmin entrar diretamente no ecossistema de qualquer município."""
    if current_user.perfil != 'superadmin':
        abort(403)
    municipio = Municipio.query.get_or_404(municipio_id)
    return redirect(url_for('core.index', municipio_slug=municipio.slug))

@auth_bp.route('/admin-global/alterar-senha', methods=['POST'])
@login_required
def alterar_senha_superadmin():
    if current_user.perfil != 'superadmin':
        abort(403)
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    
    if not current_user.verificar_senha(senha_atual):
        flash("Senha atual incorreta!", "erro")
    elif len(nova_senha) < 6:
        flash("A nova senha deve conter pelo menos 6 caracteres.", "erro")
    else:
        current_user.set_senha(nova_senha)
        db.session.commit()
        flash("Senha mestre atualizada com sucesso!", "sucesso")
        
    return redirect(url_for('auth.superadmin_dashboard'))

@auth_bp.route('/criar-usuario-teste/<slug_municipio>')
def criar_usuario_municipio_dinamico(slug_municipio):
    municipio = Municipio.query.filter_by(slug=slug_municipio).first()
    if not municipio:
        return f"<h3>Erro: O município '{slug_municipio}' não foi encontrado!</h3>"
        
    email_teste = f"secretaria@{slug_municipio}.gov.br"
    usuario_existe = Usuario.query.filter_by(email=email_teste).first()
    if usuario_existe:
        return redirect(url_for('auth.login', municipio_slug=slug_municipio))
        
    novo_usuario = Usuario(
        nome=f"Secretaria de {municipio.nome}", 
        email=email_teste, 
        perfil="secretaria", 
        municipio_id=municipio.id
    )
    novo_usuario.set_senha("admin123")
    db.session.add(novo_usuario)
    db.session.commit()
    flash(f"Usuário de teste criado para {municipio.nome}!", "sucesso")
    return redirect(url_for('auth.superadmin_dashboard'))

# -------------------------------------------------------------------------
# LOGIN DOS MUNICÍPIOS (Tenant)
# -------------------------------------------------------------------------
@auth_bp.route('/<municipio_slug>/login', methods=['GET', 'POST'])
def login():
    municipio_slug = g.municipio_slug
    municipio = Municipio.query.filter_by(slug=municipio_slug).first()
    if not municipio:
        abort(404, description="Município não cadastrado na plataforma.")

    modal_suspenso = False
    erro = None

    # Se a prefeitura está inativa/suspensa
    if not municipio.ativo:
        modal_suspenso = True

    if request.method == 'POST':
        if not municipio.ativo:
            # Se tentou logar em município suspenso, força a exibição do modal
            modal_suspenso = True
        else:
            email = request.form.get('email')
            senha = request.form.get('senha')
            
            usuario = Usuario.query.filter_by(email=email, municipio_id=municipio.id).first()
            
            if usuario and usuario.verificar_senha(senha):
                if not usuario.ativo:
                    erro = "Esta conta de servidor foi desativada pela coordenação municipal."
                else:
                    login_user(usuario)
                    return redirect(url_for('core.index', municipio_slug=municipio_slug))
            else:
                erro = "Usuário ou senha inválidos para este ambiente municipal."

    return render_template('publico/login_municipio.html', municipio=municipio, erro=erro, modal_suspenso=modal_suspenso)

# -------------------------------------------------------------------------
# SESSÃO E LANDING
# -------------------------------------------------------------------------
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada com segurança.", "sucesso")
    return redirect(url_for('auth.landing_page'))

# -------------------------------------------------------------------------
# TROCA DE SENHA PROVISÓRIA (PRIMEIRO ACESSO)
# -------------------------------------------------------------------------
@auth_bp.route('/alterar-senha-provisoria', methods=['POST'])
@login_required
def alterar_senha_provisoria():
    senha_atual = request.form.get('senha_atual', '').strip()
    nova_senha = request.form.get('nova_senha', '').strip()
    confirmar_senha = request.form.get('confirmar_senha', '').strip()
    
    if not current_user.verificar_senha(senha_atual):
        flash("A senha provisória informada não confere com a atual.", "erro")
        return redirect(request.referrer or url_for('auth.landing_page'))
        
    if len(nova_senha) < 6:
        flash("A nova senha deve ter no mínimo 6 caracteres por razões de segurança.", "erro")
        return redirect(request.referrer or url_for('auth.landing_page'))
        
    if nova_senha != confirmar_senha:
        flash("A nova senha e a confirmação de senha não coincidem.", "erro")
        return redirect(request.referrer or url_for('auth.landing_page'))
        
    current_user.set_senha(nova_senha)
    current_user.senha_provisoria = False
    db.session.commit()
    
    flash("Sua senha pessoal foi cadastrada com sucesso! Bem-vindo(a) à plataforma.", "sucesso")
    return redirect(request.referrer or url_for('auth.landing_page'))

@auth_bp.route('/')
def landing_page():
    municipios = Municipio.query.order_by(Municipio.nome).all()
    return render_template('publico/landing.html', municipios=municipios)