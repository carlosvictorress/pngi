import json
from flask import Blueprint, render_template, request, redirect, url_for, g, abort, flash
from app.models import Aluno, Pei, Usuario, EstudoCaso, Paee
from app import db
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy import func


pei_bp = Blueprint('pei', __name__)

@pei_bp.url_value_preprocessor
def pull_slug(endpoint, values):
    if values:
        g.municipio_slug = values.pop('municipio_slug', None)

@pei_bp.before_app_request
def carregar_contexto():
    if request.path.startswith('/static/') or request.path.startswith('/auth/'):
        return
    if current_user.is_authenticated and current_user.perfil != 'superadmin':
        g.municipio = current_user.municipio

@pei_bp.route('/')
@login_required
def listar_alunos_pei():
    if not g.municipio:
        abort(404)
        
    alunos = (
        Aluno.query.filter_by(municipio_id=g.municipio.id)
        .options(joinedload(Aluno.estudos_caso))
        .order_by(Aluno.nome)
        .all()
    )
    
    peis_emitidos = (
        Pei.query.join(Aluno)
        .filter(Aluno.municipio_id == g.municipio.id)
        .order_by(Pei.id.desc())
        .all()
    )
    
    return render_template('pei/escolher_aluno.html', alunos=alunos, peis_emitidos=peis_emitidos)

