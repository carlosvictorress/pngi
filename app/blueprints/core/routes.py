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
    # Ignora a raiz mestre, arquivos estáticos, PWA e rotas globais de autenticação administrativa
    if request.path == '/' or request.path.startswith('/static/') or request.path in ['/manifest.json', '/sw.js'] or request.path.startswith('/auth/login-admin-global') or request.path.startswith('/auth/admin-global'):
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

# -------------------------------------------------------------------------
# PORTAL DA FAMÍLIA / RESPONSÁVEL (Art. 28 LBI)
# -------------------------------------------------------------------------
@core_bp.route('/familia/dashboard')
@login_required
def familia_dashboard():
    from app.models import Aluno, Pei, ComunicacaoAEE, AtendimentoAee, TransporteAlunado
    from flask import flash
    
    # Busca os alunos associados ao usuário logado
    if current_user.perfil == 'familia':
        alunos = Aluno.query.filter_by(responsavel_id=current_user.id, municipio_id=g.municipio.id).all()
        if not alunos:
            matricula_temp = current_user.email.replace('familia.', '').replace('@gestoor.local', '')
            alunos = Aluno.query.filter_by(matricula=matricula_temp, municipio_id=g.municipio.id).all()
    else:
        alunos = Aluno.query.filter_by(municipio_id=g.municipio.id).limit(5).all()

    aluno_selecionado_id = request.args.get('aluno_id', type=int)
    aluno_ativo = None
    if aluno_selecionado_id:
        aluno_ativo = next((a for a in alunos if a.id == aluno_selecionado_id), None)
    
    if not aluno_ativo and alunos:
        aluno_ativo = alunos[0]

    pei_atual = None
    comunicacoes = []
    atendimentos_aee = []
    transporte = None

    if aluno_ativo:
        pei_atual = Pei.query.filter_by(aluno_id=aluno_ativo.id).order_by(Pei.id.desc()).first()
        comunicacoes = ComunicacaoAEE.query.filter_by(aluno_id=aluno_ativo.id).order_by(ComunicacaoAEE.id.desc()).all()
        atendimentos_aee = AtendimentoAee.query.filter_by(aluno_id=aluno_ativo.id).order_by(AtendimentoAee.id.desc()).all()
        transporte = TransporteAlunado.query.filter_by(aluno_id=aluno_ativo.id).first()

    return render_template(
        'familia/dashboard.html',
        alunos=alunos,
        aluno_ativo=aluno_ativo,
        pei_atual=pei_atual,
        comunicacoes=comunicacoes,
        atendimentos_aee=atendimentos_aee,
        transporte=transporte
    )

@core_bp.route('/familia/pei/<int:pei_id>/dar-ciencia', methods=['POST'])
@login_required
def dar_ciencia_pei(pei_id):
    from app.models import Pei
    from app import db
    from datetime import datetime
    from flask import flash

    pei = Pei.query.get_or_404(pei_id)
    if pei.aluno.municipio_id != g.municipio.id:
        abort(403)

    pei.assinado_familia = True
    pei.assinado_familia_em = datetime.utcnow()
    db.session.commit()

    flash("Sua assinatura / ciência digital foi registrada com sucesso no PEI do estudante!", "sucesso")
    return redirect(url_for('core.familia_dashboard', municipio_slug=g.municipio.slug, aluno_id=pei.aluno_id))

@core_bp.route('/familia/comunicacao/<int:comunicacao_id>/dar-ciencia', methods=['POST'])
@login_required
def dar_ciencia_comunicacao(comunicacao_id):
    from app.models import ComunicacaoAEE
    from app import db
    from datetime import datetime
    from flask import flash

    comunicacao = ComunicacaoAEE.query.get_or_404(comunicacao_id)
    if comunicacao.aluno.municipio_id != g.municipio.id:
        abort(403)

    comunicacao.ciencia_familia = True
    comunicacao.ciencia_data = datetime.utcnow()
    obs = request.form.get('observacoes_familia', '').strip()
    if obs:
        comunicacao.observacoes_familia = obs

    db.session.commit()
    flash("Confirmação de leitura e observações registradas!", "sucesso")
    return redirect(url_for('core.familia_dashboard', municipio_slug=g.municipio.slug, aluno_id=comunicacao.aluno_id))

