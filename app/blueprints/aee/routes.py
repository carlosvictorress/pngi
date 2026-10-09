import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Municipio, Aluno, ProfissionalAEE, PlanoAEE, 
    AgendaAEE, EvolucaoAEE, DocumentoAEE, EncaminhamentoAEE, Escola,
    AtendimentoAee, ListaEsperaAEE
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


# =========================================================================
# 7. MÓDULO EXCLUSIVO: SALA DE RECURSOS / AEE (PRONTUÁRIO & ACOMPANHAMENTO)
# =========================================================================
@aee_bp.route('/sala-recursos')
@login_required
def sala_recursos():
    """Painel Geral da Sala de AEE com dados escolares, diagnósticos e métricas de sessões."""
    busca = request.args.get('busca', '').strip()
    escola_id = request.args.get('escola_id', type=int)
    filtro_diag = request.args.get('filtro_diag', '') # 'cid', 'investigacao', 'todos'

    query = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True)

    if busca:
        query = query.filter(
            (Aluno.nome.ilike(f"%{busca}%")) | 
            (Aluno.cpf.ilike(f"%{busca}%")) | 
            (Aluno.matricula.ilike(f"%{busca}%"))
        )
    if escola_id:
        query = query.filter(Aluno.escola_id == escola_id)
    if filtro_diag == 'cid':
        query = query.filter(Aluno.cid.isnot(None), Aluno.cid != '')
    elif filtro_diag == 'investigacao':
        query = query.filter(Aluno.em_investigacao == True)

    alunos = query.order_by(Aluno.nome).all()
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()

    # Cálculo dos dados de acompanhamento para cada aluno
    dados_alunos = []
    total_sessoes_geral = 0
    total_investigacao = 0

    for al in alunos:
        sessoes = AtendimentoAee.query.filter_by(aluno_id=al.id).order_by(AtendimentoAee.data_atendimento.desc()).all()
        sessoes_realizadas = [s for s in sessoes if s.compareceu or s.frequencia]
        faltas = [s for s in sessoes if not (s.compareceu or s.frequencia)]
        
        total_sessoes_geral += len(sessoes_realizadas)
        if al.em_investigacao:
            total_investigacao += 1

        dados_alunos.append({
            'aluno': al,
            'total_realizadas': len(sessoes_realizadas),
            'total_faltas': len(faltas),
            'total_agendadas': len(sessoes),
            'taxa_presenca': int((len(sessoes_realizadas) / len(sessoes) * 100)) if sessoes else 100,
            'ultima_sessao': sessoes[0] if sessoes else None
        })

    # Estatísticas da Fila de Espera
    total_espera = ListaEsperaAEE.query.filter_by(municipio_id=g.municipio.id, status='Aguardando Vaga').count()

    return render_template(
        'aee/sala_recursos.html',
        dados_alunos=dados_alunos,
        escolas=escolas,
        total_atendidos=len(alunos),
        total_sessoes_geral=total_sessoes_geral,
        total_investigacao=total_investigacao,
        total_espera=total_espera,
        busca=busca,
        escola_id=escola_id,
        filtro_diag=filtro_diag
    )


@aee_bp.route('/aluno/<int:aluno_id>/prontuario')
@login_required
def prontuario_aluno_aee(aluno_id):
    """
    Prontuário Individual do Aluno na Sala de AEE.
    Apresenta dados pessoais completos, pais, endereço, escola, série, CID ou investigação,
    quantas sessões já foram realizadas e o histórico com o que foi feito e como foi feito.
    """
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    
    # Histórico de Atendimentos na Sala de Recursos
    sessoes = AtendimentoAee.query.filter_by(aluno_id=aluno.id).order_by(AtendimentoAee.data_atendimento.desc(), AtendimentoAee.id.desc()).all()
    sessoes_realizadas = [s for s in sessoes if s.compareceu or s.frequencia]
    faltas = [s for s in sessoes if not (s.compareceu or s.frequencia)]
    
    total_realizadas = len(sessoes_realizadas)
    total_faltas = len(faltas)
    taxa_presenca = int((total_realizadas / len(sessoes) * 100)) if sessoes else 100

    profissionais = ProfissionalAEE.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(ProfissionalAEE.nome).all()

    return render_template(
        'aee/prontuario_aluno.html',
        aluno=aluno,
        sessoes=sessoes,
        total_realizadas=total_realizadas,
        total_faltas=total_faltas,
        taxa_presenca=taxa_presenca,
        profissionais=profissionais
    )