@pei_bp.route('/aluno/<int:aluno_id>/novo', methods=['GET', 'POST'])
@login_required
def criar_pei(aluno_id):
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    estudo_previo = EstudoCaso.query.filter_by(aluno_id=aluno.id, status='Homologado').first()
    
    if request.method == 'POST':
        # 1. Processamento Dinâmico da Matriz de Disciplinas / BNCC
        disciplinas = request.form.getlist('disc_nome[]')
        conteudos = request.form.getlist('disc_conteudo[]')
        bnccs = request.form.getlist('disc_bncc[]')
        metodologias = request.form.getlist('disc_metodologia[]')
        recursos = request.form.getlist('disc_recursos[]')
        avaliacoes = request.form.getlist('disc_avaliacao[]')
        
        lista_disciplinas = []
        for i in range(len(disciplinas)):
            if disciplinas[i].strip():
                lista_disciplinas.append({
                    'disciplina': disciplinas[i],
                    'conteudo': conteudos[i],
                    'bncc': bnccs[i],
                    'metodologia': metodologias[i],
                    'recursos': recursos[i],
                    'avaliacao': avaliacoes[i]
                })

        # 2. Processamento Dinâmico das Metas Pedagogicas por Periodização
        meta_periodos = request.form.getlist('meta_periodo[]')
        meta_objetivos = request.form.getlist('meta_objetivo[]')
        meta_estrategias = request.form.getlist('meta_estrategia[]')
        meta_avaliacoes = request.form.getlist('meta_aval[]')
        
        lista_metas = []
        for i in range(len(meta_periodos)):
            if meta_periodos[i].strip():
                lista_metas.append({
                    'periodo': meta_periodos[i],
                    'objetivo': meta_objetivos[i],
                    'estrategia': meta_estrategias[i],
                    'avaliacao': meta_avaliacoes[i]
                })

        novo_pei = Pei(
            aluno_id=aluno.id,
            professor_id=current_user.id,
            periodo_trimestre=int(request.form.get('periodo_trimestre', 1)),
            ano_letivo=int(request.form.get('ano_letivo', 2026)),
            coordenador_pedagogico=request.form.get('coordenador_pedagogico'),
            periodo_vigencia=request.form.get('periodo_vigencia', 'Fevereiro a Dezembro de 2026'),
            
            # Dimensão 1: Barreiras Expandidas
            barreiras_arquitetonicas=request.form.get('barreiras_arquitetonicas'),
            barreiras_atidudinais=request.form.get('barreiras_atidudinais'),
            barreiras_pedagogicas=request.form.get('barreiras_pedagogicas'),
            barreiras_comunicacao=request.form.get('barreiras_comunicacao'),
            potencialidades_cognitivas=request.form.get('potencialidades_cognitivas'),
            
            # Dimensão: Entrevista Expandida com Responsáveis
            resp_parentesco=request.form.get('resp_parentesco'),
            resp_contato=request.form.get('resp_contato'),
            resp_data_entrevista=request.form.get('resp_data_entrevista'),
            resp_historico_desenvolvimento=request.form.get('resp_historico_desenvolvimento'),
            resp_acompanhamento_medico=request.form.get('resp_acompanhamento_medico'),
            resp_dificuldades_familiares=request.form.get('resp_dificuldades_familiares'),
            resp_potencialidades=request.form.get('resp_potencialidades'),
            resp_rotina_casa=request.form.get('resp_rotina_casa'),
            resp_medicacao=request.form.get('resp_medicacao'),
            resp_laudos_relatorios=request.form.get('resp_laudos_relatorios'),
            resp_necessita_apoio_basico=request.form.get('resp_necessita_apoio_basico'),
            resp_interesse_atividades=request.form.get('resp_interesse_atividades'),
            resp_autonomia_tarefas=request.form.get('resp_autonomia_tarefas'),
            resp_interacao_social=request.form.get('resp_interacao_social'),
            resp_comportamento_domestico=request.form.get('resp_comportamento_domestico'),
            resp_preferencias_sensibilidades=request.form.get('resp_preferencias_sensibilidades'),
            resp_expectativas_familia=request.form.get('resp_expectativas_familia'),
            resp_encaminhamentos_conjuntos=request.form.get('resp_encaminhamentos_conjuntos'),

            # Dimensão: Caracterização Multidimensional
            char_aspectos_cognitivos=request.form.get('char_aspectos_cognitivos'),
            char_aspectos_motores=request.form.get('char_aspectos_motores'),
            char_aspectos_socioemocionais=request.form.get('char_aspectos_socioemocionais'),
            char_aspectos_comunicacionais=request.form.get('char_aspectos_comunicacionais'),

            # Dimensão 2: SRM Atendimento
            frequencia_srm_semanal=int(request.form.get('frequencia_srm_semanal', 2)),
            organizacao_atendimento=request.form.get('organizacao_atendimento'),
            
            # Dimensão 3: Objetivos Fixos Legados
            objetivos_curto_prazo_acad=request.form.get('objetivos_curto_prazo_acad', ''),
            objetivos_medio_prazo_acad=request.form.get('objetivos_medio_prazo_acad', ''),
            objetivos_longo_prazo_acad=request.form.get('objetivos_longo_prazo_acad', ''),
            estrategias_pedagogicas_acad=request.form.get('estrategias_pedagogicas_acad', ''),
            objetivos_curto_prazo_auton=request.form.get('objetivos_curto_prazo_auton', ''),
            objetivos_longo_prazo_auton=request.form.get('objetivos_longo_prazo_auton', ''),
            estrategias_desenvolvimento_auton=request.form.get('estrategias_desenvolvimento_auton', ''),

            # Dimensão Dinâmica de Matrizes (Novos Modelos JSON)
            cronograma_periodizacao=request.form.get('cronograma_periodizacao', 'Trimestrais'),
            metas_pedagogicas_json=json.dumps(lista_metas, ensure_ascii=False),
            disciplinas_bncc_json=json.dumps(lista_disciplinas, ensure_ascii=False),
            
            # Dimensão 4: Recursos Checkboxes
            recursos_opticos_adicionais='recursos_opticos_adicionais' in request.form,
            recursos_comunicacao_alternativa='recursos_comunicacao_alternativa' in request.form,
            recursos_acessibilidade_informatica='recursos_acessibilidade_informatica' in request.form,
            recursos_atendimento_libras='recursos_atendimento_libras' in request.form,
            
            # Dimensão 5: Apoio Humano
            necessita_profissional_apoio='necessita_profissional_apoio' in request.form,
            atividades_apoio_especificadas=request.form.get('atividades_apoio_especificadas'),
            
            status='Aguardando Coordenação AEE' if 'enviar_validacao' in request.form else 'Rascunho'
        )
        
        if 'enviar_validacao' in request.form:
            novo_pei.assinado_professor = True
            novo_pei.assinado_professor_em = datetime.utcnow()
            
        db.session.add(novo_pei)
        db.session.commit()
        flash('PEI Institucional de Alta Performance gerado com sucesso no censo municipal.', 'success')
        return redirect(url_for('pei.listar_alunos_pei', municipio_slug=g.municipio.slug))

    # Fluxo GET: Pré-Preenchimento inteligente herdando o Estudo de Caso Homologado
    pei_herdados = None
    if estudo_previo:
        pei_herdados = Pei(
            aluno_id=aluno.id,
            barreiras_arquitetonicas=estudo_previo.barreiras_arquitetonicas,
            barreiras_atidudinais=estudo_previo.barreiras_atitudinais,
            barreiras_pedagogicas=estudo_previo.barreiras_pedagogicas,
            barreiras_comunicacao=estudo_previo.barreiras_comunicacionais,
            potencialidades_cognitivas=estudo_previo.necessidades_especificas or '',
            
            # Herança direta das entrevistas detalhadas
            resp_historico_desenvolvimento=estudo_previo.fam_historico_desenvolvimento,
            resp_laudos_relatorios=estudo_previo.fam_diagnosticos_apresentados,
            resp_acompanhamento_medico=estudo_previo.fam_acompanhamentos_terapeuticos,
            resp_rotina_casa=estudo_previo.fam_rotina_familiar,
            resp_comportamento_domestico=estudo_previo.fam_comportamento_casa,
            resp_interacao_social=estudo_previo.fam_interacao_social,
            resp_autonomia_tarefas=estudo_previo.fam_autonomia,
            resp_expectativas_familia=estudo_previo.fam_expectativas_familia,
            
            # Herança direta da observação pedagógica expandida em sala
            char_aspectos_cognitivos=estudo_previo.obs_participacao_atividades,
            char_aspectos_motores=estudo_previo.obs_coordenacao_motora,
            char_aspectos_socioemocionais=estudo_previo.obs_interacao_social,
            char_aspectos_comunicacionais=estudo_previo.obs_comunicacao
        )

    return render_template('pei/formulario_pei.html', aluno=aluno, pei=pei_herdados)

