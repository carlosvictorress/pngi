from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, g, abort, flash, session
from flask_login import login_required, current_user
from app import db
from app.models import Municipio, Aluno, ProfissionalAEE, Usuario, Escola, Pei

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
            pass
        elif current_user.municipio_id != g.municipio.id:
            abort(403, description="Acesso negado: Você não pertence a esta instância municipal.")

    # PROTEÇÃO CONTRA ACESSO A MÓDULOS NÃO CONTRATADOS / DESATIVADOS
    caminho = request.path.rstrip('/')
    slug_prefix = f"/{g.municipio_slug}"

    if caminho == f"{slug_prefix}/pei" or caminho.startswith(f"{slug_prefix}/pei/"):
        if not getattr(g.municipio, 'modulo_pei', True):
            from flask import flash
            flash(f"O módulo 'PEI Inteligente' não está habilitado para {g.municipio.nome}.", "warning")
            return redirect(url_for('core.index', municipio_slug=g.municipio_slug))

    elif caminho == f"{slug_prefix}/aee" or caminho.startswith(f"{slug_prefix}/aee/"):
        if not getattr(g.municipio, 'modulo_aee', True):
            from flask import flash
            flash(f"O módulo 'Sala de Recursos / AEE' não está habilitado para {g.municipio.nome}.", "warning")
            return redirect(url_for('core.index', municipio_slug=g.municipio_slug))

    elif caminho == f"{slug_prefix}/equipe-multi" or caminho.startswith(f"{slug_prefix}/equipe-multi/"):
        if not getattr(g.municipio, 'modulo_equipe_multi', True):
            from flask import flash
            flash(f"O módulo 'Equipe Multiprofissional' não está habilitado para {g.municipio.nome}.", "warning")
            return redirect(url_for('core.index', municipio_slug=g.municipio_slug))

    elif caminho == f"{slug_prefix}/transporte" or caminho.startswith(f"{slug_prefix}/transporte/"):
        if not getattr(g.municipio, 'modulo_transporte', True):
            from flask import flash
            flash(f"O módulo 'Transporte Inclusivo' não está habilitado para {g.municipio.nome}.", "warning")
            return redirect(url_for('core.index', municipio_slug=g.municipio_slug))

    elif caminho == f"{slug_prefix}/blindagem-juridica" or caminho.startswith(f"{slug_prefix}/blindagem-juridica/"):
        if not getattr(g.municipio, 'modulo_blindagem_juridica', True):
            from flask import flash
            flash(f"O módulo 'Blindagem Jurídica & MP' não está habilitado para {g.municipio.nome}.", "warning")
            return redirect(url_for('core.index', municipio_slug=g.municipio_slug))

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
# QUADRO UNIFICADO DE PROFISSIONAIS & EQUIPE (SECRETARIA MUNICIPAL)
# -------------------------------------------------------------------------
MAPA_CARGO_PERFIL = {
    'Professor(a) de AEE (SRM)': 'aee',
    'Psicólogo(a) Escolar': 'psicologo',
    'Psicopedagogo(a)': 'psicopedagogo',
    'Assistente Social': 'assistente_social',
    'Fonoaudiólogo(a)': 'fonoaudiologo',
    'Terapeuta Ocupacional': 'terapeuta_ocupacional',
    'Tradutor e Intérprete de Libras': 'professor_libras',
    'Especialista em Braille': 'professor_braille',
    'Guia-Intérprete': 'professor_libras',
    'Profissional de Apoio Escolar / Cuidador': 'cuidador',
    'Auxiliar de Inclusão': 'cuidador',
    'Professor(a) de Sala Regular': 'professor',
    'Diretor(a) / Coordenador(a) Escolar': 'diretor',
    'Secretaria Municipal de Educação': 'secretaria',
    'Monitor / Gestor de Transporte': 'transporte',
}

