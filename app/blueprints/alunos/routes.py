from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort, jsonify
from flask_login import login_required
from app import db
from app.models import Aluno, Escola, Pei, Paee

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
    aluno = Aluno.query.filter_by(id=aluno_id, municipio_id=g.municipio.id).first_or_404()
    peis = Pei.query.filter_by(aluno_id=aluno.id, status='Homologado').all()
    paees = Paee.query.filter_by(aluno_id=aluno.id, status='Homologado').all()
    return render_template('alunos/perfil.html', aluno=aluno, peis=peis, paees=paees)

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