@pei_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_pei(id):
    pei = Pei.query.join(Aluno).filter(Pei.id == id, Aluno.municipio_id == g.municipio.id).first_or_404()
    
    if request.method == 'POST':
        # 1. Processamento Dinâmico da Matriz de Disciplinas / BNCC
        disciplinas = request.form.getlist('disc_nome[]')
        conteudos = request.form.getlist('disc_conteudo[]')
        bnccs = request.form.getlist('disc_bncc[]')
        metodologias = request.form.getlist('disc_metodologia[]')
        recursos = request.form.getlist('disc_recursos[]')
        avaliacoes = request.form.getlist('disc_avaliacao[]')
        
        lista_disciplinas = []
        for i in range(len(disciplinas)):
            if disciplinas[i].strip():
                lista_disciplinas.append({
                    'disciplina': disciplinas[i],
                    'conteudo': conteudos[i],
                    'bncc': bnccs[i],
                    'metodologia': metodologias[i],
                    'recursos': recursos[i],
                    'avaliacao': avaliacoes[i]
                })

        # 2. Processamento Dinâmico das Metas Pedagogicas por Periodização
        meta_periodos = request.form.getlist('meta_periodo[]')
        meta_objetivos = request.form.getlist('meta_objetivo[]')
        meta_estrategias = request.form.getlist('meta_estrategia[]')
        meta_avaliacoes = request.form.getlist('meta_aval[]')
        
        lista_metas = []
        for i in range(len(meta_periodos)):
            if meta_periodos[i].strip():
                lista_metas.append({
                    'periodo': meta_periodos[i],
                    'objetivo': meta_objetivos[i],
                    'estrategia': meta_estrategias[i],
                    'avaliacao': meta_avaliacoes[i]
                })

        pei.periodo_trimestre = int(request.form.get('periodo_trimestre', 1))
        pei.ano_letivo = int(request.form.get('ano_letivo', 2026))
        pei.coordenador_pedagogico = request.form.get('coordenador_pedagogico')
        pei.periodo_vigencia = request.form.get('periodo_vigencia')
        
        # Salvamento das barreiras
        pei.barreiras_arquitetonicas = request.form.get('barreiras_arquitetonicas')
        pei.barreiras_atidudinais = request.form.get('barreiras_atidudinais')
        pei.barreiras_pedagogicas = request.form.get('barreiras_pedagogicas')
        pei.barreiras_comunicacao = request.form.get('barreiras_comunicacao')
        pei.potencialidades_cognitivas = request.form.get('potencialidades_cognitivas')
        
        # Salvamento da Entrevista com os Responsáveis
        pei.resp_parentesco = request.form.get('resp_parentesco')
        pei.resp_contato = request.form.get('resp_contato')
        pei.resp_data_entrevista = request.form.get('resp_data_entrevista')
        pei.resp_historico_desenvolvimento = request.form.get('resp_historico_desenvolvimento')
        pei.resp_acompanhamento_medico = request.form.get('resp_acompanhamento_medico')
        pei.resp_dificuldades_familiares = request.form.get('resp_dificuldades_familiares')
        pei.resp_potencialidades = request.form.get('resp_potencialidades')
        pei.resp_rotina_casa = request.form.get('resp_rotina_casa')
        pei.resp_medicacao = request.form.get('resp_medicacao')
        pei.resp_laudos_relatorios = request.form.get('resp_laudos_relatorios')
        pei.resp_necessita_apoio_basico = request.form.get('resp_necessita_apoio_basico')
        pei.resp_interesse_atividades = request.form.get('resp_interesse_atividades')
        pei.resp_autonomia_tarefas = request.form.get('resp_autonomia_tarefas')
        pei.resp_interacao_social = request.form.get('resp_interacao_social')
        pei.resp_comportamento_domestico = request.form.get('resp_comportamento_domestico')
        pei.resp_preferencias_sensibilidades = request.form.get('resp_preferencias_sensibilidades')
        pei.resp_expectativas_familia = request.form.get('resp_expectativas_familia')
        pei.resp_encaminhamentos_conjuntos = request.form.get('resp_encaminhamentos_conjuntos')

        # Salvamento da Caracterização Multidimensional
        pei.char_aspectos_cognitivos = request.form.get('char_aspectos_cognitivos')
        pei.char_aspectos_motores = request.form.get('char_aspectos_motores')
        pei.char_aspectos_socioemocionais = request.form.get('char_aspectos_socioemocionais')
        pei.char_aspectos_comunicacionais = request.form.get('char_aspectos_comunicacionais')

        # SRM
        pei.frequencia_srm_semanal = int(request.form.get('frequencia_srm_semanal', 2))
        pei.organizacao_atendimento = request.form.get('organizacao_atendimento')

        # Matrizes serializadas em JSON
        pei.cronograma_periodizacao = request.form.get('cronograma_periodizacao', 'Trimestrais')
        pei.metas_pedagogicas_json = json.dumps(lista_metas, ensure_ascii=False)
        pei.disciplinas_bncc_json = json.dumps(lista_disciplinas, ensure_ascii=False)
        
        # Checkboxes de Recursos
        pei.recursos_opticos_adicionais = 'recursos_opticos_adicionais' in request.form
        pei.recursos_comunicacao_alternativa = 'recursos_comunicacao_alternativa' in request.form
        pei.recursos_acessibilidade_informatica = 'recursos_acessibilidade_informatica' in request.form
        pei.recursos_atendimento_libras = 'recursos_atendimento_libras' in request.form
        
        # Profissional de apoio
        pei.necessita_profissional_apoio = 'necessita_profissional_apoio' in request.form
        pei.atividades_apoio_especificadas = request.form.get('atividades_apoio_especificadas')
        
        if 'enviar_validacao' in request.form:
            pei.status = 'Aguardando Coordenação AEE'
            pei.assinado_professor = True
            pei.assinado_professor_em = datetime.utcnow()
        else:
            pei.status = 'Rascunho'

        db.session.commit()
        flash(f"Plano PEI de {pei.aluno.nome} atualizado com absoluto sucesso!", "success")
        return redirect(url_for('pei.listar_alunos_pei', municipio_slug=g.municipio.slug))

    return render_template('pei/formulario_pei.html', aluno=pei.aluno, pei=pei)

