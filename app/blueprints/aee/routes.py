import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Municipio, Aluno, ProfissionalAEE, PlanoAEE, 
    AgendaAEE, EvolucaoAEE, DocumentoAEE
)

aee_bp = Blueprint('aee', __name__)

@aee_bp.url_value_preprocessor
def get_municipio_slug(endpoint, values):
    """Captura automaticamente o <municipio_slug> da URL e injeta no contexto g."""
    if values and 'municipio_slug' in values:
        g.municipio = Municipio.query.filter_by(slug=values.pop('municipio_slug')).first()
    if not g.municipio:
        abort(404)

# =========================================================================
# 1. GERENCIAMENTO DA EQUIPE TÉCNICA (PAINEL_AEE.HTML)
# =========================================================================
@aee_bp.route('/', methods=['GET', 'POST'])
@login_required
def painel_aee():
    if request.method == 'POST':
        nome = request.form.get('nome')
        cpf = request.form.get('cpf')
        cargo = request.form.get('cargo')
        escola_polo = request.form.get('escola_polo')
        telefone = request.form.get('telefone')
        email = request.form.get('email')

        # Injeta o profissional atômico no banco isolado do município
        novo_p = ProfissionalAEE(
            municipio_id=g.municipio.id,
            nome=nome,
            cpf=cpf,
            cargo=cargo,
            escola_polo=escola_polo,
            telefone=telefone,
            email=email
        )
        db.session.add(novo_p)
        db.session.commit()
        flash("Especialista portariado e alocado com sucesso na rede municipal!", "success")
        return redirect(url_for('aee.painel_aee', municipio_slug=g.municipio.slug))

    # Métricas consolidadas por sub-grupos (Apenas Ativos - Soft Delete respeitado)
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    total_geral = len(profissionais)
    total_professores = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, cargo='Professor AEE', ativo=True).count()
    total_apoio = ProfissionalAEE.query.filter(
        ProfissionalAEE.municipio_id == g.municipio.id, 
        ProfissionalAEE.cargo != 'Professor AEE',
        ProfissionalAEE.ativo == True
    ).count()

    return render_template(
        'aee/painel_aee.html', 
        profissionais=profissionais,
        total_geral=total_geral,
        total_professores=total_professores,
        total_apoio=total_apoio
    )

@aee_bp.route('/excluir/<int:id>', methods=['GET'])
@login_required
def excluir_profissional(id):
    p = ProfissionalAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    p.ativo = False # Substituição para Soft Delete governamental
    p.status = 'Afastado'
    db.session.commit()
    flash("Profissional removido das folhas de alocações vigentes.", "warning")
    return redirect(url_for('aee.painel_aee', municipio_slug=g.municipio.slug))


# =========================================================================
# 2. EMISSÃO DE PLANOS PEDAGÓGICOS ANUAIS (PLANOS_AEE.HTML)
# =========================================================================
@aee_bp.route('/planos', methods=['GET', 'POST'])
@login_required
def planos_aee():
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        profissional_id = request.form.get('profissional_id')
        avaliacao_inicial = request.form.get('avaliacao_inicial')
        barreiras_identificadas = request.form.get('barreiras_identificadas')
        objetivos_gerais = request.form.get('objetivos_gerais')
        objetivos_especificos = request.form.get('objetivos_especificos')
        estrategias_pedagogicas = request.form.get('estrategias_pedagogicas')
        recursos_utilizados = request.form.get('recursos_utilizados')
        tecnologias_assistivas = request.form.get('tecnologias_assistivas')
        metas = request.form.get('metas')
        cronograma = request.form.get('cronograma')

        if not aluno_id:
            flash("Erro crítico: É obrigatório selecionar um aluno válido da lista por digitação.", "danger")
            return redirect(url_for('aee.planos_aee', municipio_slug=g.municipio.slug))

        novo_plano = PlanoAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id),
            avaliacao_inicial=avaliacao_inicial,
            barreiras_identificadas=barreiras_identificadas,
            objetivos_gerais=objetivos_gerais,
            objetivos_especificos=objetivos_especificos,
            estrategias_pedagogicas=estrategias_pedagogicas,
            recursos_utilizados=recursos_utilizados,
            tecnologias_assistivas=tecnologias_assistivas,
            metas=metas,
            cronograma=cronograma,
            status='Homologado'
        )
        db.session.add(novo_plano)
        db.session.commit()
        flash("Prontuário Pedagógico de Atendimento Especializado publicado com sucesso!", "success")
        return redirect(url_for('aee.planos_aee', municipio_slug=g.municipio.slug))

    # Carrega apenas entidades ativas
    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    planos = PlanoAEE.query.filter_by(municipio_id=g.municipio.id).order_by(PlanoAEE.id.desc()).all()

    return render_template('aee/planos_aee.html', alunos=alunos, profissionais=profissionais, planos=planos)