@core_bp.route('/profissionais', methods=['GET', 'POST'])
@core_bp.route('/usuarios', methods=['GET', 'POST'])
@login_required
def gerenciar_profissionais():
    """Painel único centralizado de gestão de todos os profissionais e especialistas do município."""
    if not g.municipio:
        abort(404)
        
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403, description="Apenas a Secretaria de Educação pode gerenciar o quadro de profissionais.")

    from app.models import ProfissionalAEE, Usuario, Escola
    from app import db
    from flask import flash

    if request.method == 'POST':
        action = request.form.get('action')

        if action in ['cadastrar_profissional', 'cadastrar_usuario']:
            nome = request.form.get('nome', '').strip()
            cargo = request.form.get('cargo', '').strip() or 'Professor(a) de AEE (SRM)'
            escola_polo = request.form.get('escola_polo', '').strip() or 'Sede da Secretaria de Educação'
            cpf = request.form.get('cpf', '').strip()
            telefone = request.form.get('telefone', '').strip()
            email = request.form.get('email', '').strip().lower()
            habilitar_login = request.form.get('habilitar_login') in ['on', 'true', '1', True]
            senha = request.form.get('senha', 'Mudar@123').strip() or 'Mudar@123'
            perfil = request.form.get('perfil', '').strip() or MAPA_CARGO_PERFIL.get(cargo, 'professor')

            if habilitar_login and email and Usuario.query.filter_by(email=email).first():
                flash(f"O e-mail '{email}' já está em uso por outro usuário!", "erro")
            else:
                novo_prof = ProfissionalAEE(
                    municipio_id=g.municipio.id,
                    nome=nome,
                    cpf=cpf,
                    cargo=cargo,
                    escola_polo=escola_polo,
                    telefone=telefone,
                    email=email if email else None,
                    ativo=True,
                    status='Ativo'
                )
                db.session.add(novo_prof)
                db.session.flush()

                if habilitar_login and email:
                    novo_user = Usuario(
                        municipio_id=g.municipio.id,
                        nome=nome,
                        email=email,
                        perfil=perfil,
                        cpf=cpf,
                        telefone=telefone,
                        cargo=cargo,
                        escola_polo=escola_polo,
                        senha_provisoria=True,
                        ativo=True
                    )
                    novo_user.set_senha(senha)
                    db.session.add(novo_user)
                    db.session.flush()
                    novo_prof.usuario_id = novo_user.id

                db.session.commit()
                flash(f"Profissional '{nome}' cadastrado com sucesso no quadro da rede municipal!", "sucesso")

        return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))

    filtro_categoria = request.args.get('categoria', 'todos')
    busca = request.args.get('busca', '').strip()

    query_prof = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id)
    if busca:
        query_prof = query_prof.filter(
            (ProfissionalAEE.nome.ilike(f"%{busca}%")) |
            (ProfissionalAEE.cpf.ilike(f"%{busca}%")) |
            (ProfissionalAEE.cargo.ilike(f"%{busca}%")) |
            (ProfissionalAEE.email.ilike(f"%{busca}%")) |
            (ProfissionalAEE.escola_polo.ilike(f"%{busca}%"))
        )

    profissionais = query_prof.order_by(ProfissionalAEE.nome).all()

    # Contadores e categorização do quadro municipal
    total_geral = len(profissionais)
    prof_aee = [p for p in profissionais if p.cargo and 'AEE' in p.cargo.upper()]
    prof_multi = [p for p in profissionais if p.cargo and any(k in p.cargo.lower() for k in ['psicolog', 'psicopedagog', 'social', 'fono', 'terapeut'])]
    prof_apoio = [p for p in profissionais if p.cargo and any(k in p.cargo.lower() for k in ['apoio', 'cuidador', 'auxiliar'])]
    prof_libras = [p for p in profissionais if p.cargo and any(k in p.cargo.lower() for k in ['libras', 'braille', 'intérprete', 'interprete'])]
    prof_gestao = [p for p in profissionais if p.cargo and any(k in p.cargo.lower() for k in ['regular', 'sala', 'diretor', 'secretaria', 'coordenad', 'transporte'])]

    profissionais_filtrados = profissionais
    if filtro_categoria == 'aee':
        profissionais_filtrados = prof_aee
    elif filtro_categoria == 'multi':
        profissionais_filtrados = prof_multi
    elif filtro_categoria == 'apoio':
        profissionais_filtrados = prof_apoio
    elif filtro_categoria == 'libras':
        profissionais_filtrados = prof_libras
    elif filtro_categoria == 'gestao':
        profissionais_filtrados = prof_gestao

    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()

    return render_template(
        'core/profissionais.html',
        municipio=g.municipio,
        profissionais=profissionais_filtrados,
        total_geral=total_geral,
        total_aee=len(prof_aee),
        total_multi=len(prof_multi),
        total_apoio=len(prof_apoio),
        total_libras=len(prof_libras),
        total_gestao=len(prof_gestao),
        escolas=escolas,
        filtro_categoria=filtro_categoria,
        busca=busca,
        now=datetime.utcnow()
    )