@pei_bp.route('/excluir/<int:id>', methods=['GET', 'POST'])
@login_required
def excluir_pei(id):
    pei = Pei.query.join(Aluno).filter(Pei.id == id, Aluno.municipio_id == g.municipio.id).first_or_404()
    nome_aluno = pei.aluno.nome
    db.session.delete(pei)
    db.session.commit()
    flash(f"Prontuário PEI de {nome_aluno} excluído com sucesso da base municipal.", "success")
    return redirect(url_for('pei.listar_alunos_pei', municipio_slug=g.municipio.slug))

@pei_bp.route('/documento/<int:pei_id>/imprimir', methods=['GET'])
@login_required
def imprimir_pei(pei_id):
    if not g.municipio: 
        abort(404)
        
    pei = Pei.query.get_or_404(pei_id)
    aluno = pei.aluno

    # Validação de permissão: município atual do aluno OU município por onde o aluno já passou
    if aluno.municipio_id != g.municipio.id:
        condicoes = [Aluno.id == aluno.id]
        if aluno.cpf: condicoes.append(Aluno.cpf == aluno.cpf)
        if aluno.codigo_inep: condicoes.append(Aluno.codigo_inep == aluno.codigo_inep)
        alunos_rel = Aluno.query.filter(db.or_(*condicoes)).all()
        muns = [a.municipio_id for a in alunos_rel]
        if g.municipio.id not in muns:
            abort(403)
            
    return render_template('pei/imprimir_pei.html', aluno=aluno, pei=pei)