@aee_bp.route('/aluno/<int:aluno_id>/sessao/nova', methods=['POST'])
@login_required
def lancar_sessao_aee(aluno_id):
    """Registra uma nova sessão de atendimento na Sala de AEE."""
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()

    data_str = request.form.get('data_atendimento')
    try:
        data_atendimento = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else datetime.utcnow().date()
    except Exception:
        data_atendimento = datetime.utcnow().date()

    compareceu = request.form.get('compareceu') == 'true' or request.form.get('compareceu') == '1' or 'compareceu' in request.form
    o_que_foi_feito = request.form.get('o_que_foi_feito', '').strip()
    como_foi_feito = request.form.get('como_foi_feito', '').strip()
    recursos_utilizados = request.form.get('recursos_utilizados', '').strip()
    justificativa_falta = request.form.get('justificativa_falta', '').strip()
    profissional_id = request.form.get('profissional_id', type=int)

    prof_nome = current_user.nome
    if profissional_id:
        p_obj = ProfissionalAEE.query.get(profissional_id)
        if p_obj:
            prof_nome = p_obj.nome

    nova_sessao = AtendimentoAee(
        municipio_id=g.municipio.id,
        aluno_id=aluno.id,
        data_atendimento=data_atendimento,
        compareceu=compareceu,
        frequencia=compareceu,
        o_que_foi_feito=o_que_foi_feito,
        como_foi_feito=como_foi_feito,
        recursos_utilizados=recursos_utilizados,
        justificativa_falta=justificativa_falta,
        plano_sessao=o_que_foi_feito,
        evolucao_registro=como_foi_feito,
        profissional_id=current_user.id,
        profissional_nome=prof_nome
    )
    db.session.add(nova_sessao)
    db.session.commit()

    flash(f"Sessão de atendimento de {aluno.nome} registrada com sucesso!", "sucesso")
    return redirect(url_for('aee.prontuario_aluno_aee', municipio_slug=g.municipio.slug, aluno_id=aluno.id))


@aee_bp.route('/aluno/<int:aluno_id>/atualizar-dados-aee', methods=['POST'])
@login_required
def atualizar_dados_aee(aluno_id):
    """Atualização rápida dos dados pessoais e clínicos do estudante diretamente no prontuário AEE."""
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()

    aluno.nome = request.form.get('nome', aluno.nome).strip()
    aluno.cpf = request.form.get('cpf', aluno.cpf).strip()
    aluno.data_nascimento = request.form.get('data_nascimento', aluno.data_nascimento)
    aluno.nome_mae = request.form.get('nome_mae', aluno.nome_mae).strip()
    aluno.nome_pai = request.form.get('nome_pai', aluno.nome_pai).strip()
    aluno.endereco = request.form.get('endereco', aluno.endereco).strip()
    aluno.bairro = request.form.get('bairro', aluno.bairro).strip()
    aluno.turma = request.form.get('turma', aluno.turma).strip()
    aluno.etapa_ensino = request.form.get('etapa_ensino', aluno.etapa_ensino).strip()
    
    # Diagnóstico e Investigação
    aluno.cid = request.form.get('cid', aluno.cid).strip()
    aluno.em_investigacao = request.form.get('em_investigacao') == 'on' or request.form.get('em_investigacao') == 'true'
    aluno.hipotese_diagnostica = request.form.get('hipotese_diagnostica', aluno.hipotese_diagnostica).strip()
    if request.form.get('tipo_deficiencia'):
        aluno.tipo_deficiencia = request.form.get('tipo_deficiencia')

    db.session.commit()
    flash(f"Ficha cadastral de {aluno.nome} atualizada no prontuário da Sala de Recursos!", "sucesso")
    return redirect(url_for('aee.prontuario_aluno_aee', municipio_slug=g.municipio.slug, aluno_id=aluno.id))