@core_bp.route('/profissionais/<int:id>/editar', methods=['POST'])
@core_bp.route('/usuarios/<int:id>/editar', methods=['POST'])
@login_required
def editar_profissional(id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
    from app.models import ProfissionalAEE, Usuario
    from app import db
    from flask import flash

    prof = ProfissionalAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first()
    if not prof:
        user_backup = Usuario.query.filter_by(id=id, municipio_id=g.municipio.id).first()
        if user_backup:
            prof = ProfissionalAEE.query.filter_by(usuario_id=user_backup.id).first()
            if not prof:
                prof = ProfissionalAEE(
                    municipio_id=g.municipio.id,
                    usuario_id=user_backup.id,
                    nome=user_backup.nome,
                    email=user_backup.email,
                    cargo=user_backup.cargo or 'Professor(a) de AEE (SRM)',
                    escola_polo=user_backup.escola_polo or 'Sede / Secretaria',
                    cpf=user_backup.cpf,
                    telefone=user_backup.telefone,
                    ativo=user_backup.ativo
                )
                db.session.add(prof)
                db.session.flush()
    if not prof:
        abort(404)

    nome = request.form.get('nome', '').strip()
    cargo = request.form.get('cargo', '').strip() or prof.cargo
    escola_polo = request.form.get('escola_polo', '').strip() or 'Sede da Secretaria de Educação'
    cpf = request.form.get('cpf', '').strip()
    telefone = request.form.get('telefone', '').strip()
    email = request.form.get('email', '').strip().lower()
    habilitar_login = request.form.get('habilitar_login') in ['on', 'true', '1', True]
    nova_senha = request.form.get('nova_senha', '').strip()
    perfil = request.form.get('perfil') or MAPA_CARGO_PERFIL.get(cargo, 'professor')

    prof.nome = nome
    prof.cargo = cargo
    prof.escola_polo = escola_polo
    prof.cpf = cpf
    prof.telefone = telefone
    prof.email = email if email else None

    if prof.usuario_id:
        user = Usuario.query.get(prof.usuario_id)
        if user:
            if email and email != user.email:
                outro = Usuario.query.filter(Usuario.email == email, Usuario.id != user.id).first()
                if outro:
                    flash(f"O e-mail '{email}' pertence a outro usuário.", "erro")
                    return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))
            user.nome = nome
            if email: user.email = email
            user.perfil = perfil
            user.cpf = cpf
            user.telefone = telefone
            user.cargo = cargo
            user.escola_polo = escola_polo
            if nova_senha:
                user.set_senha(nova_senha)
    elif habilitar_login and email:
        outro = Usuario.query.filter_by(email=email).first()
        if outro and outro.municipio_id == g.municipio.id:
            prof.usuario_id = outro.id
            outro.nome = nome
            outro.perfil = perfil
            outro.cpf = cpf
            outro.telefone = telefone
            outro.cargo = cargo
            outro.escola_polo = escola_polo
            if nova_senha:
                outro.set_senha(nova_senha)
        elif not outro:
            novo_u = Usuario(
                municipio_id=g.municipio.id,
                nome=nome,
                email=email,
                perfil=perfil,
                cpf=cpf,
                telefone=telefone,
                cargo=cargo,
                escola_polo=escola_polo,
                senha_provisoria=True,
                ativo=prof.ativo
            )
            novo_u.set_senha(nova_senha if nova_senha else 'Mudar@123')
            db.session.add(novo_u)
            db.session.flush()
            prof.usuario_id = novo_u.id

    db.session.commit()
    flash(f"Cadastro do profissional '{nome}' atualizado com sucesso!", "sucesso")
    return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))

