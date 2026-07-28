from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from flask_login import login_required, current_user
from app import db
from app.models import Municipio, Aluno, TransporteAlunado, RotaTransporte

transporte_bp = Blueprint('transporte', __name__)

@transporte_bp.url_value_preprocessor
def get_municipio_slug(endpoint, values):
    """Captura o <municipio_slug> da URL e o injeta no contexto global 'g'."""
    if values and 'municipio_slug' in values:
        g.municipio_slug = values.pop('municipio_slug')
        g.municipio = Municipio.query.filter_by(slug=g.municipio_slug).first()
    if not g.municipio:
        abort(404)

# -------------------------------------------------------------------------
# 1. DASHBOARD PRINCIPAL DO TRANSPORTE ESCOLAR INCLUSIVO
# -------------------------------------------------------------------------
@transporte_bp.route('/')
@login_required
def home():
    """Painel principal do transporte escolar adaptado."""
    if current_user.perfil not in ['secretaria', 'superadmin', 'transporte', 'diretor', 'aee', 'professor']:
        abort(403)

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).all()
    rotas = RotaTransporte.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(RotaTransporte.nome_rota).all()

    # Cálculo dos indicadores principais
    alunos_transportados = []
    total_cadeirantes = 0
    total_monitores = 0
    total_veiculos_adaptados = 0

    for a in alunos:
        t_dados = TransporteAlunado.query.filter_by(aluno_id=a.id).first()
        if a.necessita_transporte_adaptado or a.cadeirante or a.necessita_acompanhante or (t_dados and t_dados.rota_id):
            alunos_transportados.append({
                'aluno': a,
                'transporte': t_dados,
                'rota': t_dados.rota if t_dados and t_dados.rota else None
            })
            if a.cadeirante or (t_dados and t_dados.cadeirante):
                total_cadeirantes += 1
            if a.possui_monitor_rota or (t_dados and t_dados.possui_monitor_rota):
                total_monitores += 1
            if a.necessita_transporte_adaptado or (t_dados and t_dados.necessita_veiculo_adaptado):
                total_veiculos_adaptados += 1

    total_transportados = len(alunos_transportados)
    total_rotas = len(rotas)

    return render_template(
        'transporte/dashboard_transporte.html',
        alunos_transportados=alunos_transportados,
        rotas=rotas,
        total_transportados=total_transportados,
        total_cadeirantes=total_cadeirantes,
        total_monitores=total_monitores,
        total_veiculos_adaptados=total_veiculos_adaptados,
        total_rotas=total_rotas,
        todos_alunos=alunos
    )

# -------------------------------------------------------------------------
# 2. GESTÃO E CADASTRO DE ROTAS
# -------------------------------------------------------------------------
@transporte_bp.route('/rotas', methods=['GET', 'POST'])
@login_required
def gerenciar_rotas():
    """Listagem e criação de Rotas de Transporte Inclusivo."""
    if current_user.perfil not in ['secretaria', 'superadmin', 'transporte', 'diretor', 'aee', 'professor']:
        abort(403)

    if request.method == 'POST':
        codigo_rota = request.form.get('codigo_rota', '').strip()
        nome_rota = request.form.get('nome_rota', '').strip()
        motorista_nome = request.form.get('motorista_nome', '').strip()
        motorista_telefone = request.form.get('motorista_telefone', '').strip()
        monitor_nome = request.form.get('monitor_nome', '').strip()
        monitor_telefone = request.form.get('monitor_telefone', '').strip()
        placa_veiculo = request.form.get('placa_veiculo', '').strip()
        tipo_veiculo = request.form.get('tipo_veiculo', 'Van Adaptada')
        capacidade_cadeirantes = request.form.get('capacidade_cadeirantes', 2)
        turno = request.form.get('turno', 'Manhã e Tarde')

        if not codigo_rota or not nome_rota:
            flash("Código e Nome da rota são obrigatórios!", "erro")
        else:
            nova_rota = RotaTransporte(
                municipio_id=g.municipio.id,
                codigo_rota=codigo_rota,
                nome_rota=nome_rota,
                motorista_nome=motorista_nome,
                motorista_telefone=motorista_telefone,
                monitor_nome=monitor_nome,
                monitor_telefone=monitor_telefone,
                placa_veiculo=placa_veiculo,
                tipo_veiculo=tipo_veiculo,
                capacidade_cadeirantes=int(capacidade_cadeirantes),
                turno=turno
            )
            db.session.add(nova_rota)
            db.session.commit()
            flash(f"Rota '{codigo_rota} — {nome_rota}' cadastrada com sucesso!", "sucesso")
            return redirect(url_for('transporte.gerenciar_rotas', municipio_slug=g.municipio.slug))

    rotas = RotaTransporte.query.filter_by(municipio_id=g.municipio.id, ativo=True).order_by(RotaTransporte.codigo_rota).all()
    return render_template('transporte/rotas.html', rotas=rotas)

