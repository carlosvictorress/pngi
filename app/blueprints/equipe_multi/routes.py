import os
import uuid
import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    Municipio, Aluno, Escola, Usuario, ProfissionalAEE,
    AtendimentoMultiSOAP, RelatorioEscutaEncaminhamento, PlanoAcaoMensalMulti
)
from app.services.ia_generator import gerar_minuta_escuta_ia

equipe_multi_bp = Blueprint('equipe_multi', __name__)

@equipe_multi_bp.url_value_preprocessor
def get_municipio_slug(endpoint, values):
    """Extrai <municipio_slug> da URL e injeta no contexto g."""
    if values and 'municipio_slug' in values:
        g.municipio_slug = values.pop('municipio_slug')
        g.municipio = Municipio.query.filter_by(slug=g.municipio_slug).first()
    if not g.municipio:
        abort(404)


# =========================================================================
# 1. DASHBOARD PRINCIPAL DA EQUIPE MULTIDISCIPLINAR
# =========================================================================
@equipe_multi_bp.route('/')
@login_required
def dashboard():
    """Painel Integrado da Equipe Multidisciplinar (Psicologia, Psicopedagogia e Serviço Social)."""
    # Métricas Gerais
    total_atendimentos = AtendimentoMultiSOAP.query.filter_by(municipio_id=g.municipio.id).count()
    total_psicologia = AtendimentoMultiSOAP.query.filter_by(municipio_id=g.municipio.id, especialidade='psicologo').count()
    total_psicopedagogia = AtendimentoMultiSOAP.query.filter_by(municipio_id=g.municipio.id, especialidade='psicopedagogo').count()
    total_servico_social = AtendimentoMultiSOAP.query.filter_by(municipio_id=g.municipio.id, especialidade='assistente_social').count()
    
    total_relatorios = RelatorioEscutaEncaminhamento.query.filter_by(municipio_id=g.municipio.id).count()
    total_planos_acao = PlanoAcaoMensalMulti.query.filter_by(municipio_id=g.municipio.id).count()

    # Últimos Atendimentos
    ultimos_atendimentos = AtendimentoMultiSOAP.query.filter_by(municipio_id=g.municipio.id)\
        .order_by(AtendimentoMultiSOAP.data_atendimento.desc(), AtendimentoMultiSOAP.id.desc()).limit(6).all()

    # Últimos Planos de Ação Mensais
    ultimos_planos = PlanoAcaoMensalMulti.query.filter_by(municipio_id=g.municipio.id)\
        .order_by(PlanoAcaoMensalMulti.ano_referencia.desc(), PlanoAcaoMensalMulti.data_reuniao.desc()).limit(3).all()

    # Total de estudantes únicos acompanhados pela equipe multi
    alunos_ids = db.session.query(AtendimentoMultiSOAP.aluno_id).filter_by(municipio_id=g.municipio.id).distinct().all()
    total_estudantes_atendidos = len(alunos_ids)

    return render_template(
        'equipe_multi/dashboard.html',
        total_atendimentos=total_atendimentos,
        total_psicologia=total_psicologia,
        total_psicopedagogia=total_psicopedagogia,
        total_servico_social=total_servico_social,
        total_relatorios=total_relatorios,
        total_planos_acao=total_planos_acao,
        total_estudantes_atendidos=total_estudantes_atendidos,
        ultimos_atendimentos=ultimos_atendimentos,
        ultimos_planos=ultimos_planos
    )


# =========================================================================
# 2. ATENDIMENTOS COM METODOLOGIA SOAP INSTITUCIONAL
# =========================================================================
@equipe_multi_bp.route('/atendimentos')
@login_required
def listar_atendimentos():
    """Listagem de Atendimentos SOAP com filtros por área, busca e aluno."""
    especialidade = request.args.get('especialidade', '')
    aluno_id = request.args.get('aluno_id', type=int)
    busca = request.args.get('busca', '').strip()

    query = AtendimentoMultiSOAP.query.filter_by(municipio_id=g.municipio.id)

    if especialidade:
        query = query.filter(AtendimentoMultiSOAP.especialidade == especialidade)
    if aluno_id:
        query = query.filter(AtendimentoMultiSOAP.aluno_id == aluno_id)
    if busca:
        query = query.join(Aluno).filter(
            (Aluno.nome.ilike(f"%{busca}%")) | 
            (Aluno.cpf.ilike(f"%{busca}%")) |
            (AtendimentoMultiSOAP.soap_subjetivo.ilike(f"%{busca}%"))
        )

    atendimentos = query.order_by(AtendimentoMultiSOAP.data_atendimento.desc(), AtendimentoMultiSOAP.id.desc()).all()
    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()

    return render_template(
        'equipe_multi/atendimentos.html',
        atendimentos=atendimentos,
        alunos=alunos,
        especialidade_filtro=especialidade,
        aluno_filtro=aluno_id,
        busca=busca
    )


