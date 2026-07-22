from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort
from flask_login import login_required
from app import db
from app.models import Municipio, Escola

escolas_bp = Blueprint('escolas', __name__)

@escolas_bp.url_value_preprocessor
def get_municipio_slug(endpoint, values):
    """Captura o <municipio_slug> automaticamente para garantir o multitenancy."""
    if values and 'municipio_slug' in values:
        g.municipio = Municipio.query.filter_by(slug=values.pop('municipio_slug')).first()
    if not g.municipio:
        abort(404)

@escolas_bp.route('/', methods=['GET', 'POST'])
@login_required
def cadastrar_escola():
    if request.method == 'POST':
        # 1. Identificação Jurídica e Gestão
        nome = request.form.get('nome')
        codigo_inep = request.form.get('codigo_inep')
        cnpj = request.form.get('cnpj')
        diretora_nome = request.form.get('diretora_nome')
        diretora_cpf = request.form.get('diretora_cpf')
        telefone = request.form.get('telefone')
        email_institucional = request.form.get('email_institucional')
        
        # 2. Localização e Endereço
        zona = request.form.get('zona', 'Urbana')
        endereco_rua = request.form.get('endereco_rua')
        numero = request.form.get('numero')
        bairro = request.form.get('bairro')
        cep = request.form.get('cep')
        
        # 3. Infraestrutura e Acessibilidade
        possui_sala_recursos = 'possui_sala_recursos' in request.form
        possui_rampas = 'possui_rampas' in request.form
        possui_banheiro_adaptado = 'possui_banheiro_adaptado' in request.form
        possui_portas_largas = 'possui_portas_largas' in request.form
        possui_sinalizacao_tatil = 'possui_sinalizacao_tatil' in request.form
        
        # 4. Escopo de Atendimento
        modalidades_atendidas = request.form.get('modalidades_atendidas')
        total_salas = request.form.get('total_salas_aula', 1)

        # Validação de duplicidade de INEP na rede
        escola_existente = Escola.query.filter_by(codigo_inep=codigo_inep).first()
        if escola_existente:
            flash("Esta escola já está cadastrada!", "warning")
            return redirect(url_for('escolas.cadastrar_escola', municipio_slug=g.municipio.slug))

        nova_escola = Escola(
            municipio_id=g.municipio.id,
            nome=nome,
            codigo_inep=codigo_inep,
            cnpj=cnpj,
            diretora_nome=diretora_nome,
            diretora_cpf=diretora_cpf,
            telefone=telefone,
            email_institucional=email_institucional,
            zona=zona,
            endereco_rua=endereco_rua,
            numero=numero,
            bairro=bairro,
            cep=cep,
            possui_sala_recursos=possui_sala_recursos,
            possui_rampas=possui_rampas,
            possui_banheiro_adaptado=possui_banheiro_adaptado,
            possui_portas_largas=possui_portas_largas,
            possui_sinalizacao_tatil=possui_sinalizacao_tatil,
            modalidades_atendidas=modalidades_atendidas,
            total_salas_aula=int(total_salas)
        )
        
        db.session.add(nova_escola)
        db.session.commit()
        flash("Unidade Escolar homologada e integrada com sucesso à rede municipal!", "success")
        return redirect(url_for('escolas.cadastrar_escola', municipio_slug=g.municipio.slug))

    # Lista de escolas já cadastradas para exibição em auditoria
    escolas_db = Escola.query.filter_by(municipio_id=g.municipio.id).order_by(Escola.nome).all()
    
    # CORREÇÃO CRÍTICA AQUI: O nome da variável enviada para o template agora é escolas_rede
    return render_template('escolas/cadastro.html', escolas_rede=escolas_db)

@escolas_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_escola(id):
    # Busca a escola garantindo o isolamento obrigatório por município
    escola = Escola.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()

    if request.method == 'POST':
        # 1. Identificação Jurídica e Gestão
        escola.nome = request.form.get('nome')
        codigo_inep_novo = request.form.get('codigo_inep')
        escola.cnpj = request.form.get('cnpj')
        escola.diretora_nome = request.form.get('diretora_nome')
        escola.diretora_cpf = request.form.get('diretora_cpf')
        escola.telefone = request.form.get('telefone')
        escola.email_institucional = request.form.get('email_institucional')
        
        # 2. Localização e Endereço
        escola.zona = request.form.get('zona', 'Urbana')
        escola.endereco_rua = request.form.get('endereco_rua')
        escola.numero = request.form.get('numero')
        escola.bairro = request.form.get('bairro')
        escola.cep = request.form.get('cep')
        
        # 3. Infraestrutura e Acessibilidade
        escola.possui_sala_recursos = 'possui_sala_recursos' in request.form
        escola.possui_rampas = 'possui_rampas' in request.form
        escola.possui_banheiro_adaptado = 'possui_banheiro_adaptado' in request.form
        escola.possui_portas_largas = 'possui_portas_largas' in request.form
        escola.possui_sinalizacao_tatil = 'possui_sinalizacao_tatil' in request.form
        
        # 4. Escopo de Atendimento
        escola.modalidades_atendidas = request.form.get('modalidades_atendidas')
        escola.total_salas_aula = int(request.form.get('total_salas_aula', 1))

        # Validação de duplicidade de INEP apenas se tiver alterado o código
        if escola.codigo_inep != codigo_inep_novo:
            escola_existente = Escola.query.filter_by(codigo_inep=codigo_inep_novo).first()
            if escola_existente:
                flash("Erro: Já existe outra instituição cadastrada com este código INEP.", "danger")
                return redirect(url_for('escolas.editar_escola', municipio_slug=g.municipio.slug, id=id))
            escola.codigo_inep = codigo_inep_novo

        db.session.commit()
        flash(f"Unidade Escolar {escola.nome} atualizada com sucesso no Censo!", "success")
        return redirect(url_for('escolas.cadastrar_escola', municipio_slug=g.municipio.slug))

    return render_template('escolas/editar_escola.html', escola=escola)


@escolas_bp.route('/excluir/<int:id>', methods=['GET', 'POST'])
@login_required
def excluir_escola(id):
    # Proteção de segurança: garante o escopo do município logado
    escola = Escola.query.filter_by(id=id, municipio_id=g.municipio.id).first_or_404()
    
    nome_escola = escola.nome
    try:
        db.session.delete(escola)
        db.session.commit()
        flash(f"Unidade {nome_escola} removida com sucesso da infraestrutura.", "success")
    except Exception:
        db.session.rollback()
        flash("Erro crítico: Não é possível remover esta escola pois existem alunos vinculados a ela.", "danger")
        
    return redirect(url_for('escolas.cadastrar_escola', municipio_slug=g.municipio.slug))