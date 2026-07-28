from datetime import datetime, date
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
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    ano_letivo = request.args.get('ano_letivo', '2026')
    escola_id = request.args.get('escola_id', type=int)
    status_matricula = request.args.get('status_matricula', 'Ativo')
    busca = request.args.get('busca', '').strip()

    query = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True)
    
    if ano_letivo and ano_letivo != 'todos':
        query = query.filter(Aluno.ano_letivo == ano_letivo)
    if escola_id:
        query = query.filter(Aluno.escola_id == escola_id)
    if status_matricula and status_matricula != 'todos':
        query = query.filter(Aluno.status_matricula == status_matricula)
    if busca:
        query = query.filter((Aluno.nome.ilike(f"%{busca}%")) | (Aluno.matricula.ilike(f"%{busca}%")) | (Aluno.cpf.ilike(f"%{busca}%")))

    pagination = query.order_by(Aluno.nome).paginate(page=page, per_page=per_page, error_out=False)
    alunos = pagination.items
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()

    return render_template(
        'alunos/listar.html',
        alunos=alunos,
        pagination=pagination,
        escolas=escolas,
        ano_letivo_filtro=ano_letivo,
        escola_id_filtro=escola_id,
        status_filtro=status_matricula,
        busca=busca
    )

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

    # Busca Termos de Transferência emitidos para rastreabilidade auditável
    from app.models import DocumentoAEE
    import json
    documentos_termo = DocumentoAEE.query.filter_by(
        aluno_id=aluno.id, 
        tipo_documento='Termo de Transferência Intermunicipal'
    ).order_by(DocumentoAEE.data_upload.desc()).all()

    for doc in documentos_termo:
        dados_doc = {}
        if doc.conteudo:
            try:
                dados_doc = json.loads(doc.conteudo)
            except Exception:
                pass
        dest_nome = dados_doc.get('municipio_destino_nome', 'Rede Externa')
        
        linha_tempo.append({
            'tipo': 'termo_transferencia',
            'categoria': 'Termo de Transferência',
            'icone': '📜',
            'cor': 'amber',
            'data': doc.data_upload,
            'titulo': f"Termo de Transferência ({dest_nome})",
            'subtitulo': f"Chave Rastreável: {doc.chave_autenticidade or 'TR-AUDIT'}",
            'responsavel': dados_doc.get('usuario_nome', 'Secretaria / AEE'),
            'status': 'Emitido & Registrado',
            'sintese': doc.descricao or f"Termo oficial de transferência registrado para {dest_nome}.",
            'obj': doc,
            'chave': doc.chave_autenticidade,
            'destino_nome': dest_nome,
            'motivo': dados_doc.get('motivo', ''),
            'historico_outro_municipio': False
        })

    def parse_sort_date(val):
        if not val:
            return datetime.min
        if isinstance(val, datetime):
            return val
        from datetime import date as dt_date
        if isinstance(val, dt_date):
            return datetime.combine(val, datetime.min.time())
        return datetime.min

    # Ordena do evento mais recente para o mais antigo
    linha_tempo.sort(key=lambda x: parse_sort_date(x['data']), reverse=True)

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

@alunos_bp.route('/<int:id>/remanejar', methods=['GET', 'POST'])
@login_required
def remanejar_escola_interna(id):
    """
    Remaneja o aluno para outra escola/turma do mesmo município com histórico registrado.
    """
    from app.models import HistoricoTransferenciaAluno
    if current_user.perfil not in ['secretaria', 'superadmin', 'diretor']:
        abort(403)
        
    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    escolas = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()

    if request.method == 'POST':
        escola_destino_id = request.form.get('escola_destino_id', type=int)
        nova_turma = request.form.get('nova_turma', '').strip()
        motivo = request.form.get('motivo_transferencia', '').strip()

        if not escola_destino_id or not nova_turma:
            flash("Selecione a escola de destino e a nova turma!", "erro")
        else:
            reg_historico = HistoricoTransferenciaAluno(
                municipio_id=g.municipio.id,
                aluno_id=aluno.id,
                escola_origem_id=aluno.escola_id,
                escola_destino_id=escola_destino_id,
                turma_origem=aluno.turma,
                turma_destino=nova_turma,
                ano_letivo=aluno.ano_letivo or '2026',
                motivo_transferencia=motivo,
                usuario_id=current_user.id
            )
            db.session.add(reg_historico)

            aluno.escola_id = escola_destino_id
            aluno.turma = nova_turma
            db.session.commit()

            flash(f"Estudante '{aluno.nome}' remanejado com sucesso para a nova unidade escolar!", "sucesso")
            return redirect(url_for('alunos.perfil_aluno', aluno_id=aluno.id, municipio_slug=g.municipio_slug))

    return render_template('alunos/transferir.html', aluno=aluno, escolas=escolas)


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