@equipe_multi_bp.route('/atendimentos/novo', methods=['GET', 'POST'])
@login_required
def novo_atendimento_soap():
    """Formulário para Registro de Atendimento com metodologia SOAP Especializada."""
    aluno_pre = request.args.get('aluno_id', type=int)
    aluno_selecionado = Aluno.query.filter_by(id=aluno_pre, municipio_id=g.municipio.id).first() if aluno_pre else None

    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id', type=int)
        especialidade = request.form.get('especialidade', 'psicologo')
        data_str = request.form.get('data_atendimento')
        horario_inicio = request.form.get('horario_inicio', '')
        horario_fim = request.form.get('horario_fim', '')
        tipo_sessao = request.form.get('tipo_sessao', 'Individual')
        
        soap_s = request.form.get('soap_subjetivo', '').strip()
        soap_o = request.form.get('soap_objetivo', '').strip()
        soap_a = request.form.get('soap_avaliacao', '').strip()
        soap_p = request.form.get('soap_plano', '').strip()
        encaminhamento = request.form.get('encaminhamento_sugerido', '').strip()
        sigilo = request.form.get('sigilo_etico') == 'on' or request.form.get('sigilo_etico') == 'true'

        if not aluno_id or not soap_s or not soap_o or not soap_a or not soap_p:
            flash("Preencha todos os 4 campos do SOAP Institucional (Subjetivo, Objetivo, Avaliação e Plano).", "erro")
        else:
            try:
                data_atend = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else datetime.utcnow().date()
            except Exception:
                data_atend = datetime.utcnow().date()

            novo_soap = AtendimentoMultiSOAP(
                municipio_id=g.municipio.id,
                aluno_id=aluno_id,
                usuario_id=current_user.id,
                especialidade=especialidade,
                data_atendimento=data_atend,
                horario_inicio=horario_inicio,
                horario_fim=horario_fim,
                tipo_sessao=tipo_sessao,
                soap_subjetivo=soap_s,
                soap_objetivo=soap_o,
                soap_avaliacao=soap_a,
                soap_plano=soap_p,
                encaminhamento_sugerido=encaminhamento,
                sigilo_etico=sigilo,
                status='Finalizado'
            )
            db.session.add(novo_soap)
            db.session.commit()
            flash("Atendimento SOAP registrado com sucesso na ficha multiprofissional do estudante!", "sucesso")
            return redirect(url_for('equipe_multi.listar_atendimentos', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    return render_template(
        'equipe_multi/formulario_soap.html',
        alunos=alunos,
        aluno_selecionado=aluno_selecionado
    )


@equipe_multi_bp.route('/atendimentos/<int:id>/imprimir')
@login_required
def imprimir_atendimento_soap(id):
    """Visualização e impressão timbrada do registro SOAP institucional."""
    atendimento = AtendimentoMultiSOAP.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    return render_template('equipe_multi/imprimir_soap.html', atendimento=atendimento)


# =========================================================================
# 3. RELATÓRIOS DE ESCUTA QUALIFICADA & ENCAMINHAMENTOS COM ASSISTÊNCIA DE IA
# =========================================================================
@equipe_multi_bp.route('/relatorios')
@login_required
def listar_relatorios():
    """Listagem de Relatórios de Escuta Qualificada e Encaminhamentos emitidos."""
    tipo = request.args.get('tipo', '')
    busca = request.args.get('busca', '').strip()

    query = RelatorioEscutaEncaminhamento.query.filter_by(municipio_id=g.municipio.id)

    if tipo:
        query = query.filter(RelatorioEscutaEncaminhamento.tipo_documento == tipo)
    if busca:
        query = query.join(Aluno).filter(
            (Aluno.nome.ilike(f"%{busca}%")) |
            (RelatorioEscutaEncaminhamento.orgao_destino.ilike(f"%{busca}%")) |
            (RelatorioEscutaEncaminhamento.chave_autenticidade.ilike(f"%{busca}%"))
        )

    relatorios = query.order_by(RelatorioEscutaEncaminhamento.data_emissao.desc(), RelatorioEscutaEncaminhamento.id.desc()).all()
    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()

    return render_template(
        'equipe_multi/relatorios.html',
        relatorios=relatorios,
        alunos=alunos,
        tipo_filtro=tipo,
        busca=busca
    )


@equipe_multi_bp.route('/relatorios/api-gerar-ia', methods=['POST'])
@login_required
def api_gerar_ia():
    """Endpoint AJAX que aciona a IA para elaborar a minuta do relatório técnico."""
    data = request.get_json() or {}
    
    aluno_id = data.get('aluno_id')
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first() if aluno_id else None

    # Prepara payload com dados reais do estudante e da demanda
    payload = {
        'aluno_nome': aluno.nome if aluno else data.get('aluno_nome', 'Estudante'),
        'aluno_idade': aluno.data_nascimento if aluno else 'Não informada',
        'escola': aluno.escola.nome if (aluno and aluno.escola) else 'Rede Municipal',
        'turma': f"{aluno.turma} ({aluno.etapa_ensino or ''})" if aluno else 'Regular',
        'diagnostico': (f"CID {aluno.cid}" if aluno.cid else ("Em Investigação" if aluno.em_investigacao else "Acompanhamento Preventivo")) if aluno else "Não informado",
        'especialidade': data.get('especialidade', current_user.perfil or 'Equipe Multi'),
        'profissional_nome': current_user.nome,
        'motivo_demanda': data.get('motivo_demanda', ''),
        'pontos_escuta': data.get('pontos_escuta', ''),
        'orgao_destino': data.get('orgao_destino', 'Rede Intersetorial Municipal')
    }

    resultado_ia = gerar_minuta_escuta_ia(payload)
    return jsonify({'sucesso': True, 'resultado': resultado_ia})


@equipe_multi_bp.route('/relatorios/novo', methods=['GET', 'POST'])
@login_required
def novo_relatorio_escuta():
    """Emissão de Relatório de Escuta Qualificada ou Encaminhamento Intersetorial."""
    aluno_pre = request.args.get('aluno_id', type=int)
    aluno_selecionado = Aluno.query.filter_by(id=aluno_pre, municipio_id=g.municipio.id).first() if aluno_pre else None

    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id', type=int)
        tipo_doc = request.form.get('tipo_documento', 'Relatório de Escuta Qualificada')
        orgao_destino = request.form.get('orgao_destino', 'CAPS Infantil').strip()
        motivo = request.form.get('motivo_demanda', '').strip()
        sintese = request.form.get('sintese_escuta', '').strip()
        contexto = request.form.get('situacao_contextual', '').strip()
        hipotese = request.form.get('hipotese_ou_vulnerabilidade', '').strip()
        providencias = request.form.get('providencias_recomendadas', '').strip()
        urgencia = request.form.get('urgencia', 'Média')
        gerado_ia = request.form.get('gerado_com_ia') == 'true' or request.form.get('gerado_com_ia') == '1'

        if not aluno_id or not motivo or not sintese or not orgao_destino:
            flash("Informe o aluno, órgão de destino, motivo e a síntese da escuta qualificada.", "erro")
        else:
            chave_aut = f"REL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            
            novo_rel = RelatorioEscutaEncaminhamento(
                municipio_id=g.municipio.id,
                aluno_id=aluno_id,
                usuario_id=current_user.id,
                tipo_documento=tipo_doc,
                orgao_destino=orgao_destino,
                motivo_demanda=motivo,
                sintese_escuta=sintese,
                situacao_contextual=contexto,
                hipotese_ou_vulnerabilidade=hipotese,
                providencias_recomendadas=providencias,
                urgencia=urgencia,
                gerado_com_ia=gerado_ia,
                ia_prompt_ou_modelo='ORBI Intelligence v1 (SECADI/SUAS)' if gerado_ia else None,
                chave_autenticidade=chave_aut,
                status='Emitido',
                data_emissao=datetime.utcnow().date()
            )
            db.session.add(novo_rel)
            db.session.commit()
            flash(f"Documento institucional gerado com sucesso! Chave de validação: {chave_aut}", "sucesso")
            return redirect(url_for('equipe_multi.listar_relatorios', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    return render_template(
        'equipe_multi/formulario_relatorio.html',
        alunos=alunos,
        aluno_selecionado=aluno_selecionado
    )


@equipe_multi_bp.route('/relatorios/<int:id>/imprimir')
@login_required
def imprimir_relatorio_escuta(id):
    """Página timbrada oficial para impressão do Relatório de Escuta / Encaminhamento."""
    relatorio = RelatorioEscutaEncaminhamento.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    return render_template('equipe_multi/imprimir_relatorio.html', relatorio=relatorio)


# =========================================================================
# 4. PLANOS DE AÇÃO MENSAIS (REUNIÕES DE CASOS & APRESENTAÇÃO À GESTÃO)
# =========================================================================
@equipe_multi_bp.route('/planos-acao')
@login_required
def listar_planos_acao():
    """Listagem de Reuniões Mensais de Estudo de Casos e Planos de Ação."""
    ano = request.args.get('ano', type=int) or datetime.utcnow().year
    planos = PlanoAcaoMensalMulti.query.filter_by(municipio_id=g.municipio.id, ano_referencia=ano)\
        .order_by(PlanoAcaoMensalMulti.data_reuniao.desc()).all()

    return render_template(
        'equipe_multi/planos_acao.html',
        planos=planos,
        ano_selecionado=ano
    )


@equipe_multi_bp.route('/planos-acao/novo', methods=['GET', 'POST'])
@login_required
def novo_plano_acao():
    """Registro da Reunião Mensal Multidisciplinar e Plano de Ação Estratégico."""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        mes = request.form.get('mes_referencia', 'Outubro')
        ano = request.form.get('ano_referencia', type=int) or datetime.utcnow().year
        data_str = request.form.get('data_reuniao')
        local = request.form.get('local_reuniao', 'Secretaria Municipal de Educação').strip()
        presentes = request.form.get('profissionais_presentes', '').strip()
        
        # Casos Estudados e Direcionamentos
        casos_json_raw = request.form.get('casos_discutidos_json', '').strip()
        
        # Ações Setoriais Solicitadas
        acoes_psi = request.form.get('acoes_psicologia', '').strip()
        acoes_psicoped = request.form.get('acoes_psicopedagogia', '').strip()
        acoes_social = request.form.get('acoes_servico_social', '').strip()
        deliberacoes = request.form.get('deliberacoes_gerais', '').strip()
        metas_proximo = request.form.get('metas_proximo_mes', '').strip()

        if not titulo or not presentes:
            flash("Informe o título da reunião e os profissionais presentes.", "erro")
        else:
            try:
                data_reuniao = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else datetime.utcnow().date()
            except Exception:
                data_reuniao = datetime.utcnow().date()

            chave_doc = f"PLANO-MULTI-{ano}-{uuid.uuid4().hex[:6].upper()}"

            novo_plano = PlanoAcaoMensalMulti(
                municipio_id=g.municipio.id,
                usuario_coordenador_id=current_user.id,
                titulo=titulo,
                mes_referencia=mes,
                ano_referencia=ano,
                data_reuniao=data_reuniao,
                local_reuniao=local,
                profissionais_presentes=presentes,
                casos_discutidos_json=casos_json_raw,
                acoes_psicologia=acoes_psi,
                acoes_psicopedagogia=acoes_psicoped,
                acoes_servico_social=acoes_social,
                deliberacoes_gerais=deliberacoes,
                metas_proximo_mes=metas_proximo,
                status='Aprovado em Reunião',
                chave_documento=chave_doc
            )
            db.session.add(novo_plano)
            db.session.commit()
            flash(f"Plano de Ação Mensal '{titulo}' homologado com sucesso!", "sucesso")
            return redirect(url_for('equipe_multi.listar_planos_acao', municipio_slug=g.municipio.slug))

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    profissionais = Usuario.query.filter(
        Usuario.municipio_id == g.municipio.id,
        Usuario.perfil.in_(['psicologo', 'psicopedagogo', 'assistente_social', 'aee', 'secretaria'])
    ).all()

    return render_template(
        'equipe_multi/formulario_plano.html',
        alunos=alunos,
        profissionais=profissionais,
        mes_atual=datetime.utcnow().strftime('%B'),
        ano_atual=datetime.utcnow().year
    )


@equipe_multi_bp.route('/planos-acao/<int:id>')
@login_required
def detalhes_plano_acao(id):
    """Exibição detalhada do Plano de Ação Mensal e Ata Técnica."""
    plano = PlanoAcaoMensalMulti.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    
    # Decodifica os casos discutidos se salvos em JSON
    casos = []
    if plano.casos_discutidos_json:
        try:
            casos = json.loads(plano.casos_discutidos_json)
        except Exception:
            casos = []

    return render_template(
        'equipe_multi/detalhes_plano.html',
        plano=plano,
        casos=casos
    )


@equipe_multi_bp.route('/planos-acao/<int:id>/imprimir')
@login_required
def imprimir_plano_acao(id):
    """
    DOCUMENTO OFICIAL TIMBRADO PARA APRESENTAÇÃO À GESTÃO ESCOLAR / SECRETARIA.
    Contém a ata, estudo de casos, metas setoriais e folha de assinaturas da equipe.
    """
    plano = PlanoAcaoMensalMulti.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    
    casos = []
    if plano.casos_discutidos_json:
        try:
            casos = json.loads(plano.casos_discutidos_json)
        except Exception:
            casos = []

    return render_template(
        'equipe_multi/imprimir_plano.html',
        plano=plano,
        casos=casos
    )
