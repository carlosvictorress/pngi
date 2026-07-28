import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Municipio, Aluno, ProfissionalAEE, PlanoAEE, 
    AgendaAEE, EvolucaoAEE, DocumentoAEE, EncaminhamentoAEE, Escola
)

aee_bp = Blueprint('aee', __name__)

@aee_bp.url_value_preprocessor
def get_municipio_slug(endpoint, values):
    """Captura automaticamente o <municipio_slug> da URL e injeta no contexto g."""
    if values and 'municipio_slug' in values:
        g.municipio_slug = values.pop('municipio_slug')
        g.municipio = Municipio.query.filter_by(slug=g.municipio_slug).first()
    if not g.municipio:
        abort(404)

# =========================================================================
# 1. GERENCIAMENTO DA EQUIPE TÉCNICA E NAVEGAÇÃO POR ABAS CATEGORIZADAS
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
        flash("Especialista portariado e alocado com sucesso na rede municipal!", "sucesso")
        return redirect(url_for('aee.painel_aee', municipio_slug=g.municipio.slug))

    # Filtro por Busca e Categoria
    busca = request.args.get('busca', '').strip()
    query_prof = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True)

    if busca:
        query_prof = query_prof.filter((ProfissionalAEE.nome.ilike(f"%{busca}%")) | (ProfissionalAEE.cpf.ilike(f"%{busca}%")) | (ProfissionalAEE.escola_polo.ilike(f"%{busca}%")))

    profissionais = query_prof.order_by(ProfissionalAEE.nome).all()

    # Divisão por Categorias de Especialistas (Limpo e Organizado)
    professores_aee = [p for p in profissionais if p.cargo == 'Professor AEE']
    equipe_multidisciplinar = [p for p in profissionais if p.cargo in ['Psicopedagogo', 'Psicólogo Escolar', 'Fonoaudiólogo', 'Terapeuta Ocupacional', 'Assistente Social']]
    profissionais_apoio = [p for p in profissionais if p.cargo in ['Profissional de Apoio Escolar', 'Cuidador', 'Auxiliar de Inclusão']]
    interpretes_libras = [p for p in profissionais if p.cargo in ['Tradutor e Intérprete de Libras', 'Guia-Intérprete']]

    total_geral = len(profissionais)
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()

    return render_template(
        'aee/painel_aee.html', 
        profissionais=profissionais,
        professores_aee=professores_aee,
        equipe_multidisciplinar=equipe_multidisciplinar,
        profissionais_apoio=profissionais_apoio,
        interpretes_libras=interpretes_libras,
        total_geral=total_geral,
        busca=busca,
        escolas=escolas
    )

@aee_bp.route('/profissional/<int:id>')
@login_required
def perfil_profissional(id):
    """Ficha 360º dedicada do profissional do AEE."""
    p = ProfissionalAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()

    planos = PlanoAEE.query.filter_by(profissional_id=p.id).order_by(PlanoAEE.id.desc()).all()
    agenda = AgendaAEE.query.filter_by(profissional_id=p.id, ativo=True).all()
    evolucoes = EvolucaoAEE.query.filter_by(profissional_id=p.id, ativo=True).order_by(EvolucaoAEE.data_atendimento.desc()).all()
    encaminhamentos = EncaminhamentoAEE.query.filter_by(profissional_id=p.id).order_by(EncaminhamentoAEE.id.desc()).all()

    # Alunos únicos atendidos por este profissional
    alunos_ids = set([h.aluno_id for h in agenda] + [pl.aluno_id for pl in planos] + [ev.aluno_id for ev in evolucoes])
    alunos_atendidos = Aluno.query.filter(Aluno.id.in_(alunos_ids)).all() if alunos_ids else []

    return render_template(
        'aee/perfil_profissional.html',
        profissional=p,
        planos=planos,
        agenda=agenda,
        evolucoes=evolucoes,
        encaminhamentos=encaminhamentos,
        alunos_atendidos=alunos_atendidos
    )

@aee_bp.route('/excluir/<int:id>', methods=['GET'])
@login_required
def excluir_profissional(id):
    p = ProfissionalAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    p.ativo = False
    p.status = 'Afastado'
    db.session.commit()
    flash("Profissional removido das folhas de alocações vigentes.", "warning")
    return redirect(url_for('aee.painel_aee', municipio_slug=g.municipio.slug))

