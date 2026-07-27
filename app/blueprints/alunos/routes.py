from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Aluno, Escola, Pei, Paee, Municipio

alunos_bp = Blueprint('alunos', __name__)

@alunos_bp.url_value_preprocessor
def pull_slug(endpoint, values):
    if values:
        g.municipio_slug = values.pop('municipio_slug', None)

@alunos_bp.route('/', methods=['GET'])
@login_required
def listar():
    if not g.municipio:
        abort(404)
    # Lista apenas os alunos ativos
    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    return render_template('alunos/listar.html', alunos=alunos)

@alunos_bp.route('/api/buscar_cpf', methods=['GET'])
@login_required
def buscar_cpf():
    """
    Busca um aluno globalmente pelo CPF para facilitar transferências.
    """
    cpf = request.args.get('cpf')
    if not cpf:
        return jsonify({'error': 'CPF não fornecido'}), 400
    
    # Busca o aluno mais recente com esse CPF que esteja ativo
    aluno_origem = Aluno.query.filter_by(cpf=cpf, ativo=True).order_by(Aluno.criado_em.desc()).first()
    
    if not aluno_origem:
        return jsonify({'encontrado': False})
    
    # Formata a data de nascimento corretamente se existir
    data_nascimento_str = None
    if aluno_origem.data_nascimento:
        if isinstance(aluno_origem.data_nascimento, str):
            data_nascimento_str = aluno_origem.data_nascimento
        else:
            data_nascimento_str = aluno_origem.data_nascimento.strftime('%Y-%m-%d')
            
    # Se encontrou, retorna os dados, mas NÃO retorna a escola/matrícula antiga
    return jsonify({
        'encontrado': True,
        'dados': {
            'nome': aluno_origem.nome,
            'data_nascimento': data_nascimento_str,
            'sexo': aluno_origem.sexo,
            'raca_cor': aluno_origem.raca_cor,
            'naturalidade': aluno_origem.naturalidade,
            'nome_mae': aluno_origem.nome_mae,
            'nome_pai': aluno_origem.nome_pai,
            'recebe_bpc': aluno_origem.recebe_bpc,
            'codigo_inep': aluno_origem.codigo_inep,
            'tipo_deficiencia': aluno_origem.tipo_deficiencia,
            'cid': aluno_origem.cid,
            'possui_tea': aluno_origem.possui_tea,
            'possui_superdotacao': aluno_origem.possui_superdotacao,
            'medicacoes': aluno_origem.medicacoes,
            'restricoes_alimentares': aluno_origem.restricoes_alimentares,
            'acessibilidade_necessaria': aluno_origem.acessibilidade_necessaria,
            'necessita_transporte_adaptado': aluno_origem.necessita_transporte_adaptado,
            'cadeirante': aluno_origem.cadeirante,
            'necessita_acompanhante': aluno_origem.necessita_acompanhante,
            'possui_monitor_rota': aluno_origem.possui_monitor_rota,
            'contato_urgencia': aluno_origem.contato_urgencia,
            'municipio_origem_id': aluno_origem.municipio_id
        }
    })