@core_bp.route('/profissionais/<int:id>/resetar-senha', methods=['POST'])
@core_bp.route('/usuarios/<int:id>/resetar-senha', methods=['POST'])
@login_required
def resetar_senha_profissional(id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
    from app.models import ProfissionalAEE, Usuario
    from app import db
    from flask import flash

    prof = ProfissionalAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first()
    nova_senha = request.form.get('nova_senha', '').strip()
    if not nova_senha:
        flash("Informe a nova senha!", "erro")
        return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))

    if prof and prof.usuario_id:
        user = Usuario.query.get(prof.usuario_id)
        if user:
            user.set_senha(nova_senha)
            user.senha_provisoria = True
            db.session.commit()
            flash(f"Senha de '{prof.nome}' redefinida com sucesso!", "sucesso")
            return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))
    elif prof and prof.email:
        perfil = MAPA_CARGO_PERFIL.get(prof.cargo, 'professor')
        novo_u = Usuario(
            municipio_id=g.municipio.id,
            nome=prof.nome,
            email=prof.email,
            perfil=perfil,
            cpf=prof.cpf,
            telefone=prof.telefone,
            cargo=prof.cargo,
            escola_polo=prof.escola_polo,
            senha_provisoria=True,
            ativo=prof.ativo
        )
        novo_u.set_senha(nova_senha)
        db.session.add(novo_u)
        db.session.flush()
        prof.usuario_id = novo_u.id
        db.session.commit()
        flash(f"Conta de acesso criada e senha definida para '{prof.nome}'!", "sucesso")
        return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))

    flash("Este profissional não possui e-mail cadastrado para login. Edite o cadastro e informe um e-mail.", "erro")
    return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))

@core_bp.route('/profissionais/<int:id>/toggle-status')
@core_bp.route('/usuarios/<int:id>/toggle-status')
@login_required
def toggle_status_profissional(id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
    from app.models import ProfissionalAEE, Usuario
    from app import db
    from flask import flash

    prof = ProfissionalAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first()
    if prof:
        prof.ativo = not prof.ativo
        prof.status = 'Ativo' if prof.ativo else 'Suspenso'
        if prof.usuario_id:
            u = Usuario.query.get(prof.usuario_id)
            if u:
                u.ativo = prof.ativo
        db.session.commit()
        status_txt = "ativado" if prof.ativo else "suspenso"
        flash(f"Profissional '{prof.nome}' foi {status_txt}!", "sucesso")
    return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))

@core_bp.route('/profissionais/<int:id>/excluir', methods=['POST', 'GET'])
@core_bp.route('/usuarios/<int:id>/excluir', methods=['POST', 'GET'])
@login_required
def excluir_profissional(id):
    if current_user.perfil not in ['secretaria', 'superadmin']:
        abort(403)
    from app.models import ProfissionalAEE, Usuario
    from app import db
    from flask import flash

    prof = ProfissionalAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first()
    if prof:
        nome_p = prof.nome
        if prof.usuario_id and prof.usuario_id == current_user.id:
            flash("Você não pode excluir sua própria conta de usuário logada!", "erro")
            return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))
        if prof.usuario_id:
            u = Usuario.query.get(prof.usuario_id)
            if u and u.perfil != 'superadmin':
                db.session.delete(u)
        db.session.delete(prof)
        db.session.commit()
        flash(f"Profissional '{nome_p}' removido do quadro municipal com sucesso.", "sucesso")
    return redirect(url_for('core.gerenciar_profissionais', municipio_slug=g.municipio.slug))