# =========================================================================
# 8. MÓDULO LISTA DE ESPERA DA SALA DE RECURSOS / AEE
# =========================================================================
@aee_bp.route('/lista-espera', methods=['GET', 'POST'])
@login_required
def lista_espera():
    """Gerenciamento da Fila e Lista de Espera da Sala de Recursos Multifuncionais / AEE."""
    if request.method == 'POST':
        nome = request.form.get('nome_completo', '').strip()
        data_nasc = request.form.get('data_nascimento', '').strip()
        cpf = request.form.get('cpf', '').strip()
        telefone = request.form.get('telefone', '').strip()
        nome_resp = request.form.get('nome_responsavel', '').strip()
        escola_origem = request.form.get('escola_origem', '').strip()
        ano_serie = request.form.get('ano_serie', '').strip()
        endereco = request.form.get('endereco', '').strip()
        diag = request.form.get('diagnostico_hipotese', '').strip()
        em_invest = request.form.get('em_investigacao') == 'on' or request.form.get('em_investigacao') == 'true'
        prioridade = request.form.get('prioridade', 'Média')
        turno = request.form.get('turno_pretendido', 'Contraturno')
        obs = request.form.get('observacoes_triagem', '').strip()

        if not nome or not telefone:
            flash("Nome completo e telefone para contato são obrigatórios!", "erro")
        else:
            novo_candidato = ListaEsperaAEE(
                municipio_id=g.municipio.id,
                nome_completo=nome,
                data_nascimento=data_nasc,
                cpf=cpf,
                telefone=telefone,
                nome_responsavel=nome_resp,
                escola_origem=escola_origem,
                ano_serie=ano_serie,
                endereco=endereco,
                diagnostico_hipotese=diag,
                em_investigacao=em_invest,
                prioridade=prioridade,
                turno_pretendido=turno,
                observacoes_triagem=obs,
                status='Aguardando Vaga'
            )
            db.session.add(novo_candidato)
            db.session.commit()
            flash(f"Estudante '{nome}' inserido com sucesso na lista de espera do AEE!", "sucesso")
            return redirect(url_for('aee.lista_espera', municipio_slug=g.municipio.slug))

    filtro_status = request.args.get('status', '')
    filtro_prioridade = request.args.get('prioridade', '')
    busca = request.args.get('busca', '').strip()

    query = ListaEsperaAEE.query.filter_by(municipio_id=g.municipio.id)

    if filtro_status:
        query = query.filter(ListaEsperaAEE.status == filtro_status)
    if filtro_prioridade:
        query = query.filter(ListaEsperaAEE.prioridade == filtro_prioridade)
    if busca:
        query = query.filter(
            (ListaEsperaAEE.nome_completo.ilike(f"%{busca}%")) | 
            (ListaEsperaAEE.cpf.ilike(f"%{busca}%")) | 
            (ListaEsperaAEE.telefone.ilike(f"%{busca}%"))
        )

    # Ordenação por prioridade (Alta primeiro) e data
    candidatos = query.order_by(
        db.case((ListaEsperaAEE.prioridade == 'Alta / Urgente', 1), (ListaEsperaAEE.prioridade == 'Média', 2), else_=3),
        ListaEsperaAEE.data_solicitacao.asc()
    ).all()

    total_espera = ListaEsperaAEE.query.filter_by(municipio_id=g.municipio.id, status='Aguardando Vaga').count()
    total_chamados = ListaEsperaAEE.query.filter_by(municipio_id=g.municipio.id, status='Chamado/Convocado').count()
    total_matriculados = ListaEsperaAEE.query.filter_by(municipio_id=g.municipio.id, status='Matriculado no AEE').count()

    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()

    return render_template(
        'aee/lista_espera.html',
        candidatos=candidatos,
        total_espera=total_espera,
        total_chamados=total_chamados,
        total_matriculados=total_matriculados,
        filtro_status=filtro_status,
        filtro_prioridade=filtro_prioridade,
        busca=busca,
        escolas=escolas
    )


@aee_bp.route('/lista-espera/<int:id>/status', methods=['POST'])
@login_required
def alterar_status_espera(id):
    """Atualiza o status de um candidato na lista de espera (ex: Chamado, Em Triagem, etc.)."""
    candidato = ListaEsperaAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    novo_status = request.form.get('novo_status')
    if novo_status:
        candidato.status = novo_status
        db.session.commit()
        flash(f"Status de '{candidato.nome_completo}' alterado para '{novo_status}'!", "sucesso")
    return redirect(url_for('aee.lista_espera', municipio_slug=g.municipio.slug))


@aee_bp.route('/lista-espera/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_espera(id):
    """Remove um registro da lista de espera."""
    candidato = ListaEsperaAEE.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    nome = candidato.nome_completo
    db.session.delete(candidato)
    db.session.commit()
    flash(f"Registro de '{nome}' removido da lista de espera.", "sucesso")
    return redirect(url_for('aee.lista_espera', municipio_slug=g.municipio.slug))