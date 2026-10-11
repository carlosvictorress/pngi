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


def _garantir_tabelas_multi():
    """Garante que as tabelas e colunas do módulo equipe multi existam no PostgreSQL."""
    try:
        AtendimentoMultiSOAP.__table__.create(db.engine, checkfirst=True)
        RelatorioEscutaEncaminhamento.__table__.create(db.engine, checkfirst=True)
        PlanoAcaoMensalMulti.__table__.create(db.engine, checkfirst=True)
    except Exception:
        db.session.rollback()

    try:
        from sqlalchemy import text
        with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            ddls = [
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS usuario_id INTEGER;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS profissional_id INTEGER;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS especialidade_emissor VARCHAR(50);",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(80);",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS orgao_destino VARCHAR(150);",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS motivo_demanda TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS sintese_escuta TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS sintese_escuta_qualificada TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS situacao_contextual TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS evidencias_observadas TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS acoes_ja_realizadas_escola TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS hipotese_ou_vulnerabilidade TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS providencias_recomendadas TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS sugestoes_encaminhamento TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS urgencia VARCHAR(20) DEFAULT 'Média';",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS gerado_com_ia BOOLEAN DEFAULT FALSE;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS ia_prompt_ou_modelo VARCHAR(100);",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS chave_autenticidade VARCHAR(64);",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'Emitido';",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS data_emissao DATE DEFAULT CURRENT_DATE;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",

                # Relaxamento seguro de NOT NULL para relatorios
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN especialidade_emissor DROP NOT NULL;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN sintese_escuta_qualificada DROP NOT NULL;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN sugestoes_encaminhamento DROP NOT NULL;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN acoes_ja_realizadas_escola DROP NOT NULL;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN profissional_id DROP NOT NULL;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN tipo_documento DROP NOT NULL;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN motivo_demanda TYPE TEXT;",
                "ALTER TABLE relatorios_escuta_encaminhamentos ALTER COLUMN motivo_demanda DROP NOT NULL;",

                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS usuario_id INTEGER;",
                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS profissional_id INTEGER;",
                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS compareceu BOOLEAN DEFAULT TRUE;",
                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS justificativa_falta VARCHAR(255);",
                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS encaminhamento_sugerido VARCHAR(150);",
                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'Finalizado';",
                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
                "ALTER TABLE atendimentos_multi_soap ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",

                # Relaxamento seguro de NOT NULL para atendimentos
                "ALTER TABLE atendimentos_multi_soap ALTER COLUMN profissional_id DROP NOT NULL;",
                "ALTER TABLE atendimentos_multi_soap ALTER COLUMN especialidade DROP NOT NULL;",
                "ALTER TABLE atendimentos_multi_soap ALTER COLUMN compareceu DROP NOT NULL;",
                "ALTER TABLE atendimentos_multi_soap ALTER COLUMN data_atendimento DROP NOT NULL;",

                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS usuario_coordenador_id INTEGER;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS coordenador_reuniao_id INTEGER;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS titulo VARCHAR(150);",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS pauta_discutida TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS local_reuniao VARCHAR(150) DEFAULT 'Secretaria Municipal de Educação';",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS profissionais_presentes TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS participantes_nomes TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS casos_discutidos_json TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS casos_discutidos TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS deliberacoes_gerais TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS encaminhamentos_gestao TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS metas_proximo_mes TEXT;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS chave_documento VARCHAR(64);",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS chave_autenticidade VARCHAR(64);",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
                "ALTER TABLE planos_acao_mensais_multi ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",

                # Conversão e relaxamento seguro de planos de acao
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN mes_referencia TYPE VARCHAR(50) USING mes_referencia::VARCHAR;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN mes_referencia DROP NOT NULL;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN ano_referencia DROP NOT NULL;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN coordenador_reuniao_id DROP NOT NULL;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN participantes_nomes DROP NOT NULL;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN pauta_discutida DROP NOT NULL;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN casos_discutidos DROP NOT NULL;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN encaminhamentos_gestao DROP NOT NULL;",
                "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN status DROP NOT NULL;"
            ]
            for cmd in ddls:
                try:
                    conn.execute(text(cmd))
                except Exception:
                    pass
    except Exception:
        db.session.rollback()

# =========================================================================
# 1. DASHBOARD PRINCIPAL DA EQUIPE MULTIDISCIPLINAR
# =========================================================================
@equipe_multi_bp.route('/')
@login_required
def dashboard():
    """Painel Integrado da Equipe Multidisciplinar (Psicologia, Psicopedagogia e Serviço Social)."""
    _garantir_tabelas_multi()
    try:
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
    except Exception as e:
        db.session.rollback()
        print(f"[AVISO] Falha no dashboard da equipe multi: {e}")
        total_atendimentos = total_psicologia = total_psicopedagogia = total_servico_social = total_relatorios = total_planos_acao = total_estudantes_atendidos = 0
        ultimos_atendimentos = []
        ultimos_planos = []

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
    _garantir_tabelas_multi()
    especialidade = request.args.get('especialidade', '')
    aluno_id = request.args.get('aluno_id', type=int)
    busca = request.args.get('busca', '').strip()

    try:
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
    except Exception as e:
        db.session.rollback()
        print(f"[AVISO] Falha ao listar atendimentos SOAP: {e}")
        atendimentos = []

    try:
        alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    except Exception:
        db.session.rollback()
        alunos = []

    return render_template(
        'equipe_multi/atendimentos.html',
        atendimentos=atendimentos,
        alunos=alunos,
        especialidade_filtro=especialidade,
        aluno_filtro=aluno_id,
        busca=busca,
        now=datetime.utcnow()
    )