@alunos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if not g.municipio:
        abort(404)
    if request.method == 'POST':
        cpf_submetido = request.form.get('cpf')
        
        # LOGICA DE TRANSFERÊNCIA: Desativa o aluno no município antigo caso ele exista lá
        if cpf_submetido:
            alunos_antigos = Aluno.query.filter(
                Aluno.cpf == cpf_submetido, 
                Aluno.municipio_id != g.municipio.id, 
                Aluno.ativo == True
            ).all()
            
            for antigo in alunos_antigos:
                antigo.ativo = False
        
        novo_aluno = Aluno(
            municipio_id=g.municipio.id,
            nome=request.form.get('nome'),
            cpf=cpf_submetido,
            data_nascimento=request.form.get('data_nascimento'),
            sexo=request.form.get('sexo'),
            raca_cor=request.form.get('raca_cor'),
            naturalidade=request.form.get('naturalidade'),
            nome_mae=request.form.get('nome_mae'),
            nome_pai=request.form.get('nome_pai'),
            recebe_bpc='recebe_bpc' in request.form,
            codigo_inep=request.form.get('codigo_inep'),
            matricula=request.form.get('matricula'),
            escola_id=request.form.get('escola_id') or None,
            turma=request.form.get('turma'),
            modalidade=request.form.get('modalidade'),
            etapa_ensino=request.form.get('etapa_ensino'),
            recurso_ledor='recurso_ledor' in request.form,
            recurso_transcritor='recurso_transcritor' in request.form,
            recurso_libras='recurso_libras' in request.form,
            recurso_ampliado='recurso_ampliado' in request.form,
            cid=request.form.get('cid') or None,
            tipo_deficiencia=request.form.get('tipo_deficiencia'),
            possui_tea='possui_tea' in request.form,
            possui_superdotacao='possui_superdotacao' in request.form,
            local_aee=request.form.get('local_aee'),
            necessita_apoio=request.form.get('necessita_apoio'),
            medicacoes=request.form.get('medicacoes'),
            restricoes_alimentares=request.form.get('restricoes_alimentares'),
            acessibilidade_necessaria=request.form.get('acessibilidade_necessaria'),
            necessita_transporte_adaptado='necessita_transporte_adaptado' in request.form,
            cadeirante='cadeirante' in request.form,
            necessita_acompanhante='necessita_acompanhante' in request.form,
            possui_monitor_rota='possui_monitor_rota' in request.form,
            contato_urgencia=request.form.get('contato_urgencia')
        )
        db.session.add(novo_aluno)
        db.session.commit()
        flash(f"Estudante {novo_aluno.nome} matriculado com sucesso!", "success")
        return redirect(url_for('alunos.listar', municipio_slug=g.municipio_slug))
    
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()
    return render_template('alunos/formulario.html', escolas=escolas)

@alunos_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_aluno(id):
    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    if request.method == 'POST':
        aluno.nome = request.form.get('nome')
        aluno.cpf = request.form.get('cpf')
        aluno.data_nascimento = request.form.get('data_nascimento')
        aluno.sexo = request.form.get('sexo')
        aluno.raca_cor = request.form.get('raca_cor')
        aluno.naturalidade = request.form.get('naturalidade')
        aluno.nome_mae = request.form.get('nome_mae')
        aluno.nome_pai = request.form.get('nome_pai')
        aluno.contato_urgencia = request.form.get('contato_urgencia')
        aluno.recebe_bpc = 'recebe_bpc' in request.form
        aluno.codigo_inep = request.form.get('codigo_inep')
        aluno.matricula = request.form.get('matricula')
        aluno.escola_id = request.form.get('escola_id')
        aluno.turma = request.form.get('turma')
        aluno.modalidade = request.form.get('modalidade')
        aluno.etapa_ensino = request.form.get('etapa_ensino')
        aluno.recurso_ledor = 'recurso_ledor' in request.form
        aluno.recurso_transcritor = 'recurso_transcritor' in request.form
        aluno.recurso_libras = 'recurso_libras' in request.form
        aluno.recurso_ampliado = 'recurso_ampliado' in request.form
        aluno.tipo_deficiencia = request.form.get('tipo_deficiencia')
        aluno.cid = request.form.get('cid')
        aluno.possui_tea = 'possui_tea' in request.form
        aluno.possui_superdotacao = 'possui_superdotacao' in request.form
        aluno.local_aee = request.form.get('local_aee')
        aluno.necessita_apoio = request.form.get('necessita_apoio')
        aluno.medicacoes = request.form.get('medicacoes')
        aluno.restricoes_alimentares = request.form.get('restricoes_alimentares')
        aluno.acessibilidade_necessaria = request.form.get('acessibilidade_necessaria')
        aluno.necessita_transporte_adaptado = 'necessita_transporte_adaptado' in request.form
        aluno.cadeirante = 'cadeirante' in request.form
        aluno.necessita_acompanhante = 'necessita_acompanhante' in request.form
        aluno.possui_monitor_rota = 'possui_monitor_rota' in request.form
        db.session.commit()
        flash(f"Prontuário de {aluno.nome} atualizado!", "success")
        return redirect(url_for('alunos.listar', municipio_slug=g.municipio_slug))
    
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()
    return render_template('alunos/editar.html', aluno=aluno, escolas=escolas)