# -------------------------------------------------------------------------
# PORTAL DA FAMÍLIA / RESPONSÁVEL (Art. 28 LBI)
# -------------------------------------------------------------------------
@core_bp.route('/familia/dashboard')
@login_required
def familia_dashboard():
    from app.models import (
        Aluno, Pei, ComunicacaoAEE, AtendimentoAee, TransporteAlunado,
        AgendaAEE, MensagemFamilia, ConquistaEstudante
    )
    from flask import flash
    
    aluno_ativo = None
    
    # 1. Usuário com perfil 'familia' (Acesso da Família restrito 100% ao seu próprio estudante)
    if current_user.perfil == 'familia':
        # Prioridade 1: ID da sessão gravado no login da família
        fam_aluno_id = session.get('familia_aluno_id')
        if fam_aluno_id:
            aluno_ativo = Aluno.query.filter_by(id=fam_aluno_id, municipio_id=g.municipio.id).first()
        
        # Prioridade 2: Vínculo direto de responsavel_id com o usuário logado
        if not aluno_ativo:
            aluno_ativo = Aluno.query.filter_by(responsavel_id=current_user.id, municipio_id=g.municipio.id).first()
            
        # Prioridade 3: Pela matrícula extraída do e-mail 'familia.<matricula>@gestoor.local'
        if not aluno_ativo and current_user.email:
            matricula_temp = current_user.email.replace('familia.', '').replace('@gestoor.local', '')
            aluno_ativo = Aluno.query.filter_by(matricula=matricula_temp, municipio_id=g.municipio.id).first()
            
        if aluno_ativo:
            session['familia_aluno_id'] = aluno_ativo.id
            if aluno_ativo.responsavel_id != current_user.id:
                aluno_ativo.responsavel_id = current_user.id
                db.session.commit()
        else:
            flash("Nenhum estudante vinculado ao seu cadastro familiar foi localizado.", "erro")
            return redirect(url_for('auth.acesso_rapido_familia', municipio_slug=g.municipio.slug))
            
    # 2. Usuário da rede escolar (Secretaria, Diretor, Professor, Especialista AEE) visualizando o portal de um aluno
    else:
        aluno_selecionado_id = request.args.get('aluno_id', type=int)
        if aluno_selecionado_id:
            aluno_ativo = Aluno.query.filter_by(id=aluno_selecionado_id, municipio_id=g.municipio.id).first_or_404()
        else:
            aluno_ativo = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).first()
            
    if not aluno_ativo:
        flash("Estudante não localizado.", "erro")
        return redirect(url_for('core.dashboard', municipio_slug=g.municipio.slug))

    # A lista enviada para o template contém ESTRITAMENTE o estudante ativo (sem vazar outros alunos)
    alunos = [aluno_ativo]

    pei_atual = Pei.query.filter_by(aluno_id=aluno_ativo.id).order_by(Pei.id.desc()).first()
    
    # Comunicados estritamente deste estudante no município
    try:
        comunicacoes = ComunicacaoAEE.query.filter_by(
            aluno_id=aluno_ativo.id,
            municipio_id=g.municipio.id
        ).order_by(ComunicacaoAEE.id.desc()).all()
    except Exception:
        comunicacoes = []

    try:
        atendimentos_aee = AtendimentoAee.query.filter_by(aluno_id=aluno_ativo.id).order_by(AtendimentoAee.data_atendimento.desc(), AtendimentoAee.id.desc()).all()
    except Exception:
        atendimentos_aee = []

    try:
        agenda_horarios = AgendaAEE.query.filter_by(aluno_id=aluno_ativo.id, ativo=True).order_by(AgendaAEE.id.desc()).all()
    except Exception:
        agenda_horarios = []

    try:
        transporte = TransporteAlunado.query.filter_by(aluno_id=aluno_ativo.id).first()
    except Exception:
        transporte = None

    try:
        conquistas = ConquistaEstudante.query.filter_by(aluno_id=aluno_ativo.id).order_by(ConquistaEstudante.data_registro.desc()).all()
    except Exception:
        conquistas = []

    try:
        mensagens = MensagemFamilia.query.filter_by(aluno_id=aluno_ativo.id).order_by(MensagemFamilia.data_envio.desc()).all()
    except Exception:
        mensagens = []

    sessoes_feitas = [s for s in atendimentos_aee if getattr(s, 'compareceu', False) or getattr(s, 'frequencia', False)]
    total_realizadas = len(sessoes_feitas)
    total_faltas = len(atendimentos_aee) - total_realizadas
    taxa_frequencia = int((total_realizadas / len(atendimentos_aee) * 100)) if atendimentos_aee else 100
    comunicados_novos = sum(1 for c in comunicacoes if not getattr(c, 'ciencia_familia', False))

    proximo_atendimento = agenda_horarios[0] if agenda_horarios else None

    return render_template(
        'familia/dashboard.html',
        alunos=alunos,
        aluno_ativo=aluno_ativo,
        pei_atual=pei_atual,
        comunicacoes=comunicacoes,
        atendimentos_aee=atendimentos_aee,
        agenda_horarios=agenda_horarios,
        conquistas=conquistas,
        mensagens=mensagens,
        transporte=transporte,
        total_realizadas=total_realizadas,
        total_faltas=total_faltas,
        taxa_frequencia=taxa_frequencia,
        comunicados_novos=comunicados_novos,
        proximo_atendimento=proximo_atendimento
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

    if current_user.perfil == 'familia':
        fam_aluno_id = session.get('familia_aluno_id')
        if fam_aluno_id and pei.aluno_id != fam_aluno_id:
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
    if comunicacao.municipio_id != g.municipio.id:
        abort(403)

    if current_user.perfil == 'familia':
        fam_aluno_id = session.get('familia_aluno_id')
        if fam_aluno_id and comunicacao.aluno_id and comunicacao.aluno_id != fam_aluno_id:
            abort(403)

    comunicacao.ciencia_familia = True
    comunicacao.ciencia_data = datetime.utcnow()
    obs = request.form.get('observacoes_familia', '').strip()
    if obs:
        comunicacao.observacoes_familia = obs

    db.session.commit()
    flash("Confirmação de leitura e observações registradas com sucesso!", "sucesso")
    alvo_aluno_id = request.form.get('aluno_id') or comunicacao.aluno_id
    return redirect(url_for('core.familia_dashboard', municipio_slug=g.municipio.slug, aluno_id=alvo_aluno_id))

@core_bp.route('/familia/aluno/<int:aluno_id>/enviar-mensagem', methods=['POST'])
@login_required
def familia_enviar_mensagem(aluno_id):
    from app.models import Aluno, MensagemFamilia
    from app import db
    from datetime import datetime
    from flask import flash

    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    if current_user.perfil == 'familia':
        fam_aluno_id = session.get('familia_aluno_id')
        if fam_aluno_id and aluno.id != fam_aluno_id:
            abort(403)

    assunto = request.form.get('assunto', '').strip() or 'Mensagem da Família'
    texto = request.form.get('mensagem', '').strip()

    if not texto:
        flash("A mensagem não pode ser vazia.", "erro")
        return redirect(url_for('core.familia_dashboard', municipio_slug=g.municipio.slug, aluno_id=aluno.id))

    nova_msg = MensagemFamilia(
        municipio_id=g.municipio.id,
        aluno_id=aluno.id,
        remetente_tipo='familia',
        remetente_nome=current_user.nome or f"Família de {aluno.nome}",
        destinatario_nome="Equipe Escolar / AEE",
        assunto=assunto,
        mensagem=texto,
        data_envio=datetime.utcnow(),
        lida=False
    )
    db.session.add(nova_msg)
    db.session.commit()
    flash("Mensagem enviada com sucesso para a equipe escolar!", "sucesso")
    return redirect(url_for('core.familia_dashboard', municipio_slug=g.municipio.slug, aluno_id=aluno.id))

@core_bp.route('/familia/aluno/<int:aluno_id>/notificar-ausencia', methods=['POST'])
@login_required
def familia_notificar_ausencia(aluno_id):
    from app.models import Aluno, ComunicacaoAEE, MensagemFamilia
    from app import db
    from datetime import datetime
    from flask import flash

    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    if current_user.perfil == 'familia':
        fam_aluno_id = session.get('familia_aluno_id')
        if fam_aluno_id and aluno.id != fam_aluno_id:
            abort(403)

    data_str = request.form.get('data_ausencia')
    motivo = request.form.get('motivo_ausencia', '').strip() or 'Imprevisto Familiar / Consulta Médica'
    detalhes = request.form.get('detalhes', '').strip()

    texto_msg = f"Aviso de Ausência/Falta em {data_str}. Motivo: {motivo}. Observações: {detalhes or 'Sem observações adicionais.'}"

    nova_msg = MensagemFamilia(
        municipio_id=g.municipio.id,
        aluno_id=aluno.id,
        remetente_tipo='familia',
        remetente_nome=current_user.nome or f"Família de {aluno.nome}",
        destinatario_nome="Profissional da Sala de Recursos / AEE",
        assunto=f"Aviso de Ausência: {aluno.nome} ({data_str or 'Próxima Sessão'})",
        mensagem=texto_msg,
        data_envio=datetime.utcnow(),
        lida=False
    )
    db.session.add(nova_msg)
    db.session.commit()
    flash("Aviso de ausência registrado com sucesso! A equipe escolar foi notificada.", "sucesso")
    return redirect(url_for('core.familia_dashboard', municipio_slug=g.municipio.slug, aluno_id=aluno.id))


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