@equipe_multi_bp.route('/atendimentos/novo', methods=['GET', 'POST'])
@login_required
def novo_atendimento_soap():
    """Formulário para Registro de Atendimento com metodologia SOAP Especializada."""
    _garantir_tabelas_multi()
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

            try:
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
            except Exception as e:
                db.session.rollback()
                flash(f"Aviso ao salvar atendimento SOAP: {e}", "erro")

    try:
        alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    except Exception:
        db.session.rollback()
        alunos = []

    return render_template(
        'equipe_multi/formulario_soap.html',
        alunos=alunos,
        aluno_selecionado=aluno_selecionado,
        now=datetime.utcnow()
    )


@equipe_multi_bp.route('/atendimentos/<int:id>/imprimir')
@login_required
def imprimir_atendimento_soap(id):
    """Visualização e impressão timbrada do registro SOAP institucional."""
    _garantir_tabelas_multi()
    atendimento = AtendimentoMultiSOAP.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    return render_template('equipe_multi/imprimir_soap.html', atendimento=atendimento, now=datetime.utcnow())


# =========================================================================
# 3. RELATÓRIOS DE ESCUTA QUALIFICADA & ENCAMINHAMENTOS COM ASSISTÊNCIA DE IA
# =========================================================================
@equipe_multi_bp.route('/relatorios')
@login_required
def listar_relatorios():
    """Listagem de Relatórios de Escuta Qualificada e Encaminhamentos emitidos."""
    _garantir_tabelas_multi()
    tipo = request.args.get('tipo', '')
    busca = request.args.get('busca', '').strip()

    try:
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
    except Exception as e:
        db.session.rollback()
        print(f"[AVISO] Falha ao carregar relatórios de escuta: {e}")
        relatorios = []

    try:
        alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    except Exception:
        db.session.rollback()
        alunos = []

    return render_template(
        'equipe_multi/relatorios.html',
        relatorios=relatorios,
        alunos=alunos,
        tipo_filtro=tipo,
        busca=busca,
        now=datetime.utcnow()
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
    _garantir_tabelas_multi()
    aluno_pre = request.args.get('aluno_id', type=int)
    aluno_selecionado = Aluno.query.filter_by(id=aluno_pre, municipio_id=g.municipio.id).first() if aluno_pre else None

    if request.method == 'POST':
        aluno_id = request.form.get('aluno_id', type=int)
        tipo_doc = request.form.get('tipo_documento', 'Relatório de Escuta Qualificada')
        especialidade_emissor = request.form.get('especialidade') or request.form.get('especialidade_emissor') or (current_user.perfil.title() if getattr(current_user, 'perfil', None) else 'Equipe Multidisciplinar')
        orgao_destino = request.form.get('orgao_destino', 'CAPS Infantil').strip()
        motivo = request.form.get('motivo_demanda', '').strip()
        sintese = request.form.get('sintese_escuta', '').strip()
        contexto = request.form.get('situacao_contextual', '').strip()
        hipotese = request.form.get('hipotese_ou_vulnerabilidade', '').strip()
        providencias = request.form.get('providencias_recomendadas', '').strip()
        acoes_escola = request.form.get('acoes_ja_realizadas_escola', '').strip() or contexto or 'Acompanhamento pedagógico regular.'
        urgencia = request.form.get('urgencia', 'Média')
        gerado_ia = request.form.get('gerado_com_ia') == 'true' or request.form.get('gerado_com_ia') == '1'

        if not aluno_id or not motivo or not sintese or not orgao_destino:
            flash("Informe o aluno, órgão de destino, motivo e a síntese da escuta qualificada.", "erro")
        else:
            chave_aut = f"REL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            
            try:
                novo_rel = RelatorioEscutaEncaminhamento(
                    municipio_id=g.municipio.id,
                    aluno_id=aluno_id,
                    usuario_id=current_user.id,
                    profissional_id=current_user.id,
                    especialidade_emissor=especialidade_emissor,
                    tipo_documento=tipo_doc,
                    orgao_destino=orgao_destino,
                    motivo_demanda=motivo,
                    sintese_escuta=sintese,
                    sintese_escuta_qualificada=sintese,
                    situacao_contextual=contexto,
                    evidencias_observadas=contexto,
                    acoes_ja_realizadas_escola=acoes_escola,
                    hipotese_ou_vulnerabilidade=hipotese,
                    providencias_recomendadas=providencias,
                    sugestoes_encaminhamento=providencias,
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
            except Exception as e:
                db.session.rollback()
                flash(f"Aviso ao registrar relatório: {e}", "erro")

    try:
        alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    except Exception:
        db.session.rollback()
        alunos = []

    return render_template(
        'equipe_multi/formulario_relatorio.html',
        alunos=alunos,
        aluno_selecionado=aluno_selecionado,
        now=datetime.utcnow()
    )


@equipe_multi_bp.route('/relatorios/<int:id>/imprimir')
@login_required
def imprimir_relatorio_escuta(id):
    """Página timbrada oficial para impressão do Relatório de Escuta / Encaminhamento."""
    _garantir_tabelas_multi()
    relatorio = RelatorioEscutaEncaminhamento.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    return render_template('equipe_multi/imprimir_relatorio.html', relatorio=relatorio, now=datetime.utcnow())


# =========================================================================
# 4. PLANOS DE AÇÃO MENSAIS (REUNIÕES DE CASOS & APRESENTAÇÃO À GESTÃO)
# =========================================================================
@equipe_multi_bp.route('/planos-acao')
@login_required
def listar_planos_acao():
    """Listagem de Reuniões Mensais de Estudo de Casos e Planos de Ação."""
    _garantir_tabelas_multi()
    ano = request.args.get('ano', type=int) or datetime.utcnow().year
    try:
        planos = PlanoAcaoMensalMulti.query.filter_by(municipio_id=g.municipio.id, ano_referencia=ano)\
            .order_by(PlanoAcaoMensalMulti.data_reuniao.desc()).all()
    except Exception as e:
        db.session.rollback()
        print(f"[AVISO] Falha ao carregar planos de ação: {e}")
        planos = []

    return render_template(
        'equipe_multi/planos_acao.html',
        planos=planos,
        ano_selecionado=ano,
        now=datetime.utcnow()
    )


@equipe_multi_bp.route('/planos-acao/novo', methods=['GET', 'POST'])
@login_required
def novo_plano_acao():
    """Registro da Reunião Mensal Multidisciplinar e Plano de Ação Estratégico."""
    _garantir_tabelas_multi()
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

            try:
                novo_plano = PlanoAcaoMensalMulti(
                    municipio_id=g.municipio.id,
                    usuario_coordenador_id=current_user.id,
                    coordenador_reuniao_id=current_user.id,
                    titulo=titulo,
                    pauta_discutida=titulo,
                    mes_referencia=mes,
                    ano_referencia=ano,
                    data_reuniao=data_reuniao,
                    local_reuniao=local,
                    profissionais_presentes=presentes,
                    participantes_nomes=presentes,
                    casos_discutidos_json=casos_json_raw,
                    casos_discutidos=casos_json_raw or 'Discussão geral de casos da rede',
                    acoes_psicologia=acoes_psi,
                    acoes_psicopedagogia=acoes_psicoped,
                    acoes_servico_social=acoes_social,
                    deliberacoes_gerais=deliberacoes,
                    encaminhamentos_gestao=deliberacoes or 'Encaminhamentos pactuados em ata.',
                    metas_proximo_mes=metas_proximo,
                    status='Aprovado em Reunião',
                    chave_documento=chave_doc,
                    chave_autenticidade=chave_doc
                )
                db.session.add(novo_plano)
                db.session.commit()
                flash(f"Plano de Ação Mensal '{titulo}' homologado com sucesso!", "sucesso")
                return redirect(url_for('equipe_multi.listar_planos_acao', municipio_slug=g.municipio.slug))
            except Exception as e:
                db.session.rollback()
                flash(f"Aviso ao registrar plano de ação: {e}", "erro")

    try:
        alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(Aluno.nome).all()
    except Exception:
        db.session.rollback()
        alunos = []

    try:
        profissionais = Usuario.query.filter(
            Usuario.municipio_id == g.municipio.id,
            Usuario.perfil.in_(['psicologo', 'psicopedagogo', 'assistente_social', 'aee', 'secretaria'])
        ).all()
    except Exception:
        db.session.rollback()
        profissionais = []

    return render_template(
        'equipe_multi/formulario_plano.html',
        alunos=alunos,
        profissionais=profissionais,
        mes_atual=datetime.utcnow().strftime('%B'),
        ano_atual=datetime.utcnow().year,
        now=datetime.utcnow()
    )


@equipe_multi_bp.route('/planos-acao/<int:id>')
@login_required
def detalhes_plano_acao(id):
    """Exibição detalhada do Plano de Ação Mensal e Ata Técnica."""
    _garantir_tabelas_multi()
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
        casos=casos,
        now=datetime.utcnow()
    )


@equipe_multi_bp.route('/planos-acao/<int:id>/imprimir')
@login_required
def imprimir_plano_acao(id):
    """
    DOCUMENTO OFICIAL TIMBRADO PARA APRESENTAÇÃO À GESTÃO ESCOLAR / SECRETARIA.
    Contém a ata, estudo de casos, metas setoriais e folha de assinaturas da equipe.
    """
    _garantir_tabelas_multi()
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
        casos=casos,
        now=datetime.utcnow()
    )