@alunos_bp.route('/<int:aluno_id>/perfil', methods=['GET'])
@login_required
def perfil_aluno(aluno_id):
    from app.models import EstudoCaso, EvolucaoAEE, PlanoAEE
    
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    
    # Identifica todos os registros vinculados ao mesmo aluno em redes municipais
    condicoes = [Aluno.id == aluno.id]
    if aluno.cpf and aluno.cpf.strip():
        condicoes.append(Aluno.cpf == aluno.cpf.strip())
    if aluno.codigo_inep and aluno.codigo_inep.strip():
        condicoes.append(Aluno.codigo_inep == aluno.codigo_inep.strip())
        
    alunos_relacionados = Aluno.query.filter(db.or_(*condicoes)).all()
    ids_relacionados = [a.id for a in alunos_relacionados]
    
    peis = Pei.query.filter(Pei.aluno_id.in_(ids_relacionados)).order_by(Pei.criado_em.desc()).all()
    paees = Paee.query.filter(Paee.aluno_id.in_(ids_relacionados)).order_by(Paee.data_cadastro.desc()).all()
    planos_aee = PlanoAEE.query.filter(PlanoAEE.aluno_id.in_(ids_relacionados)).order_by(PlanoAEE.data_criacao.desc()).all()
    estudos_caso = EstudoCaso.query.filter(EstudoCaso.aluno_id.in_(ids_relacionados)).order_by(EstudoCaso.data_cadastro.desc()).all()
    evolucoes_aee = EvolucaoAEE.query.filter(EvolucaoAEE.aluno_id.in_(ids_relacionados)).order_by(EvolucaoAEE.data_atendimento.desc()).all()

    # Municipios para o modal de transferencia
    municipios_disponiveis = Municipio.query.filter(Municipio.id != g.municipio.id, Municipio.ativo == True).order_by(Municipio.nome).all()

    # Construção da Linha do Tempo Unificada
    linha_tempo = []
    
    for item in peis:
        is_outro_mun = (item.aluno.escola.municipio_id != g.municipio.id) if (item.aluno and item.aluno.escola) else False
        nome_mun = item.aluno.escola.municipio.nome if (is_outro_mun and item.aluno and item.aluno.escola and item.aluno.escola.municipio) else None
        
        linha_tempo.append({
            'tipo': 'pei',
            'categoria': f"PEI Inteligente {'(Histórico: ' + nome_mun + ')' if is_outro_mun else ''}",
            'icone': '🧠',
            'cor': 'indigo',
            'data': item.criado_em or item.atualizado_em,
            'titulo': f"PEI {item.ano_letivo} — {item.periodo_trimestre}º Trimestre",
            'subtitulo': f"Emitido em: {nome_mun}" if is_outro_mun else (item.periodo_vigencia or f"Ano Letivo {item.ano_letivo}"),
            'responsavel': item.professor.nome if item.professor else 'Professor Responsável',
            'status': item.status or 'Homologado',
            'sintese': item.objetivos_curto_prazo_acad or item.barreiras_atidudinais or 'Plano Educacional Individualizado registrado.',
            'obj': item,
            'historico_outro_municipio': is_outro_mun,
            'nome_municipio_origem': nome_mun
        })
        
    for item in paees:
        is_outro_mun = (item.aluno.escola.municipio_id != g.municipio.id) if (item.aluno and item.aluno.escola) else False
        nome_mun = item.aluno.escola.municipio.nome if (is_outro_mun and item.aluno and item.aluno.escola and item.aluno.escola.municipio) else None

        linha_tempo.append({
            'tipo': 'paee',
            'categoria': f"PAEE (Plano SRM) {'(Histórico: ' + nome_mun + ')' if is_outro_mun else ''}",
            'icone': '🧩',
            'cor': 'emerald',
            'data': item.data_cadastro,
            'titulo': f"PAEE — {item.periodo_vigencia or 'SRM'}",
            'subtitulo': f"Emitido em: {nome_mun}" if is_outro_mun else (item.periodo_vigencia or 'Plano de Atendimento Especializado'),
            'responsavel': item.professor_regente or 'Especialista AEE',
            'status': item.status or 'Homologado',
            'sintese': item.objetivo_geral or item.objetivos_especificos or 'Plano de Atendimento Educacional Especializado registrado.',
            'obj': item,
            'historico_outro_municipio': is_outro_mun,
            'nome_municipio_origem': nome_mun
        })

    for item in planos_aee:
        linha_tempo.append({
            'tipo': 'paee',
            'categoria': 'Plano Técnico AEE',
            'icone': '📋',
            'cor': 'teal',
            'data': item.data_criacao,
            'titulo': "Plano Anual AEE",
            'subtitulo': f"Status: {item.status}",
            'responsavel': item.profissional.nome if item.profissional else 'Profissional AEE',
            'status': item.status or 'Em Andamento',
            'sintese': item.objetivos_gerais or item.avaliacao_inicial or 'Plano de Atendimento em Sala de Recursos.',
            'obj': item,
            'historico_outro_municipio': False
        })

    for item in estudos_caso:
        is_outro_mun = (item.aluno.escola.municipio_id != g.municipio.id) if (item.aluno and item.aluno.escola) else False
        nome_mun = item.aluno.escola.municipio.nome if (is_outro_mun and item.aluno and item.aluno.escola and item.aluno.escola.municipio) else None

        linha_tempo.append({
            'tipo': 'estudo_caso',
            'categoria': f"Estudo de Caso & Triagem {'(Histórico: ' + nome_mun + ')' if is_outro_mun else ''}",
            'icone': '🔍',
            'cor': 'purple',
            'data': item.data_cadastro,
            'titulo': f"Estudo de Caso {item.ano_letivo}",
            'subtitulo': f"Emitido em: {nome_mun}" if is_outro_mun else f"Prof. Regente: {item.professor_regente or 'N/A'}",
            'responsavel': item.professor_aee or (item.professor.nome if item.professor else 'Equipe Técnica'),
            'status': item.status or 'Homologado',
            'sintese': item.hist_desenvolvimento_academico or item.necessidades_especificas or 'Protocolo de Triagem e Análise Pedagógica.',
            'obj': item,
            'historico_outro_municipio': is_outro_mun,
            'nome_municipio_origem': nome_mun
        })

    for item in evolucoes_aee:
        linha_tempo.append({
            'tipo': 'evolucao',
            'categoria': 'Evolução Diária (SOAP)',
            'icone': '📝',
            'cor': 'amber',
            'data': item.data_atendimento,
            'titulo': f"Atendimento AEE — {item.data_atendimento.strftime('%d/%m/%Y') if hasattr(item.data_atendimento, 'strftime') else item.data_atendimento}",
            'subtitulo': f"Presença: {item.presenca}",
            'responsavel': item.profissional.nome if item.profissional else 'Especialista AEE',
            'status': 'Registrado',
            'sintese': f"Atividade: {item.atividade_trabalhada} | Observado: {item.evolucao_observada}",
            'obj': item,
            'historico_outro_municipio': False
        })

    # Ordena do evento mais recente para o mais antigo
    linha_tempo.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)

    return render_template(
        'alunos/perfil.html', 
        aluno=aluno, 
        peis=peis, 
        paees=paees, 
        estudos_caso=estudos_caso,
        evolucoes_aee=evolucoes_aee,
        linha_tempo=linha_tempo,
        municipios_disponiveis=municipios_disponiveis
    )