@pei_bp.route('/aluno/<int:aluno_id>/estudo-caso', methods=['GET', 'POST'])
@login_required
def estudo_caso(aluno_id):
    if not g.municipio:
        abort(404)
        
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    caso = EstudoCaso.query.filter_by(aluno_id=aluno.id).first()

    if request.method == 'POST':
        necessidades = request.form.getlist('nec_id[]')
        estrategias = request.form.getlist('est_int[]')
        responsaveis = request.form.getlist('resp[]')
        periodicidades = request.form.getlist('periodo[]')
        
        lista_intervencoes = []
        for i in range(len(necessidades)):
            if necessidades[i].strip():
                lista_intervencoes.append({
                    'necessidade': necessidades[i],
                    'estrategia': estrategias[i],
                    'responsavel': responsaveis[i],
                    'periodicidade': periodicidades[i]
                })

        if not caso:
            caso = EstudoCaso(aluno_id=aluno.id, professor_id=current_user.id)

        caso.ano_letivo = int(request.form.get('ano_letivo', 2026))
        caso.professor_regente = request.form.get('professor_regente')
        caso.professor_aee = request.form.get('professor_aee')
        caso.responsavel_familiar = request.form.get('responsavel_familiar')
        
        caso.hist_frequencia_escolar = request.form.get('hist_frequencia_escolar')
        caso.hist_desenvolvimento_academico = request.form.get('hist_desenvolvimento_academico')
        caso.hist_dificuldades_observadas = request.form.get('hist_dificuldades_observadas')
        caso.hist_potencialidades_identificadas = request.form.get('hist_potencialidades_identificadas')
        caso.hist_relatorios_anteriores = request.form.get('hist_relatorios_anteriores')
        caso.hist_participacao_projetos = request.form.get('hist_participacao_projetos')
        
        caso.fam_historico_desenvolvimento = request.form.get('fam_historico_desenvolvimento')
        caso.fam_diagnosticos_apresentados = request.form.get('fam_diagnosticos_apresentados')
        caso.fam_acompanhamentos_terapeuticos = request.form.get('fam_acompanhamentos_terapeuticos')
        caso.fam_rotina_familiar = request.form.get('fam_rotina_familiar')
        caso.fam_comportamento_casa = request.form.get('fam_comportamento_casa')
        caso.fam_interacao_social = request.form.get('fam_interacao_social')
        caso.fam_autonomia = request.form.get('fam_autonomia')
        caso.fam_expectativas_familia = request.form.get('fam_expectativas_familia')
        
        caso.obs_participacao_atividades = request.form.get('obs_participacao_atividades')
        caso.obs_comunicacao = request.form.get('obs_comunicacao')
        caso.obs_interacao_social = request.form.get('obs_interacao_social')
        caso.obs_atencao_concentracao = request.form.get('obs_atencao_concentracao')
        caso.obs_coordenacao_motora = request.form.get('obs_coordenacao_motora')
        caso.obs_compreensao_comandos = request.form.get('obs_compreensao_comandos')
        caso.obs_tempo_execucao = request.form.get('obs_tempo_execucao')
        caso.obs_necessidade_mediacao = request.form.get('obs_necessidade_mediacao')
        
        caso.barreiras_arquitetonicas = request.form.get('barreiras_arquitetonicas')
        caso.barreiras_pedagogicas = request.form.get('barreiras_pedagogicas')
        caso.barreiras_comunicacionais = request.form.get('barreiras_comunicacionais')
        caso.barreiras_atitudinais = request.form.get('barreiras_atitudinais')
        caso.necessidades_especificas = request.form.get('necessidades_especificas')
        
        caso.intervencoes_json = json.dumps(lista_intervencoes, ensure_ascii=False)
        
        caso.necessita_pei = 'necessita_pei' in request.form
        caso.necessita_paee = 'necessita_paee' in request.form
        caso.necessita_aee = 'necessita_aee' in request.form
        caso.necessita_apoio = 'necessita_apoio' in request.form
        
        caso.apoio_pedagogico = 'apoio_pedagogico' in request.form
        caso.apoio_locomocao = 'apoio_locomocao' in request.form
        caso.apoio_alimentacao = 'apoio_alimentacao' in request.form
        caso.apoio_higiene = 'apoio_higiene' in request.form
        caso.apoio_comportamental = 'apoio_comportamental' in request.form
        caso.apoio_comunicacional = 'apoio_comunicacional' in request.form
        caso.media_escolar = 'media_escolar' in request.form
        caso.apoio_outro = request.form.get('apoio_outro')
        
        caso.intensidade_suporte = request.form.get('intensidade_suporte', 'Moderado')
        caso.enc_psicopedagogo = 'enc_psicopedagogo' in request.form
        caso.enc_psicologo = 'enc_psicologo' in request.form
        caso.enc_fono = 'enc_fono' in request.form
        caso.enc_to = 'enc_to' in request.form
        caso.enc_fisioterapeuta = 'enc_fisioterapeuta' in request.form
        caso.enc_neuropediatra = 'enc_neuropediatra' in request.form
        
        caso.parecer_pedagogico = request.form.get('parecer_pedagogico')

        if 'homologar_caso' in request.form:
            caso.status = 'Homologado'
            flash(f"Estudo de Caso de {aluno.nome} homologado com sucesso! Diretrizes liberadas.", "success")
        else:
            caso.status = 'Rascunho'
            flash(f"Rascunho do Estudo de Caso de {aluno.nome} salvo com sucesso.", "info")

        db.session.add(caso)
        db.session.commit()
        return redirect(url_for('pei.listar_alunos_pei', municipio_slug=g.municipio.slug))

    return render_template('pei/estudo_caso.html', aluno=aluno, caso=caso)