@alunos_bp.route('/<int:id>/imprimir-termo-transferencia', methods=['GET', 'POST'])
@login_required
def imprimir_termo_transferencia(id):
    """Gera o Termo Oficial de Transferência Intermunicipal em PDF/Impressão timbrada."""
    from datetime import datetime
    from app.models import Pei, PlanoAEE, TransferenciaAluno

    aluno = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    
    # Captura dados de destino e motivo enviados via GET/POST
    municipio_destino_nome = request.values.get('municipio_destino_nome', request.values.get('destino_nome', '')).strip()
    motivo = request.values.get('motivo', '').strip()

    if not municipio_destino_nome:
        # Tenta buscar a última transferência registrada no banco
        ultima_transf = TransferenciaAluno.query.filter_by(aluno_id=aluno.id).order_by(TransferenciaAluno.id.desc()).first()
        if ultima_transf:
            if ultima_transf.municipio_destino:
                municipio_destino_nome = f"{ultima_transf.municipio_destino.nome} — {ultima_transf.municipio_destino.estado} (Rede Integrada PNGI)"
            else:
                municipio_destino_nome = "Rede Municipal / Estadual de Destino"
            if not motivo and ultima_transf.motivo:
                motivo = ultima_transf.motivo
        else:
            municipio_destino_nome = "Rede Municipal / Estadual de Destino (Não Integrada ao PNGI)"

    if not motivo:
        motivo = "Transferência intermunicipal de escolaridade e histórico do AEE."

    # Contadores de histórico
    peis_count = Pei.query.filter_by(aluno_id=aluno.id).count()
    paee_count = PlanoAEE.query.filter_by(aluno_id=aluno.id).count()
    timestamp_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')

    def format_data(val):
        if not val:
            return 'Não Informada'
        if hasattr(val, 'strftime'):
            return val.strftime('%d/%m/%Y')
        if isinstance(val, str):
            val_s = val.strip()
            if not val_s:
                return 'Não Informada'
            if '-' in val_s:
                parts = val_s.split('T')[0].split('-')
                if len(parts) == 3:
                    return f"{parts[2]}/{parts[1]}/{parts[0]}"
            return val_s
        return str(val)

    data_nascimento_str = format_data(aluno.data_nascimento)

    # Registra no Controle Documental Digital (DocumentoAEE) para Rastreabilidade Integral
    import uuid, json
    from app.models import DocumentoAEE
    
    chave_autenticidade = f"TR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    doc_termo = DocumentoAEE(
        municipio_id=g.municipio.id,
        aluno_id=aluno.id,
        tipo_documento='Termo de Transferência Intermunicipal',
        descricao=f'Termo de Transferência Intermunicipal emitido para {municipio_destino_nome}',
        conteudo=json.dumps({
            'municipio_destino_nome': municipio_destino_nome,
            'motivo': motivo,
            'chave': chave_autenticidade,
            'usuario_nome': current_user.nome,
            'usuario_cargo': current_user.perfil
        }, ensure_ascii=False),
        chave_autenticidade=chave_autenticidade,
        data_upload=datetime.utcnow()
    )
    db.session.add(doc_termo)
    db.session.commit()

    return render_template(
        'alunos/imprimir_termo_transferencia.html',
        aluno=aluno,
        data_nascimento_str=data_nascimento_str,
        municipio_destino_nome=municipio_destino_nome,
        motivo=motivo,
        peis_count=peis_count,
        paee_count=paee_count,
        timestamp_emissao=timestamp_emissao,
        chave_autenticidade=chave_autenticidade
    )

@alunos_bp.route('/<int:id>/transferir', methods=['POST'])
@login_required
def transferir_aluno(id):
    from datetime import datetime
    from app.models import TransferenciaAluno
    
    aluno_origem = Aluno.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    tipo_transferencia = request.form.get('tipo_transferencia', 'integrada')
    motivo = request.form.get('motivo', 'Transferência intermunicipal solicitada pela família/escola.').strip()
    
    # -------------------------------------------------------------------------
    # CASO A: Transferência Externa (Município que NÃO utiliza a Plataforma PNGI)
    # -------------------------------------------------------------------------
    if tipo_transferencia == 'externa':
        municipio_destino_nome = request.form.get('municipio_destino_nome', 'Outro Município / Estado').strip()
        if not municipio_destino_nome:
            flash("Informe o nome do município/estado de destino para emissão da transferência.", "warning")
            return redirect(url_for('alunos.perfil_aluno', municipio_slug=g.municipio_slug, aluno_id=aluno_origem.id))

        aluno_origem.ativo = False
        aluno_origem.status_transferencia = f'Transferido Externa ({municipio_destino_nome})'
        aluno_origem.data_transferencia = datetime.utcnow()

        transferencia = TransferenciaAluno(
            aluno_id=aluno_origem.id,
            municipio_origem_id=g.municipio.id,
            municipio_destino_id=g.municipio.id,
            usuario_id=current_user.id,
            motivo=f"[Destino Externa: {municipio_destino_nome}] {motivo}"
        )
        db.session.add(transferencia)
        db.session.commit()

        flash(f"✅ Estudante {aluno_origem.nome} transferido externamente para '{municipio_destino_nome}'. Termo oficial gerado e histórico arquivado em {g.municipio.nome}.", "success")
        return redirect(url_for('alunos.perfil_aluno', municipio_slug=g.municipio_slug, aluno_id=aluno_origem.id))

    # -------------------------------------------------------------------------
    # CASO B: Transferência Integrada (Município Parceiro com Plataforma PNGI)
    # -------------------------------------------------------------------------
    municipio_destino_id = request.form.get('municipio_destino_id', type=int)
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