@alunos_bp.route('/<int:id>/desativar', methods=['POST'])
@login_required
def desativar_aluno(id):
    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    aluno.ativo = False
    db.session.commit()
    flash(f"{aluno.nome} foi desativado.", "info")
    return redirect(url_for('alunos.listar', municipio_slug=g.municipio_slug))

@alunos_bp.route('/desativados', methods=['GET'])
@login_required
def listar_desativados():
    # Busca apenas os alunos onde ativo é False
    alunos_inativos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=False).all()
    return render_template('alunos/desativados.html', alunos=alunos_inativos)

@alunos_bp.route('/<int:id>/reativar', methods=['POST'])
@login_required
def reativar_aluno(id):
    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    aluno.ativo = True
    db.session.commit()
    flash(f"Aluno {aluno.nome} reativado com sucesso!", "success")
    return redirect(url_for('alunos.listar_desativados', municipio_slug=g.municipio_slug))

@alunos_bp.route('/<int:id>/upload-foto', methods=['POST'])
@login_required
def upload_foto(id):
    import os
    from datetime import datetime
    
    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    foto = request.files.get('foto')
    
    if not foto or foto.filename == '':
        flash("Selecione uma imagem válida para o perfil do estudante.", "warning")
        return redirect(url_for('alunos.perfil_aluno', municipio_slug=g.municipio_slug, aluno_id=aluno.id))
        
    upload_folder = os.path.join('app', 'static', 'uploads', 'fotos_alunos')
    os.makedirs(upload_folder, exist_ok=True)
    
    ext = os.path.splitext(foto.filename)[1] or '.jpg'
    filename = f"foto_aluno_{aluno.id}_{int(datetime.utcnow().timestamp())}{ext}"
    foto.save(os.path.join(upload_folder, filename))
    
    aluno.foto_url = f"uploads/fotos_alunos/{filename}"
    db.session.commit()
    
    flash(f"Foto oficial de {aluno.nome} atualizada com sucesso no prontuário!", "success")
    return redirect(url_for('alunos.perfil_aluno', municipio_slug=g.municipio_slug, aluno_id=aluno.id))