@pei_bp.route('/aluno/<int:aluno_id>/novo-paee', methods=['GET', 'POST'])
@login_required
def criar_paee(aluno_id):
    if not g.municipio:
        abort(404)
        
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    estudo_previo = EstudoCaso.query.filter_by(aluno_id=aluno.id, status='Homologado').first()
    
    if not estudo_previo:
        flash("🔒 Ação Bloqueada: É necessário homologar o Estudo de Caso primeiro.", "danger")
        return redirect(url_for('pei.listar_alunos_pei', municipio_slug=g.municipio.slug))

    if request.method == 'POST':
        # 1. Captura de tabelas dinâmicas em listas (JSON)
        cronograma_data = []
        areas = request.form.getlist('org_area[]')
        for i in range(len(areas)):
            cronograma_data.append({
                'periodo': areas[i], # Adaptando aos campos da tabela
                'objetivo': request.form.getlist('org_obj[]')[i],
                'estrategia': request.form.getlist('org_est[]')[i],
                'recursos': request.form.getlist('org_rec[]')[i],
                'avaliacao': request.form.getlist('org_ava[]')[i]
            })

        # 2. Captura de Checklists (Item 3)
        needs = request.form.getlist('needs[]')
        needs_outros = request.form.get('needs_outros', '').strip()
        if 'Outros' in needs and needs_outros:
            needs.remove('Outros')
            needs.append(f"Outros: {needs_outros}")

        # 3. Criação do Objeto com o novo Modelo
        novo_paee = Paee(
            aluno_id=aluno.id,
            professor_id=current_user.id,
            # Campos do Checklist
            necessidades_checklist_json=json.dumps(needs, ensure_ascii=False),
            objetivo_geral=request.form.get('obj_geral'),
            objetivos_especificos=request.form.get('obj_especificos'),
            organizacao_atendimento_json=json.dumps(cronograma_data),
            metodologias_json=json.dumps(request.form.getlist('metodologias[]')),
            orientacao_familia=request.form.get('orientacao_familia'),
            # Homologação
            nome_regente=request.form.get('nome_regente'),
            nome_aee=request.form.get('nome_aee'),
            nome_coordenacao=request.form.get('nome_coordenacao'),
            nome_responsavel=request.form.get('nome_responsavel'),
            nome_semec=request.form.get('nome_semec'),
            status='Homologado' if 'homologar' in request.form else 'Rascunho'
        )
        
        db.session.add(novo_paee)
        db.session.commit()
        flash(f"PAEE de {aluno.nome} protocolado com sucesso!", "success")
        return redirect(url_for('pei.listar_alunos_pei', municipio_slug=g.municipio.slug))

    # GET: Fluxo de herança de dados do Estudo de Caso
    paee_herdados = Paee(
        aluno_id=aluno.id,
        objetivo_geral="Promover condições de acessibilidade e participação do estudante no ambiente escolar..."
    )

    return render_template('pei/formulario_paee.html', aluno=aluno, paee=paee_herdados)