# =========================================================================
# 3. GRADE DE HORÁRIOS E MAPA DE SALAS (AGENDA_AEE.HTML)
# =========================================================================
@aee_bp.route('/agenda', methods=['GET', 'POST'])
@login_required
def agenda_aee():
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        profissional_id = request.form.get('profissional_id')
        dia_semana = request.form.get('dia_semana')
        horario_inicio = request.form.get('horario_inicio')
        horario_fim = request.form.get('horario_fim')
        sala_recurso = request.form.get('sala_recurso')
        quantidade_sessoes = request.form.get('quantidade_sessoes', 1)

        if not aluno_id:
            flash("Selecione um aluno válido da lista para homologar a agenda.", "danger")
            return redirect(url_for('aee.agenda_aee', municipio_slug=g.municipio.slug))

        novo_horario = AgendaAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id),
            dia_semana=dia_semana,
            horario_inicio=horario_inicio,
            horario_fim=horario_fim,
            sala_recurso=sala_recurso,
            quantidade_sessoes=int(quantidade_sessoes)
        )
        db.session.add(novo_horario)
        db.session.commit()
        flash("Reserva de sala e grade horária fixada com sucesso!", "success")
        return redirect(url_for('aee.agenda_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    agenda = AgendaAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).all()

    return render_template('aee/agenda_aee.html', alunos=alunos, profissionais=profissionais, agenda=agenda)

@aee_bp.route('/agenda/<int:id>/desativar', methods=['POST'])
@login_required
def desativar_agendamento(id):
    """Rota nova para cancelar horários na agenda via Soft Delete"""
    agendamento = AgendaAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    agendamento.ativo = False
    agendamento.status = 'Cancelado'
    db.session.commit()
    flash("Agendamento removido da pauta com sucesso.", "info")
    return redirect(url_for('aee.agenda_aee', municipio_slug=g.municipio.slug))


# =========================================================================
# 4. PRONTUÁRIO DE EVOLUÇÕES DIÁRIAS / PADRÃO SOAP (EVOLUCOES_AEE.HTML)
# =========================================================================
@aee_bp.route('/evolucoes', methods=['GET', 'POST'])
@login_required
def evolucoes_aee():
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        profissional_id = request.form.get('profissional_id')
        data_str = request.form.get('data_atendimento')
        
        # Injeção dos novos campos SOAP da nossa arquitetura
        comportamento_subjetivo = request.form.get('comportamento_subjetivo') 
        atividade_trabalhada = request.form.get('atividade_trabalhada')
        evolucao_observada = request.form.get('evolucao_observada')
        dificuldades_identificadas = request.form.get('dificuldades_identificadas')
        intervencoes_realizadas = request.form.get('intervencoes_realizadas')
        proximos_passos = request.form.get('proximos_passos')
        presenca = request.form.get('presenca', 'Presente')

        if not aluno_id:
            flash("Indique um aluno para registrar a evolução técnica.", "danger")
            return redirect(url_for('aee.evolucoes_aee', municipio_slug=g.municipio.slug))

        data_atendimento = datetime.strptime(data_str, '%Y-%m-%d').date()

        nova_ev = EvolucaoAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id),
            data_atendimento=data_atendimento,
            comportamento_subjetivo=comportamento_subjetivo,
            atividade_trabalhada=atividade_trabalhada,
            evolucao_observada=evolucao_observada,
            dificuldades_identificadas=dificuldades_identificadas,
            intervencoes_realizadas=intervencoes_realizadas,
            proximos_passos=proximos_passos,
            presenca=presenca
        )
        db.session.add(nova_ev)
        db.session.commit()
        flash("Diário de evolução (SOAP) lançado com sucesso no prontuário!", "success")
        return redirect(url_for('aee.evolucoes_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    evolucoes = EvolucaoAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(EvolucaoAEE.data_atendimento.desc()).all()

    return render_template('aee/evolucoes_aee.html', alunos=alunos, profissionais=profissionais, evolucoes=evolucoes)


# =========================================================================
# 5. CONTROLE DIGITAL DE LAUDOS E PARECERES (DOCUMENTOS_AEE.HTML)
# =========================================================================
@aee_bp.route('/documentos', methods=['GET', 'POST'])
@login_required
def documentos_aee():
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        profissional_id = request.form.get('profissional_id') # Faltava puxar quem assina o laudo
        tipo_documento = request.form.get('tipo_documento')
        descricao = request.form.get('descricao')
        
        arquivo = request.files.get('arquivo')
        if not arquivo or arquivo.filename == '':
            flash("Erro: É obrigatório selecionar um arquivo PDF ou de Imagem para fazer o upload.", "danger")
            return redirect(url_for('aee.documentos_aee', municipio_slug=g.municipio.slug))

        if not aluno_id:
            flash("Selecione um aluno para vincular a peça pericial.", "danger")
            return redirect(url_for('aee.documentos_aee', municipio_slug=g.municipio.slug))

        upload_folder = os.path.join('app', 'static', 'uploads', 'documentos')
        os.makedirs(upload_folder, exist_ok=True)
        
        filename = f"doc_{int(aluno_id)}_{int(datetime.utcnow().timestamp())}_{arquivo.filename}"
        arquivo.save(os.path.join(upload_folder, filename))
        url_arquivo = f"uploads/documentos/{filename}"

        novo_doc = DocumentoAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id) if profissional_id else None,
            tipo_documento=tipo_documento,
            descricao=descricao,
            url_arquivo=url_arquivo
        )
        db.session.add(novo_doc)
        db.session.commit()
        flash("Laudo/Peça técnica digitalizada e anexada ao prontuário do aluno com trilha de auditoria!", "success")
        return redirect(url_for('aee.documentos_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    documentos = DocumentoAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(DocumentoAEE.data_upload.desc()).all()

    return render_template('aee/documentos_aee.html', alunos=alunos, profissionais=profissionais, documentos=documentos)