@alunos_bp.route('/<int:id>/prontuario', methods=['GET'])
@login_required
def prontuario(id):
    from datetime import datetime
    from app.models import EstudoCaso, EvolucaoAEE, PlanoAEE, AgendaAEE, AtendimentoAee
    
    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    
    peis = Pei.query.filter_by(aluno_id=aluno.id).order_by(Pei.criado_em.desc()).all()
    paees = Paee.query.filter_by(aluno_id=aluno.id).order_by(Paee.data_cadastro.desc()).all()
    planos_aee = PlanoAEE.query.filter_by(aluno_id=aluno.id).order_by(PlanoAEE.data_criacao.desc()).all()
    estudos_caso = EstudoCaso.query.filter_by(aluno_id=aluno.id).order_by(EstudoCaso.data_cadastro.desc()).all()
    evolucoes_aee = EvolucaoAEE.query.filter_by(aluno_id=aluno.id).order_by(EvolucaoAEE.data_atendimento.desc()).all()
    agendamentos = AgendaAEE.query.filter_by(aluno_id=aluno.id).order_by(AgendaAEE.criado_em.desc()).all()
    atendimentos = AtendimentoAee.query.filter_by(aluno_id=aluno.id).all()
    
    timestamp_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
    
    return render_template(
        'alunos/prontuario.html',
        aluno=aluno,
        peis=peis,
        paees=paees,
        planos_aee=planos_aee,
        estudos_caso=estudos_caso,
        evolucoes_aee=evolucoes_aee,
        agendamentos=agendamentos,
        atendimentos=atendimentos,
        timestamp_emissao=timestamp_emissao
    )

@alunos_bp.route('/<int:id>/imprimir-prontuario', methods=['GET'])
@login_required
def imprimir_prontuario(id):
    from datetime import datetime
    from app.models import EstudoCaso, EvolucaoAEE, PlanoAEE, AgendaAEE, AtendimentoAee
    
    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    
    peis = Pei.query.filter_by(aluno_id=aluno.id).order_by(Pei.criado_em.desc()).all()
    paees = Paee.query.filter_by(aluno_id=aluno.id).order_by(Paee.data_cadastro.desc()).all()
    planos_aee = PlanoAEE.query.filter_by(aluno_id=aluno.id).order_by(PlanoAEE.data_criacao.desc()).all()
    estudos_caso = EstudoCaso.query.filter_by(aluno_id=aluno.id).order_by(EstudoCaso.data_cadastro.desc()).all()
    evolucoes_aee = EvolucaoAEE.query.filter_by(aluno_id=aluno.id).order_by(EvolucaoAEE.data_atendimento.desc()).all()
    agendamentos = AgendaAEE.query.filter_by(aluno_id=aluno.id).order_by(AgendaAEE.criado_em.desc()).all()
    
    timestamp_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
    
    return render_template(
        'alunos/imprimir_prontuario.html',
        aluno=aluno,
        peis=peis,
        paees=paees,
        planos_aee=planos_aee,
        estudos_caso=estudos_caso,
        evolucoes_aee=evolucoes_aee,
        agendamentos=agendamentos,
        timestamp_emissao=timestamp_emissao
    )