@transporte_bp.route('/rotas/<int:rota_id>')
@login_required
def detalhes_rota(rota_id):
    """Ficha detalhada e itinerário da rota para o motorista/monitor."""
    if current_user.perfil not in ['secretaria', 'superadmin', 'transporte', 'diretor', 'aee', 'professor']:
        abort(403)

    rota = RotaTransporte.query.filter_by(id=rota_id, municipio_id=g.municipio.id).first_or_404()
    alunos_vinculados = TransporteAlunado.query.filter_by(rota_id=rota.id).all()

    return render_template(
        'transporte/detalhes_rota.html',
        rota=rota,
        alunos_vinculados=alunos_vinculados
    )

@transporte_bp.route('/rotas/<int:rota_id>/editar', methods=['POST'])
@login_required
def editar_rota(rota_id):
    """Edita dados da rota."""
    if current_user.perfil not in ['secretaria', 'superadmin', 'transporte', 'diretor', 'aee', 'professor']:
        abort(403)

    rota = RotaTransporte.query.filter_by(id=rota_id, municipio_id=g.municipio.id).first_or_404()

    rota.codigo_rota = request.form.get('codigo_rota', '').strip()
    rota.nome_rota = request.form.get('nome_rota', '').strip()
    rota.motorista_nome = request.form.get('motorista_nome', '').strip()
    rota.motorista_telefone = request.form.get('motorista_telefone', '').strip()
    rota.monitor_nome = request.form.get('monitor_nome', '').strip()
    rota.monitor_telefone = request.form.get('monitor_telefone', '').strip()
    rota.placa_veiculo = request.form.get('placa_veiculo', '').strip()
    rota.tipo_veiculo = request.form.get('tipo_veiculo', 'Van Adaptada')
    rota.capacidade_cadeirantes = int(request.form.get('capacidade_cadeirantes', 2))
    rota.turno = request.form.get('turno', 'Manhã e Tarde')

    db.session.commit()
    flash(f"Rota '{rota.codigo_rota}' atualizada com sucesso!", "sucesso")
    return redirect(url_for('transporte.gerenciar_rotas', municipio_slug=g.municipio.slug))

@transporte_bp.route('/rotas/<int:rota_id>/excluir')
@login_required
def excluir_rota(rota_id):
    """Desativa uma rota do sistema."""
    if current_user.perfil not in ['secretaria', 'superadmin', 'transporte', 'diretor', 'aee', 'professor']:
        abort(403)

    rota = RotaTransporte.query.filter_by(id=rota_id, municipio_id=g.municipio.id).first_or_404()
    rota.ativo = False
    
    # Desvincula alunos da rota
    TransporteAlunado.query.filter_by(rota_id=rota.id).update({'rota_id': None})
    db.session.commit()

    flash(f"Rota '{rota.codigo_rota}' foi desativada.", "sucesso")
    return redirect(url_for('transporte.gerenciar_rotas', municipio_slug=g.municipio.slug))