# =========================================================================
# 2. GUIAS DE ENCAMINHAMENTO PARA A REDE DE SAÚDE / SUS / CRAS
# =========================================================================
@aee_bp.route('/encaminhamentos', methods=['GET', 'POST'])
@login_required
def encaminhamentos_aee():
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        profissional_id = request.form.get('profissional_id')
        destino_rede = request.form.get('destino_rede')
        motivo_encaminhamento = request.form.get('motivo_encaminhamento')
        hipotese_observada = request.form.get('hipotese_observada')

        if not aluno_id or not destino_rede:
            flash("Indique o aluno e o destino da rede de atendimento (SUS/CRAS).", "erro")
            return redirect(url_for('aee.encaminhamentos_aee', municipio_slug=g.municipio.slug))

        novo_enc = EncaminhamentoAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id) if profissional_id else None,
            destino_rede=destino_rede,
            motivo_encaminhamento=motivo_encaminhamento,
            hipotese_observada=hipotese_observada,
            status='Pendente'
        )
        db.session.add(novo_enc)
        db.session.commit()
        flash(f"Guia de Encaminhamento para {destino_rede} emitida com sucesso!", "sucesso")
        return redirect(url_for('aee.encaminhamentos_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    encaminhamentos = EncaminhamentoAEE.query.filter_by(municipio_id=g.municipio.id).order_by(EncaminhamentoAEE.id.desc()).all()

    return render_template(
        'aee/encaminhamentos.html',
        alunos=alunos,
        profissionais=profissionais,
        encaminhamentos=encaminhamentos
    )

@aee_bp.route('/encaminhamentos/<int:id>/imprimir')
@login_required
def imprimir_encaminhamento(id):
    """Guia oficial de encaminhamento timbrada para o SUS/CRAS com campo de contrarreferência."""
    enc = EncaminhamentoAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    data_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M')
    return render_template('aee/imprimir_encaminhamento.html', enc=enc, data_emissao=data_emissao)

# =========================================================================
# 3. PLANOS PEDAGÓGICOS ANUAIS (PLANOS_AEE.HTML)
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
            flash("É obrigatório selecionar um aluno válido para o plano.", "erro")
            return redirect(url_for('aee.planos_aee', municipio_slug=g.municipio.slug))

        novo_plano = PlanoAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id) if profissional_id else None,
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
        flash("Prontuário Pedagógico de Atendimento Especializado publicado com sucesso!", "sucesso")
        return redirect(url_for('aee.planos_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    planos = PlanoAEE.query.filter_by(municipio_id=g.municipio.id).order_by(PlanoAEE.id.desc()).all()

    return render_template('aee/planos_aee.html', alunos=alunos, profissionais=profissionais, planos=planos)

# =========================================================================
# 4. GRADE DE HORÁRIOS E MAPA DE SALAS (AGENDA_AEE.HTML)
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
            flash("Selecione um aluno válido da lista para agendamento.", "erro")
            return redirect(url_for('aee.agenda_aee', municipio_slug=g.municipio.slug))

        novo_horario = AgendaAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id) if profissional_id else None,
            dia_semana=dia_semana,
            horario_inicio=horario_inicio,
            horario_fim=horario_fim,
            sala_recurso=sala_recurso,
            quantidade_sessoes=int(quantidade_sessoes)
        )
        db.session.add(novo_horario)
        db.session.commit()
        flash("Reserva de sala e grade horária fixada com sucesso!", "sucesso")
        return redirect(url_for('aee.agenda_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    agenda = AgendaAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).all()

    return render_template('aee/agenda_aee.html', alunos=alunos, profissionais=profissionais, agenda=agenda)

@aee_bp.route('/agenda/<int:id>/desativar', methods=['POST', 'GET'])
@login_required
def desativar_agendamento(id):
    agendamento = AgendaAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    agendamento.ativo = False
    agendamento.status = 'Cancelado'
    db.session.commit()
    flash("Agendamento removido da pauta com sucesso.", "sucesso")
    return redirect(url_for('aee.agenda_aee', municipio_slug=g.municipio.slug))

# =========================================================================
# 5. PRONTUÁRIO DE EVOLUÇÕES DIÁRIAS / PADRÃO SOAP (EVOLUCOES_AEE.HTML)
# =========================================================================
@aee_bp.route('/evolucoes', methods=['GET', 'POST'])
@login_required
def evolucoes_aee():
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        profissional_id = request.form.get('profissional_id')
        data_str = request.form.get('data_atendimento')
        
        comportamento_subjetivo = request.form.get('comportamento_subjetivo') 
        atividade_trabalhada = request.form.get('atividade_trabalhada')
        evolucao_observada = request.form.get('evolucao_observada')
        dificuldades_identificadas = request.form.get('dificuldades_identificadas')
        intervencoes_realizadas = request.form.get('intervencoes_realizadas')
        proximos_passos = request.form.get('proximos_passos')
        presenca = request.form.get('presenca', 'Presente')

        if not aluno_id:
            flash("Indique um aluno para registrar a evolução técnica.", "erro")
            return redirect(url_for('aee.evolucoes_aee', municipio_slug=g.municipio.slug))

        data_atendimento = datetime.strptime(data_str, '%Y-%m-%d').date()

        nova_ev = EvolucaoAEE(
            municipio_id=g.municipio.id,
            aluno_id=int(aluno_id),
            profissional_id=int(profissional_id) if profissional_id else None,
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
        flash("Diário de evolução (SOAP) lançado com sucesso no prontuário!", "sucesso")
        return redirect(url_for('aee.evolucoes_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    evolucoes = EvolucaoAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(EvolucaoAEE.data_atendimento.desc()).all()

    return render_template('aee/evolucoes_aee.html', alunos=alunos, profissionais=profissionais, evolucoes=evolucoes)

# =========================================================================
# 6. CONTROLE DIGITAL DE LAUDOS E PARECERES (DOCUMENTOS_AEE.HTML)
# =========================================================================
@aee_bp.route('/documentos', methods=['GET', 'POST'])
@login_required
def documentos_aee():
    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id')
        profissional_id = request.form.get('profissional_id')
        tipo_documento = request.form.get('tipo_documento')
        descricao = request.form.get('descricao')
        
        arquivo = request.files.get('arquivo')
        if not arquivo or arquivo.filename == '':
            flash("Erro: É obrigatório selecionar um arquivo PDF ou de Imagem para fazer o upload.", "erro")
            return redirect(url_for('aee.documentos_aee', municipio_slug=g.municipio.slug))

        if not aluno_id:
            flash("Selecione um aluno para vincular a peça pericial.", "erro")
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
        flash("Laudo/Peça técnica digitalizada e anexada ao prontuário do aluno com trilha de auditoria!", "sucesso")
        return redirect(url_for('aee.documentos_aee', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()
    documentos = DocumentoAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(DocumentoAEE.data_upload.desc()).all()

    return render_template('aee/documentos_aee.html', alunos=alunos, profissionais=profissionais, documentos=documentos)