@alunos_bp.route('/<int:id>/transferir', methods=['POST'])
@login_required
def transferir_aluno(id):
    from datetime import datetime
    from app.models import TransferenciaAluno
    
    aluno_origem = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    municipio_destino_id = request.form.get('municipio_destino_id', type=int)
    motivo = request.form.get('motivo', 'Transferência intermunicipal solicitada pela família/escola.')
    
    if not municipio_destino_id:
        flash("Selecione um município de destino válido.", "danger")
        return redirect(url_for('alunos.perfil_aluno', municipio_slug=g.municipio_slug, aluno_id=aluno_origem.id))
        
    municipio_destino = Municipio.query.get_or_404(municipio_destino_id)
    if municipio_destino.id == g.municipio.id:
        flash("O município de destino deve ser diferente do município atual.", "warning")
        return redirect(url_for('alunos.perfil_aluno', municipio_slug=g.municipio_slug, aluno_id=aluno_origem.id))

    # 1. Inativa o aluno na origem
    aluno_origem.ativo = False
    aluno_origem.status_transferencia = 'Transferido'
    aluno_origem.data_transferencia = datetime.utcnow()

    # 2. Cria registro do aluno no município de destino
    aluno_destino = Aluno(
        nome=aluno_origem.nome,
        cpf=aluno_origem.cpf,
        data_nascimento=aluno_origem.data_nascimento,
        sexo=aluno_origem.sexo,
        raca_cor=aluno_origem.raca_cor,
        naturalidade=aluno_origem.naturalidade,
        foto_url=aluno_origem.foto_url,
        nome_mae=aluno_origem.nome_mae,
        nome_pai=aluno_origem.nome_pai,
        recebe_bpc=aluno_origem.recebe_bpc,
        matricula=f"{aluno_origem.matricula}-{municipio_destino.slug[:4].upper()}",
        codigo_inep=aluno_origem.codigo_inep,
        escola_id=None,
        turma="A Definir (Nova Rede)",
        modalidade=aluno_origem.modalidade,
        etapa_ensino=aluno_origem.etapa_ensino,
        cid=aluno_origem.cid,
        tipo_deficiencia=aluno_origem.tipo_deficiencia,
        possui_tea=aluno_origem.possui_tea,
        possui_superdotacao=aluno_origem.possui_superdotacao,
        local_aee=aluno_origem.local_aee,
        necessita_apoio=aluno_origem.necessita_apoio,
        medicacoes=aluno_origem.medicacoes,
        restricoes_alimentares=aluno_origem.restricoes_alimentares,
        acessibilidade_necessaria=aluno_origem.acessibilidade_necessaria,
        necessita_transporte_adaptado=aluno_origem.necessita_transporte_adaptado,
        cadeirante=aluno_origem.cadeirante,
        necessita_acompanhante=aluno_origem.necessita_acompanhante,
        possui_monitor_rota=aluno_origem.possui_monitor_rota,
        contato_urgencia=aluno_origem.contato_urgencia,
        municipio_id=municipio_destino.id,
        municipio_origem_id=g.municipio.id,
        status_transferencia='Recebido',
        ativo=True
    )
    db.session.add(aluno_destino)
    db.session.flush()

    # 3. Registra a transferência no histórico
    transferencia = TransferenciaAluno(
        aluno_id=aluno_origem.id,
        municipio_origem_id=g.municipio.id,
        municipio_destino_id=municipio_destino.id,
        usuario_id=current_user.id,
        motivo=motivo
    )
    db.session.add(transferencia)
    db.session.commit()

    flash(f"✅ Transferência concluída com sucesso! Estudante {aluno_origem.nome} transferido para {municipio_destino.nome} - {municipio_destino.estado}. O histórico antigo permanece preservado como somente-leitura em {g.municipio.nome}.", "success")
    return redirect(url_for('alunos.perfil_aluno', municipio_slug=g.municipio_slug, aluno_id=aluno_origem.id))