# -------------------------------------------------------------------------
# 3. VÍNCULO E LOGÍSTICA DO ESTUDANTE
# -------------------------------------------------------------------------
@transporte_bp.route('/aluno/<int:aluno_id>/vincular', methods=['POST'])
@login_required
def vincular_aluno(aluno_id):
    """Atribui ou atualiza as configurações de transporte do aluno."""
    if current_user.perfil not in ['secretaria', 'superadmin', 'transporte', 'diretor', 'aee', 'professor']:
        abort(403)

    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()

    rota_id = request.form.get('rota_id')
    ponto_embarque = request.form.get('ponto_embarque', '').strip()
    horario_embarque = request.form.get('horario_embarque', '').strip()
    horario_desembarque = request.form.get('horario_desembarque', '').strip()
    observacoes_logistica = request.form.get('observacoes_logistica', '').strip()

    necessita_veiculo = 'necessita_veiculo_adaptado' in request.form
    cadeirante = 'cadeirante' in request.form
    necessita_acompanhante = 'necessita_acompanhante' in request.form
    possui_monitor_rota = 'possui_monitor_rota' in request.form

    # Atualiza na ficha do aluno
    aluno.necessita_transporte_adaptado = necessita_veiculo
    aluno.cadeirante = cadeirante
    aluno.necessita_acompanhante = necessita_acompanhante
    aluno.possui_monitor_rota = possui_monitor_rota

    # Atualiza ou cria em TransporteAlunado
    t_dados = TransporteAlunado.query.filter_by(aluno_id=aluno.id).first()
    if not t_dados:
        t_dados = TransporteAlunado(aluno_id=aluno.id)
        db.session.add(t_dados)

    t_dados.rota_id = int(rota_id) if rota_id and rota_id != 'none' else None
    if t_dados.rota_id:
        rota_obj = RotaTransporte.query.get(t_dados.rota_id)
        if rota_obj:
            t_dados.rota_codigo = rota_obj.codigo_rota

    t_dados.ponto_embarque = ponto_embarque
    t_dados.horario_embarque = horario_embarque
    t_dados.horario_desembarque = horario_desembarque
    t_dados.observacoes_logistica = observacoes_logistica
    t_dados.necessita_veiculo_adaptado = necessita_veiculo
    t_dados.cadeirante = cadeirante
    t_dados.necessita_acompanhante = necessita_acompanhante
    t_dados.possui_monitor_rota = possui_monitor_rota

    db.session.commit()
    flash(f"Logística de transporte de '{aluno.nome}' atualizada!", "sucesso")
    return redirect(url_for('transporte.home', municipio_slug=g.municipio.slug))

# -------------------------------------------------------------------------
# 4. RELATÓRIO DE PRESTAÇÃO DE CONTAS FUNDEB
# -------------------------------------------------------------------------
@transporte_bp.route('/relatorio-fundeb')
@login_required
def relatorio_fundeb():
    """Emite o relatório auditável do Transporte Adaptado para o Fundeb/MEC."""
    if current_user.perfil not in ['secretaria', 'superadmin', 'transporte', 'diretor', 'aee', 'professor']:
        abort(403)

    from datetime import datetime

    alunos = Aluno.query.filter_by(municipio_id=g.municipio.id, ativo=True).all()
    dados_transporte = []

    for a in alunos:
        t = TransporteAlunado.query.filter_by(aluno_id=a.id).first()
        if a.necessita_transporte_adaptado or a.cadeirante or (t and t.rota_id):
            dados_transporte.append({
                'aluno': a,
                'transporte': t,
                'escola_nome': a.escola.nome if a.escola else 'Escola Municipal'
            })

    data_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M')

    return render_template(
        'transporte/relatorio_fundeb.html',
        dados_transporte=dados_transporte,
        data_emissao=data_emissao
    )