@pei_bp.route('/aluno/<int:aluno_id>/imprimir-paee', methods=['GET'])
@login_required
def imprimir_paee(aluno_id):
    if not g.municipio: 
        abort(404)
        
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    
    # Captura o último plano PAEE estruturado na Sala de Recursos para este estudante
    from app.models import Paee
    paee = Paee.query.filter_by(aluno_id=aluno.id).order_by(Paee.id.desc()).first()

    if not paee:
        flash("Nenhum plano PAEE estruturado foi encontrado para este estudante.", "aviso")
        return redirect(url_for('pei.listar_alunos_pei', municipio_slug=g.municipio.slug))

    # Renderiza o layout de impressão oficial do PAEE
    return render_template('pei/imprimir_paee.html', aluno=aluno, paee=paee)

@pei_bp.route('/dashboard-secretaria')
@login_required
def dashboard_secretaria():
    # Contadores institucionais
    total_peis = Pei.query.filter(Pei.aluno.has(municipio_id=g.municipio.id)).count()
    peis_homologados = Pei.query.filter(Pei.status == 'Homologado').count()
    
    # Agrupamento por tipo de deficiência para o gráfico
    stats_deficiencia = db.session.query(
        Aluno.tipo_deficiencia, func.count(Pei.id)
    ).join(Pei).group_by(Aluno.tipo_deficiencia).all()

    return render_template('pei/dashboard_secretaria.html', 
                           total_peis=total_peis, 
                           homologados=peis_homologados,
                           stats=stats_deficiencia)