# -------------------------------------------------------------------------
# PAINEL DE BLINDAGEM JURÍDICA (MINISTÉRIO PÚBLICO & CENSO INEP)
# -------------------------------------------------------------------------
@core_bp.route('/blindagem-juridica')
@login_required
def dashboard_blindagem():
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
        
    from app.models import Aluno, Pei, DocumentoAEE, Escola
    
    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).all()
    total_alunos = len(alunos)
    
    peis_homologados = 0
    peis_com_ciencia_familia = 0
    alunos_demanda_apoio = 0
    alunos_com_laudo = 0
    
    recursos_saeb_ledor = 0
    recursos_saeb_transcritor = 0
    recursos_saeb_libras = 0
    recursos_saeb_ampliado = 0
    
    for a in alunos:
        pei = Pei.query.filter_by(aluno_id=a.id).order_by(Pei.id.desc()).first()
        if pei:
            if pei.homologado_secretaria or pei.status == 'Homologado pela Secretaria':
                peis_homologados += 1
            if pei.assinado_familia:
                peis_com_ciencia_familia += 1
            if pei.necessita_profissional_apoio or a.necessita_apoio:
                alunos_demanda_apoio += 1
        elif a.necessita_apoio:
            alunos_demanda_apoio += 1
            
        laudo = DocumentoAEE.query.filter_by(aluno_id=a.id, ativo=True).filter(DocumentoAEE.tipo_documento.in_(['Laudo', 'Documento Médico'])).first()
        if laudo or a.cid:
            alunos_com_laudo += 1
            
        if a.recurso_ledor: recursos_saeb_ledor += 1
        if a.recurso_transcritor: recursos_saeb_transcritor += 1
        if a.recurso_libras: recursos_saeb_libras += 1
        if a.recurso_ampliado: recursos_saeb_ampliado += 1
        
    taxa_conformidade_pei = int((peis_homologados / total_alunos * 100)) if total_alunos > 0 else 100
    taxa_ciencia_familia = int((peis_com_ciencia_familia / total_alunos * 100)) if total_alunos > 0 else 100
    
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).all()
    
    return render_template(
        'blindagem/dashboard_blindagem.html',
        total_alunos=total_alunos,
        peis_homologados=peis_homologados,
        peis_com_ciencia_familia=peis_com_ciencia_familia,
        alunos_demanda_apoio=alunos_demanda_apoio,
        alunos_com_laudo=alunos_com_laudo,
        taxa_conformidade_pei=taxa_conformidade_pei,
        taxa_ciencia_familia=taxa_ciencia_familia,
        recursos_saeb_ledor=recursos_saeb_ledor,
        recursos_saeb_transcritor=recursos_saeb_transcritor,
        recursos_saeb_libras=recursos_saeb_libras,
        recursos_saeb_ampliado=recursos_saeb_ampliado,
        escolas=escolas,
        alunos=alunos
    )

@core_bp.route('/blindagem-juridica/relatorio-mp')
@login_required
def relatorio_mp():
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
        
    from app.models import Aluno, Pei, DocumentoAEE
    from datetime import datetime
    
    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    
    dossie_alunos = []
    for a in alunos:
        pei = Pei.query.filter_by(aluno_id=a.id).order_by(Pei.id.desc()).first()
        laudo = DocumentoAEE.query.filter_by(aluno_id=a.id, ativo=True).filter(DocumentoAEE.tipo_documento.in_(['Laudo', 'Documento Médico'])).first()
        
        dossie_alunos.append({
            'aluno': a,
            'pei': pei,
            'laudo': laudo,
            'escola_nome': a.escola.nome if a.escola else 'Não Informada'
        })
        
    data_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M')
    
    return render_template(
        'blindagem/relatorio_mp.html',
        dossie_alunos=dossie_alunos,
        data_emissao=data_emissao
    )

@core_bp.route('/blindagem-juridica/relatorio-profissionais-apoio')
@login_required
def relatorio_profissionais_apoio():
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
        
    from app.models import Aluno, Escola, Pei
    from datetime import datetime
    
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()
    
    relatorio_escolas = []
    for esc in escolas:
        alunos_escola = Aluno.query.filter_by(escola_id=esc.id, ativo=True).all()
        alunos_apoio = []
        for a in alunos_escola:
            pei = Pei.query.filter_by(aluno_id=a.id).order_by(Pei.id.desc()).first()
            necessita = False
            especificacao = "Atendimento a cuidados de higiene, locomoção e alimentação."
            
            if a.necessita_apoio or a.cadeirante or a.necessita_acompanhante:
                necessita = True
            if pei and pei.necessita_profissional_apoio:
                necessita = True
                if pei.atividades_apoio_especificadas:
                    especificacao = pei.atividades_apoio_especificadas
                    
            if necessita:
                alunos_apoio.append({
                    'aluno': a,
                    'pei': pei,
                    'especificacao': especificacao
                })
                
        relatorio_escolas.append({
            'escola': esc,
            'total_pcd': len(alunos_escola),
            'total_apoio': len(alunos_apoio),
            'alunos_apoio': alunos_apoio
        })
        
    data_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M')
    
    return render_template(
        'blindagem/relatorio_apoio.html',
        relatorio_escolas=relatorio_escolas,
        data_emissao=data_emissao
    )

@core_bp.route('/blindagem-juridica/exportar-censo-inep')
@login_required
def exportar_censo_inep():
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
        
    from app.models import Aluno
    
    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    
    return render_template(
        'blindagem/exportar_inep.html',
        alunos=alunos
    )