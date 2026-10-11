from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


class Municipio(db.Model):
    """
    Tabela do Inquilino (Tenant).
    Centraliza a adesão de cada cidade ao ecossistema.
    """
    __tablename__ = 'municipios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    estado = db.Column(db.String(2), nullable=False) # Ex: PI, CE, MA
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True) # Ex: 'valenca-do-piaui'
    brasao_url = db.Column(db.String(255), nullable=True)
    
    # Configurações de Contrato / Limites do SaaS
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    limite_alunos = db.Column(db.Integer, default=500) # Para planos de cobrança
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos Globais do Município
    usuarios = db.relationship('Usuario', backref='municipio', lazy=True, cascade='all, delete-orphan')
    alunos = db.relationship('Aluno', foreign_keys='Aluno.municipio_id', backref='municipio', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Municipio {self.nome}-{self.estado}>"


class Usuario(db.Model, UserMixin):
    """
    Controle de Usuários e Perfis (RBAC), agora atrelado a um município.
    Perfil 'superadmin' gerencia a plataforma globalmente (cria municípios).
    """
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=True) # Null apenas para SuperAdmin Global
    
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(256), nullable=False)
    
    # Perfis: 'superadmin', 'secretaria', 'diretor', 'professor', 'aee', 'transporte', 'familia'
    perfil = db.Column(db.String(30), nullable=False, default='professor')
    
    senha_provisoria = db.Column(db.Boolean, default=False, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    peis_criados = db.relationship('Pei', backref=db.backref('professor_criador', overlaps="peis_elaborados,professor"), lazy=True, overlaps="peis_elaborados,professor")
    alunos_responsaveis = db.relationship('Aluno', backref='responsavel_usuario', lazy=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Aluno(db.Model):
    """
    Módulo 1: Cadastro Centralizado, isolado obrigatoriamente por município.
    """
    __tablename__ = 'alunos'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    
    # Controle de Status (Soft Delete)
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True) 
    
    # Dados Pessoais e Civis (Sincronizados com o Formulário)
    nome = db.Column(db.String(100), nullable=False, index=True)
    cpf = db.Column(db.String(14), nullable=True, index=True)
    data_nascimento = db.Column(db.String(10), nullable=True) # Armazena a data vinda do input date (AAAA-MM-DD)
    sexo = db.Column(db.String(20), nullable=True)
    raca_cor = db.Column(db.String(30), nullable=True)
    naturalidade = db.Column(db.String(100), nullable=True)
    foto_url = db.Column(db.String(255), nullable=True)
    
    # Filiação e Indicadores Sociais
    nome_mae = db.Column(db.String(100), nullable=True)
    nome_pai = db.Column(db.String(100), nullable=True)
    recebe_bpc = db.Column(db.Boolean, default=False, nullable=True)

    # Vínculo Escolar & Censo Regulamentar
    matricula = db.Column(db.String(30), unique=True, nullable=False)
    codigo_inep = db.Column(db.String(30), nullable=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escolas.id'), nullable=True, index=True)
    turma = db.Column(db.String(50), nullable=False)
    modalidade = db.Column(db.String(50), nullable=True)
    etapa_ensino = db.Column(db.String(50), nullable=True)

    # Recursos de Acessibilidade para Avaliações Oficiais (SAEB)
    recurso_ledor = db.Column(db.Boolean, default=False, nullable=True)
    recurso_transcritor = db.Column(db.Boolean, default=False, nullable=True)
    recurso_libras = db.Column(db.Boolean, default=False, nullable=True)
    recurso_ampliado = db.Column(db.Boolean, default=False, nullable=True)
    
    # Mapeamento Clínico & Atendimento Especializado (AEE)
    cid = db.Column(db.String(15), nullable=True)
    tipo_deficiencia = db.Column(db.String(100), nullable=False)
    possui_tea = db.Column(db.Boolean, default=False, nullable=False)
    possui_superdotacao = db.Column(db.Boolean, default=False, nullable=False)
    local_aee = db.Column(db.String(100), nullable=True)
    necessita_apoio = db.Column(db.String(100), nullable=True)
    
    # Prontuário de Saúde Institucional
    medicacoes = db.Column(db.Text, nullable=True)
    restricoes_alimentares = db.Column(db.Text, nullable=True)
    acessibilidade_necessaria = db.Column(db.Text, nullable=True)
    
    # Logística de Transporte Inclusivo
    necessita_transporte_adaptado = db.Column(db.Boolean, default=False, nullable=True)
    cadeirante = db.Column(db.Boolean, default=False, nullable=True)
    necessita_acompanhante = db.Column(db.Boolean, default=False, nullable=True)
    possui_monitor_rota = db.Column(db.Boolean, default=False, nullable=True)

    # Controle Operacional, Segurança Familiar & Histórico de Transferências Intermunicipais
    ano_letivo = db.Column(db.String(10), default='2026', nullable=False)
    status_matricula = db.Column(db.String(30), default='Ativo', nullable=False) # 'Ativo', 'Transferido', 'Egresso', 'Concluído'
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    contato_urgencia = db.Column(db.String(50), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    municipio_origem_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=True)
    status_transferencia = db.Column(db.String(50), default='Regular')
    data_transferencia = db.Column(db.DateTime, nullable=True)

    municipio_origem = db.relationship('Municipio', foreign_keys=[municipio_origem_id], lazy=True)

    # Propriedades compatíveis com novas telas sem forçar colunas não migradas no banco
    @property
    def endereco(self):
        return getattr(self, '_endereco', None) or (self.dados_transporte.ponto_embarque if self.dados_transporte else None) or ''
    
    @endereco.setter
    def endereco(self, val):
        self._endereco = val

    @property
    def bairro(self):
        return getattr(self, '_bairro', None) or ''
    
    @bairro.setter
    def bairro(self, val):
        self._bairro = val

    @property
    def em_investigacao(self):
        return getattr(self, '_em_investigacao', not bool(self.cid))

    @em_investigacao.setter
    def em_investigacao(self, val):
        self._em_investigacao = bool(val)

    @property
    def hipotese_diagnostica(self):
        return getattr(self, '_hipotese_diagnostica', None) or self.tipo_deficiencia or ''

    @hipotese_diagnostica.setter
    def hipotese_diagnostica(self, val):
        self._hipotese_diagnostica = val

    # Relacionamentos Mapeados do Ecossistema Gestoor 360
    escola = db.relationship('Escola', backref=db.backref('alunos_matriculados', lazy=True))
    peis = db.relationship('Pei', back_populates='aluno', cascade='all, delete-orphan', lazy=True, order_by=lambda: db.desc(Pei.id))
    atendimentos_aee = db.relationship('AtendimentoAee', backref='aluno', cascade='all, delete-orphan', lazy=True)
    dados_transporte = db.relationship('TransporteAlunado', backref='aluno', uselist=False, cascade='all, delete-orphan', lazy=True)


class Pei(db.Model):
    """
    Módulo 2: PEI Inteligente & Governança Inclusiva Municipal.
    Alinhado com as Diretrizes Operacionais da Educação Especial do MEC,
    Decreto nº 7.611/2011, Lei nº 13.146/2015 (LBI) e Nota Técnica Conjunta SECADI/SEB/MEC.
    """
    __tablename__ = 'peis'

    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    ano_letivo = db.Column(db.Integer, nullable=False, default=2026)
    periodo_trimestre = db.Column(db.Integer, nullable=False) # 1, 2 ou 3
    
    # --- NOVO: CONTROLE DE HISTÓRICO POR MÊS DE COMPETÊNCIA ---
    mes_competencia = db.Column(db.String(30), default="Maio", nullable=True) # Ex: Janeiro, Fevereiro...
    
    # --- COMPLEMENTO DE IDENTIFICAÇÃO DE GOVERNANÇA ---
    coordenador_pedagogico = db.Column(db.String(255), nullable=True)
    periodo_vigencia = db.Column(db.String(100), default="Fevereiro a Dezembro de 2026", nullable=True)

    # --- DIMENSÃO 1: IDENTIFICAÇÃO DE BARREIRAS (Art. 3º da LBI / Lei 13.146) ---
    barreiras_arquitetonicas = db.Column(db.Text, nullable=True)   # Barreiras físicas na escola/sala
    barreiras_atidudinais = db.Column(db.Text, nullable=True)      # Barreiras sociais/isolamento
    barreiras_pedagogicas = db.Column(db.Text, nullable=True)      # Barreiras de material/didática
    barreiras_comunicacao = db.Column(db.Text, nullable=True)      # NOVO: Barreiras de instrução e apoio visual
    potencialidades_cognitivas = db.Column(db.Text, nullable=False) # Habilidades já consolidadas

    # --- NOVA DIMENSÃO: ENTREVISTA COM OS RESPONSÁVEIS (MAPEAMENTO CLÍNICO E SOCIAL) ---
    resp_parentesco = db.Column(db.String(100), nullable=True)
    resp_contato = db.Column(db.String(100), nullable=True)
    resp_data_entrevista = db.Column(db.String(50), nullable=True)
    resp_historico_desenvolvimento = db.Column(db.Text, nullable=True) # Primeiros anos de vida
    resp_acompanhamento_medico = db.Column(db.Text, nullable=True)     # Médico, terapêutico ou multiprofissional
    resp_dificuldades_familiares = db.Column(db.Text, nullable=True)   # Observadas no ambiente doméstico
    resp_potencialidades = db.Column(db.Text, nullable=True)           # Potencialidades e habilidades vistas pela família
    resp_rotina_casa = db.Column(db.Text, nullable=True)               # Rotina diária da criança
    resp_medicacao = db.Column(db.Text, nullable=True)                 # Uso de fármacos/dosagens
    resp_laudos_relatorios = db.Column(db.Text, nullable=True)         # Existência de documentos atualizados
    resp_necessita_apoio_basico = db.Column(db.Text, nullable=True)    # Apoio para locomoção, alimentação ou higiene
    resp_interesse_atividades = db.Column(db.Text, nullable=True)      # Interesse pelas atividades escolares
    resp_autonomia_tarefas = db.Column(db.Text, nullable=True)         # Nível de autonomia nas tarefas de casa
    resp_interacao_social = db.Column(db.Text, nullable=True)          # Interação com familiares e colegas
    resp_comportamento_domestico = db.Column(db.Text, nullable=True)   # Comportamentos no ambiente doméstico
    resp_preferencias_sensibilidades = db.Column(db.Text, nullable=True) # Preferências, estímulos e sensibilidades
    resp_expectativas_familia = db.Column(db.Text, nullable=True)      # Expectativas da família com a escola
    resp_encaminhamentos_conjuntos = db.Column(db.Text, nullable=True) # Encaminhamentos definidos em conjunto

    # --- NOVA DIMENSÃO: CARACTERIZAÇÃO MULTIDIMENSIONAL DO ESTUDANTE ---
    char_aspectos_cognitivos = db.Column(db.Text, nullable=True)       # Potencial de aprendizagem e adaptações
    char_aspectos_motores = db.Column(db.Text, nullable=True)          # Limitações físicas, postura, coordenação fina/ampla
    char_aspectos_socioemocionais = db.Column(db.Text, nullable=True)  # Interação social, autoestima e incentivos
    char_aspectos_comunicacionais = db.Column(db.Text, nullable=True)  # Compreensão de comandos e instruções

    # --- DIMENSÃO 2: PLANO DE ATENDIMENTO SRM (MEC) ---
    frequencia_srm_semanal = db.Column(db.Integer, default=2)     # Vezes por semana na sala de recursos
    organizacao_atendimento = db.Column(db.String(30))             # Individual ou Em Grupo
    
    # --- DIMENSÃO 3: PLANEJAMENTO CURRICULAR E METAS PARCELADAS (Padrão MEC/Auditoria) ---
    # Área Acadêmica / Cognitiva
    objetivos_curto_prazo_acad = db.Column(db.Text, nullable=False)
    objetivos_medio_prazo_acad = db.Column(db.Text, nullable=False)
    objetivos_longo_prazo_acad = db.Column(db.Text, nullable=False)
    estrategias_pedagogicas_acad = db.Column(db.Text, nullable=False)
    
    # Área de Atividades de Vida Diária (AVD) e Autonomia
    objetivos_curto_prazo_auton = db.Column(db.Text, nullable=False)
    objetivos_longo_prazo_auton = db.Column(db.Text, nullable=False)
    estrategias_desenvolvimento_auton = db.Column(db.Text, nullable=False)

    # --- NOVA DIMENSÃO: CRONOGRAMA DE METAS E MATRIZ DE DISCIPLINAS DINÂMICAS ---
    cronograma_periodizacao = db.Column(db.String(50), default="Trimestrais", nullable=True) # Mensais, Bimestrais, Trimestrais, Semestrais
    metas_pedagogicas_json = db.Column(db.Text, nullable=True)     # Armazena a listagem de metas fracionadas por período
    disciplinas_bncc_json = db.Column(db.Text, nullable=True)      # Armazena a grade completa de Disciplinas, Conteúdos, Habilidades BNCC, Metodologias e Recursos
    
    # --- DIMENSÃO 4: RECURSOS E ACESSIBILIDADE (Espelho Censo Escolar MEC/INEP) ---
    recursos_opticos_adicionais = db.Column(db.Boolean, default=False) # Lupa, lentes, etc.
    recursos_comunicacao_alternativa = db.Column(db.Boolean, default=False) # Pranchas CAA, PECS
    recursos_acessibilidade_informatica = db.Column(db.Boolean, default=False) # Teclado adaptado, leitores de tela
    recursos_atendimento_libras = db.Column(db.Boolean, default=False) # Tradutor/Intérprete
    
    # --- DIMENSÃO 5: PROFISSIONAIS DE APOIO (Lei 13.146/2015) ---
    necessita_profissional_apoio = db.Column(db.Boolean, default=False)
    atividades_apoio_especificadas = db.Column(db.Text, nullable=True) # Alimentação, higiene, locomoção
    
    # --- DIMENSÃO 6: FLUXO JURÍDICO E VALIDAÇÃO ---
    status = db.Column(db.String(40), default='Rascunho', nullable=False) # Rascunho, Validado pelo AEE, Homologado pela Secretaria
    
    # Trilha de Autenticação Eletrônica (Auditoria MP)
    assinado_professor = db.Column(db.Boolean, default=False)
    assinado_professor_em = db.Column(db.DateTime, nullable=True)
    assinado_coordenador_aee = db.Column(db.Boolean, default=False)
    assinado_coordenador_aee_em = db.Column(db.DateTime, nullable=True)
    homologado_secretaria = db.Column(db.Boolean, default=False)
    homologado_secretaria_em = db.Column(db.DateTime, nullable=True)
    
    # Assinatura / Ciência do Responsável (Art. 28 LBI)
    assinado_familia = db.Column(db.Boolean, default=False)
    assinado_familia_em = db.Column(db.DateTime, nullable=True)
    
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos Utilitários
    aluno = db.relationship('Aluno', back_populates='peis')
    professor = db.relationship('Usuario', backref=db.backref('peis_elaborados', lazy=True), overlaps="peis_criados,professor_criador")

class AtendimentoAee(db.Model):
    """
    Módulo Sala de AEE: Registro de atendimentos e sessões na Sala de Recursos.
    Totalmente alinhado ao esquema de banco original existente em produção.
    """
    __tablename__ = 'atendimentos_aee'

    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False, index=True)
    
    data_atendimento = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    horario_inicio = db.Column(db.Time, nullable=True)
    horario_fim = db.Column(db.Time, nullable=True)
    
    # Controle de Presença / Frequência no banco real
    frequencia = db.Column(db.Boolean, default=True, nullable=False)
    plano_sessao = db.Column(db.Text, nullable=True, default='')
    evolucao_registro = db.Column(db.Text, nullable=True, default='')
    recursos_utilizados = db.Column(db.String(255), nullable=True)
    registrado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        # Mapeamento transparente de kwargs novos para campos reais do PostgreSQL
        if 'compareceu' in kwargs:
            kwargs['frequencia'] = bool(kwargs.pop('compareceu'))
        if 'o_que_foi_feito' in kwargs:
            kwargs['plano_sessao'] = kwargs.pop('o_que_foi_feito') or ''
        if 'como_foi_feito' in kwargs:
            kwargs['evolucao_registro'] = kwargs.pop('como_foi_feito') or ''
        self._municipio_id = kwargs.pop('municipio_id', None)
        self._profissional_id = kwargs.pop('profissional_id', None)
        self._profissional_nome = kwargs.pop('profissional_nome', 'Especialista AEE')
        self._justificativa_falta = kwargs.pop('justificativa_falta', '')
        self._observacoes_evolucao = kwargs.pop('observacoes_evolucao', '')
        super().__init__(**kwargs)

    @property
    def compareceu(self):
        return self.frequencia

    @compareceu.setter
    def compareceu(self, val):
        self.frequencia = bool(val)

    @property
    def o_que_foi_feito(self):
        return self.plano_sessao or ''

    @o_que_foi_feito.setter
    def o_que_foi_feito(self, val):
        self.plano_sessao = val or ''

    @property
    def como_foi_feito(self):
        return self.evolucao_registro or ''

    @como_foi_feito.setter
    def como_foi_feito(self, val):
        self.evolucao_registro = val or ''

    @property
    def justificativa_falta(self):
        return getattr(self, '_justificativa_falta', '')

    @justificativa_falta.setter
    def justificativa_falta(self, val):
        self._justificativa_falta = val

    @property
    def profissional_nome(self):
        return getattr(self, '_profissional_nome', 'Especialista AEE')

    @profissional_nome.setter
    def profissional_nome(self, val):
        self._profissional_nome = val

    @property
    def profissional_id(self):
        return getattr(self, '_profissional_id', None)

    @profissional_id.setter
    def profissional_id(self, val):
        self._profissional_id = val

    @property
    def municipio_id(self):
        return getattr(self, '_municipio_id', None)

    @municipio_id.setter
    def municipio_id(self, val):
        self._municipio_id = val

    @property
    def atividade_realizada(self):
        return self.o_que_foi_feito or self.plano_sessao or 'Atendimento individualizado na Sala de Recursos.'

    @property
    def metodologia_realizada(self):
        return self.como_foi_feito or self.evolucao_registro or self.recursos_utilizados or 'Recursos pedagógicos adaptados e mediação direta.'


class RotaTransporte(db.Model):
    """
    Módulo 4: Gestão de Rotas e Frota do Transporte Escolar Adaptado.
    """
    __tablename__ = 'rotas_transporte'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    
    codigo_rota = db.Column(db.String(50), nullable=False)  # Ex: ROTA-01 ZONA RURAL
    nome_rota = db.Column(db.String(150), nullable=False)   # Ex: Itinerário Povoado Centro
    
    motorista_nome = db.Column(db.String(100), nullable=True)
    motorista_telefone = db.Column(db.String(20), nullable=True)
    monitor_nome = db.Column(db.String(100), nullable=True)
    monitor_telefone = db.Column(db.String(20), nullable=True)
    
    placa_veiculo = db.Column(db.String(10), nullable=True)
    tipo_veiculo = db.Column(db.String(50), default='Van Adaptada') # Van Adaptada, Micro-ônibus Elevatório, Ônibus Acessível
    capacidade_cadeirantes = db.Column(db.Integer, default=2)
    turno = db.Column(db.String(30), default='Manhã e Tarde')
    
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    municipio = db.relationship('Municipio', backref=db.backref('rotas_transporte', lazy=True, cascade='all, delete-orphan'))


class TransporteAlunado(db.Model):
    """
    Módulo 4: Logística e Acessibilidade no Transporte Escolar.
    """
    __tablename__ = 'transporte_alunado'

    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), unique=True, nullable=False)
    rota_id = db.Column(db.Integer, db.ForeignKey('rotas_transporte.id'), nullable=True)
    
    necessita_veiculo_adaptado = db.Column(db.Boolean, default=False, nullable=False)
    cadeirante = db.Column(db.Boolean, default=False, nullable=False)
    necessita_acompanhante = db.Column(db.Boolean, default=False, nullable=False)
    possui_monitor_rota = db.Column(db.Boolean, default=False, nullable=False)
    
    rota_codigo = db.Column(db.String(50), nullable=True)
    ponto_embarque = db.Column(db.String(150), nullable=True)
    horario_embarque = db.Column(db.String(10), nullable=True)   # Ex: 06:45
    horario_desembarque = db.Column(db.String(10), nullable=True) # Ex: 11:45
    observacoes_logistica = db.Column(db.Text, nullable=True)
    
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rota = db.relationship('RotaTransporte', backref=db.backref('alunos_vinculados', lazy=True))


class ProfissionalAEE(db.Model):
    __tablename__ = 'profissionais_aee'
    
    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(14), nullable=False)
    cargo = db.Column(db.String(50), nullable=False) 
    escola_polo = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Ativo')
    
    ativo = db.Column(db.Boolean, default=True, server_default='true', nullable=False)

    municipio = db.relationship('Municipio', backref=db.backref('profissionais', lazy=True))  

class PlanoAEE(db.Model):
    __tablename__ = 'planos_aee'
    
    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissionais_aee.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Conteúdo Pedagógico
    objetivos_gerais = db.Column(db.Text)
    objetivos_especificos = db.Column(db.Text)
    barreiras_identificadas = db.Column(db.Text)
    estrategias_pedagogicas = db.Column(db.Text)
    recursos_utilizados = db.Column(db.Text)
    tecnologias_assistivas = db.Column(db.Text)
    avaliacao_inicial = db.Column(db.Text)
    metas = db.Column(db.Text)
    cronograma = db.Column(db.Text)
    status = db.Column(db.String(20), default='Em Andamento') # 'Em Andamento', 'Concluído', 'Revisado'

    # Relacionamentos
    aluno = db.relationship('Aluno', backref=db.backref('planos', lazy=True))
    profissional = db.relationship('ProfissionalAEE', backref=db.backref('planos_criados', lazy=True))


class EncaminhamentoAEE(db.Model):
    """
    Módulo AEE: Guias de Encaminhamento para a Rede de Saúde (SUS/CAPS/CRAS).
    """
    __tablename__ = 'encaminhamentos_aee'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False, index=True)
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissionais_aee.id'), nullable=True)

    destino_rede = db.Column(db.String(80), nullable=False) # 'Neuropediatria', 'CAPS Infantil', 'Psicologia SUS', 'Fonoaudiologia', 'Terapia Ocupacional', 'CRAS/CREAS'
    motivo_encaminhamento = db.Column(db.Text, nullable=False)
    hipotese_observada = db.Column(db.Text, nullable=True)
    contrarreferencia_resposta = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(30), default='Pendente') # 'Pendente', 'Em Atendimento', 'Concluído'
    data_emissao = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    aluno = db.relationship('Aluno', backref=db.backref('encaminhamentos', lazy=True, order_by='EncaminhamentoAEE.id.desc()'))
    profissional = db.relationship('ProfissionalAEE', backref=db.backref('encaminhamentos_emitidos', lazy=True))


class HistoricoTransferenciaAluno(db.Model):
    """
    Rastreabilidade e Histórico de Transferências/Remanejamentos Internos de Estudantes PCD.
    """
    __tablename__ = 'historico_transferencias_alunos'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False, index=True)
    
    escola_origem_id = db.Column(db.Integer, db.ForeignKey('escolas.id'), nullable=True)
    escola_destino_id = db.Column(db.Integer, db.ForeignKey('escolas.id'), nullable=True)
    
    turma_origem = db.Column(db.String(50), nullable=True)
    turma_destino = db.Column(db.String(50), nullable=True)
    
    ano_letivo = db.Column(db.String(10), default='2026')
    motivo_transferencia = db.Column(db.Text, nullable=True)
    data_transferencia = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    aluno = db.relationship('Aluno', backref=db.backref('historico_remanejamentos_internos', lazy=True, order_by='HistoricoTransferenciaAluno.id.desc()'))
    escola_origem = db.relationship('Escola', foreign_keys=[escola_origem_id])
    escola_destino = db.relationship('Escola', foreign_keys=[escola_destino_id])

# =========================================================================
# 4. AGENDA DE ATENDIMENTOS & AGENDAMENTOS
# =========================================================================
class AgendaAEE(db.Model):
    __tablename__ = 'agenda_aee'
    
    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissionais_aee.id'), nullable=False)
    
    dia_semana = db.Column(db.String(20), nullable=False)
    horario_inicio = db.Column(db.String(5), nullable=False)
    horario_fim = db.Column(db.String(5), nullable=False)
    sala_recurso = db.Column(db.String(100))
    quantidade_sessoes = db.Column(db.Integer, default=1)

    # --- NOVO: Status e Auditoria ---
    status = db.Column(db.String(20), default='Agendado')
    ativo = db.Column(db.Boolean, default=True, server_default='true', nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # RELACIONAMENTOS
    aluno = db.relationship('Aluno', backref=db.backref('agenda', lazy=True))
    profissional = db.relationship('ProfissionalAEE', backref=db.backref('agenda_horarios', lazy=True))

# =========================================================================
# 5. REGISTRO DE EVOLUÇÃO DIÁRIA (Diário de Classe do AEE)
# =========================================================================
class EvolucaoAEE(db.Model):
    __tablename__ = 'evolucoes_aee'
    
    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissionais_aee.id'), nullable=False)
    
    data_atendimento = db.Column(db.Date, nullable=False)
    atividade_trabalhada = db.Column(db.String(200), nullable=False)
    evolucao_observada = db.Column(db.Text, nullable=False)
    dificuldades_identificadas = db.Column(db.Text)
    intervencoes_realizadas = db.Column(db.Text)
    presenca = db.Column(db.String(10), default='Presente') # 'Presente', 'Falta', 'Reposicao'

    # --- NOVO: Complementos Metodologia SOAP e Auditoria ---
    comportamento_subjetivo = db.Column(db.Text, nullable=True) # S (Subjetivo): Como o aluno chegou
    proximos_passos = db.Column(db.Text, nullable=True) # P (Plano): O que fazer na próxima sessão
    ativo = db.Column(db.Boolean, default=True, server_default='true', nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    aluno = db.relationship('Aluno', backref=db.backref('evolucoes', lazy=True))
    profissional = db.relationship('ProfissionalAEE', backref=db.backref('evolucoes_realizadas', lazy=True))

# =========================================================================
# 7. CONTROLE DOCUMENTAL DIGITAL
# =========================================================================
class DocumentoAEE(db.Model):
    __tablename__ = 'documentos_aee'
    
    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    
    # --- NOVO: Relacionar com o profissional que gerou o documento ---
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissionais_aee.id'), nullable=True)

    tipo_documento = db.Column(db.String(50), nullable=False) # 'Laudo', 'Parecer', 'Documento Médico', 'Autorização'
    descricao = db.Column(db.String(200))
    
    # --- NOVO: url_arquivo passa a permitir nulos para aceitar geração em HTML via sistema ---
    url_arquivo = db.Column(db.String(255), nullable=True) # Caminho salvo local ou no Supabase/S3
    conteudo = db.Column(db.Text, nullable=True) # Texto gerado diretamente na plataforma
    
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)

    # --- NOVO: Governança Legal ---
    chave_autenticidade = db.Column(db.String(64), unique=True, nullable=True)
    status = db.Column(db.String(20), default='Válido')
    ativo = db.Column(db.Boolean, default=True, server_default='true', nullable=False)

    aluno = db.relationship('Aluno', backref=db.backref('documentos', lazy=True))
    profissional = db.relationship('ProfissionalAEE', backref=db.backref('documentos_emitidos', lazy=True))

# =========================================================================
# 10. COMUNICAÇÃO COM A FAMÍLIA E ATAS DE REUNIÃO
# =========================================================================
class ComunicacaoAEE(db.Model):
    __tablename__ = 'comunicacoes_aee'
    
    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    
    tipo_registro = db.Column(db.String(50), nullable=False) # 'Reunião Familiar', 'Orientação', 'Encaminhamento'
    data_registro = db.Column(db.Date, nullable=False)
    relato_descritivo = db.Column(db.Text, nullable=False)
    compartilhado_com_familia = db.Column(db.Boolean, default=False)
    
    # Ciência & Feedback do Responsável (Portal da Família)
    ciencia_familia = db.Column(db.Boolean, default=False)
    ciencia_data = db.Column(db.DateTime, nullable=True)
    observacoes_familia = db.Column(db.Text, nullable=True)

    aluno = db.relationship('Aluno', backref=db.backref('comunicacoes', lazy=True, order_by='ComunicacaoAEE.id.desc()'))
    
class Escola(db.Model):
    """
    Módulo Core: Cadastro de Unidades Escolares da Rede Municipal.
    Isolado obrigatoriamente por município e alinhado com o Censo Escolar INEP.
    """
    __tablename__ = 'escolas'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    
    # 1. Identificação Jurídica e Administrativa
    nome = db.Column(db.String(150), nullable=False, index=True)
    codigo_inep = db.Column(db.String(20), unique=True, nullable=False, index=True)
    cnpj = db.Column(db.String(18), nullable=True)
    diretora_nome = db.Column(db.String(100), nullable=False)
    diretora_cpf = db.Column(db.String(14), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    email_institucional = db.Column(db.String(100), nullable=True)
    
    # 2. Localização e Endereço
    zona = db.Column(db.String(10), nullable=False, default='Urbana') # Urbana ou Rural
    endereco_rua = db.Column(db.String(150), nullable=False)
    numero = db.Column(db.String(20), nullable=True)
    bairro = db.Column(db.String(80), nullable=False)
    cep = db.Column(db.String(10), nullable=True)
    
    # 3. Infraestrutura e Acessibilidade (Crucial para Educação Inclusiva)
    possui_sala_recursos = db.Column(db.Boolean, default=False, nullable=False) # SRM ativa
    possui_rampas = db.Column(db.Boolean, default=False, nullable=False)
    possui_banheiro_adaptado = db.Column(db.Boolean, default=False, nullable=False)
    possui_portas_largas = db.Column(db.Boolean, default=False, nullable=False)
    possui_sinalizacao_tatil = db.Column(db.Boolean, default=False, nullable=False)
    
    # 4. Escopo de Atendimento
    modalidades_atendidas = db.Column(db.String(200), nullable=True) # Ex: Infantil, Fundamental, EJA
    total_salas_aula = db.Column(db.Integer, default=1)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento Reverso para o Município
    municipio = db.relationship('Municipio', backref=db.backref('escolas_rede', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Escola {self.nome} - INEP {self.codigo_inep}>"  

class EstudoCaso(db.Model):
    __tablename__ = 'estudos_caso'
    
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    ano_letivo = db.Column(db.Integer, default=2026, nullable=False)
    
    # 1. Identificação Adicional
    professor_regente = db.Column(db.String(255))
    professor_aee = db.Column(db.String(255))
    responsavel_familiar = db.Column(db.String(255))
    
    # 2. LEVANTAMENTO DE INFORMAÇÕES ESCOLARES (CAMPOS EXPLODIDOS)
    hist_frequencia_escolar = db.Column(db.Text)
    hist_desenvolvimento_academico = db.Column(db.Text)
    hist_dificuldades_observadas = db.Column(db.Text)
    hist_potencialidades_identificadas = db.Column(db.Text)
    hist_relatorios_anteriores = db.Column(db.Text)
    hist_participacao_projetos = db.Column(db.Text)
    
    # 3. ENTREVISTA COM A FAMÍLIA (CAMPOS EXPLODIDOS)
    fam_historico_desenvolvimento = db.Column(db.Text)
    fam_diagnosticos_apresentados = db.Column(db.Text)
    fam_acompanhamentos_terapeuticos = db.Column(db.Text)
    fam_rotina_familiar = db.Column(db.Text)
    fam_comportamento_casa = db.Column(db.Text)
    fam_interacao_social = db.Column(db.Text)
    fam_autonomia = db.Column(db.Text)
    fam_expectativas_familia = db.Column(db.Text)
    
    # 4. OBSERVAÇÃO PEDAGÓGICA EM SALA (CAMPOS EXPLODIDOS)
    obs_participacao_atividades = db.Column(db.Text)
    obs_comunicacao = db.Column(db.Text)
    obs_interacao_social = db.Column(db.Text)
    obs_atencao_concentracao = db.Column(db.Text)
    obs_coordenacao_motora = db.Column(db.Text)
    obs_compreensao_comandos = db.Column(db.Text)
    obs_tempo_execucao = db.Column(db.Text)
    obs_necessidade_mediacao = db.Column(db.Text)
    
    # 5. Mapeamento de Barreiras
    barreiras_arquitetonicas = db.Column(db.Text)
    barreiras_pedagogicas = db.Column(db.Text)
    barreiras_comunicacionais = db.Column(db.Text)
    barreiras_atitudinais = db.Column(db.Text)
    
    # 6. Necessidades Educacionais Específicas
    # Mapeado para necessidades_especificas se preferir, mas mantido o tipo
    necessidades_especificas = db.Column(db.Text)
    
    # 7. Matriz de Intervenções (Salvaremos como JSON para suportar as linhas dinâmicas da tabela)
    intervencoes_json = db.Column(db.Text) # Armazena como string JSON compacta
    
    # 8. Definição de Suportes (Checkboxes)
    necessita_pei = db.Column(db.Boolean, default=False)
    necessita_paee = db.Column(db.Boolean, default=False)
    necessita_aee = db.Column(db.Boolean, default=False)
    necessita_apoio = db.Column(db.Boolean, default=False)
    
    # Tipos de Apoio
    apoio_pedagogico = db.Column(db.Boolean, default=False)
    apoio_locomocao = db.Column(db.Boolean, default=False)
    apoio_alimentacao = db.Column(db.Boolean, default=False)
    apoio_higiene = db.Column(db.Boolean, default=False)
    apoio_comportamental = db.Column(db.Boolean, default=False)
    apoio_comunicacional = db.Column(db.Boolean, default=False)
    media_escolar = db.Column(db.Boolean, default=False)
    apoio_outro = db.Column(db.String(255))
    
    # Intensidade e Encaminhamentos
    intensidade_suporte = db.Column(db.String(50), default='Moderado')
    enc_psicopedagogo = db.Column(db.Boolean, default=False)
    enc_psicologo = db.Column(db.Boolean, default=False)
    enc_fono = db.Column(db.Boolean, default=False)
    enc_to = db.Column(db.Boolean, default=False)
    enc_fisioterapeuta = db.Column(db.Boolean, default=False)
    enc_neuropediatra = db.Column(db.Boolean, default=False)
    
    # 9 e 10. Parecer Conclusivo
    parecer_pedagogico = db.Column(db.Text)
    status = db.Column(db.String(50), default='Rascunho') # 'Rascunho' ou 'Homologado'
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos utilitários organizados com backref limpo
    aluno = db.relationship('Aluno', backref=db.backref('estudos_caso', lazy=True, cascade='all, delete-orphan'))
    professor = db.relationship('Usuario', backref=db.backref('estudos_caso_criados', lazy=True))
    
class Paee(db.Model):
    __tablename__ = 'paees'
    
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    ano_letivo = db.Column(db.Integer, default=2026, nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Rascunho')
    
    # 1. IDENTIFICAÇÃO (Complementar aos dados do Aluno)
    professor_regente = db.Column(db.String(255))
    periodo_vigencia = db.Column(db.String(100))

    # 3. NECESSIDADES EDUCACIONAIS ESPECÍFICAS (Checklist Item 3)
    # Salvamos como JSON para facilitar a marcação de múltiplos itens
    necessidades_checklist_json = db.Column(db.Text) 

    # 4. OBJETIVOS DO AEE (Item 4)
    objetivo_geral = db.Column(db.Text, default="Promover condições de acessibilidade e participação do estudante no ambiente escolar...")
    objetivos_especificos = db.Column(db.Text)

    # 5, 8, 9, 11 e 12. TABELAS DINÂMICAS (JSON)
    # Item 5: Organização do Atendimento (Tabela Área/Objetivos/Estratégias/Recursos/Avaliação)
    organizacao_atendimento_json = db.Column(db.Text)
    
    # Item 6: Recursos e Tecnologia Assistiva
    recursos_pedagogicos_json = db.Column(db.Text)
    tecnologia_assistiva_json = db.Column(db.Text)

    # Item 9: Acompanhamento e Evolução
    acompanhamento_bimestral_json = db.Column(db.Text)

    # Item 11: Articulação Multiprofissional
    articulacao_saude_json = db.Column(db.Text)

    # 7. METODOLOGIAS (Item 7 - Checklist)
    metodologias_json = db.Column(db.Text)

    # 10. PARTICIPAÇÃO DA FAMÍLIA (Item 10)
    orientacao_familia = db.Column(db.Text)

    # 13. HOMOLOGAÇÃO
    # Assinaturas digitais/nomes dos responsáveis
    nome_regente = db.Column(db.String(255))
    nome_aee = db.Column(db.String(255))
    nome_coordenacao = db.Column(db.String(255))
    nome_responsavel = db.Column(db.String(255))
    nome_semec = db.Column(db.String(255))

    # Relacionamentos
    aluno = db.relationship('Aluno', backref=db.backref('paees_emitidos', lazy=True, cascade='all, delete-orphan'))
    professor = db.relationship('Usuario', backref=db.backref('paees_criados', lazy=True), overlaps="peis_criados,professor_criador")

class TransferenciaAluno(db.Model):
    __tablename__ = 'transferencias_alunos'
    
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    municipio_origem_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False)
    municipio_destino_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=True)
    data_transferencia = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    motivo = db.Column(db.Text, nullable=True)
    
    aluno = db.relationship('Aluno', backref=db.backref('historico_transferencias', lazy=True), foreign_keys=[aluno_id])
    municipio_origem = db.relationship('Municipio', foreign_keys=[municipio_origem_id], lazy=True)
    municipio_destino = db.relationship('Municipio', foreign_keys=[municipio_destino_id], lazy=True)
    usuario = db.relationship('Usuario', lazy=True)


# =========================================================================
# MÓDULO 1: SALA DE RECURSOS / AEE — LISTA DE ESPERA E GESTÃO DE VAGAS
# =========================================================================
class ListaEsperaAEE(db.Model):
    """
    Lista de Espera da Sala de Recursos Multifuncionais / AEE.
    Permite gerenciar a fila de triagem, prioridades e chamamento.
    """
    __tablename__ = 'lista_espera_aee'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=True)

    # Dados Pessoais Obrigatórios Solicitados
    nome_completo = db.Column(db.String(150), nullable=False, index=True)
    data_nascimento = db.Column(db.String(20), nullable=True)
    cpf = db.Column(db.String(20), nullable=True)
    telefone = db.Column(db.String(30), nullable=False)

    # Dados Escolares e Familiares
    nome_responsavel = db.Column(db.String(150), nullable=True)
    escola_origem = db.Column(db.String(150), nullable=True)
    ano_serie = db.Column(db.String(50), nullable=True)
    serie_ano = db.Column(db.String(50), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)

    # Diagnóstico / Investigação
    diagnostico_hipotese = db.Column(db.String(255), nullable=True)
    motivo_encaminhamento = db.Column(db.Text, nullable=True)
    em_investigacao = db.Column(db.Boolean, default=False)
    
    # Gestão de Fila e Triagem
    prioridade = db.Column(db.String(30), default='Média')
    status = db.Column(db.String(40), default='Aguardando Vaga')
    turno_pretendido = db.Column(db.String(30), default='Contraturno')
    observacoes_triagem = db.Column(db.Text, nullable=True)
    data_solicitacao = db.Column(db.Date, default=datetime.utcnow)
    data_atendimento = db.Column(db.DateTime, nullable=True)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    municipio = db.relationship('Municipio', backref=db.backref('candidatos_espera_aee', lazy=True))
    aluno = db.relationship('Aluno', backref=db.backref('espera_aee_vinculo', lazy=True))

    def __init__(self, **kwargs):
        if 'ano_serie' in kwargs and 'serie_ano' not in kwargs:
            kwargs['serie_ano'] = kwargs['ano_serie']
        elif 'serie_ano' in kwargs and 'ano_serie' not in kwargs:
            kwargs['ano_serie'] = kwargs['serie_ano']
        if not kwargs.get('data_nascimento'):
            kwargs['data_nascimento'] = 'Não informada'
        if not kwargs.get('telefone'):
            kwargs['telefone'] = '(00) 00000-0000'
        super().__init__(**kwargs)


# =========================================================================
# MÓDULO 2: EQUIPE MULTIDISCIPLINAR — PSICOLOGIA, PSICOPEDAGOGIA E SERVIÇO SOCIAL
# =========================================================================
class AtendimentoMultiSOAP(db.Model):
    """
    Registro de Atendimento Institucional com Metodologia SOAP Especializada
    diferenciada por área: Psicologia, Psicopedagogia e Serviço Social.
    """
    __tablename__ = 'atendimentos_multi_soap'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    profissional_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    # Especialidade: 'psicologo', 'psicopedagogo', 'assistente_social'
    especialidade = db.Column(db.String(50), nullable=False, index=True)
    data_atendimento = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    horario_inicio = db.Column(db.String(10), nullable=True)
    horario_fim = db.Column(db.String(10), nullable=True)
    tipo_sessao = db.Column(db.String(50), default='Individual')
    compareceu = db.Column(db.Boolean, default=True)
    justificativa_falta = db.Column(db.String(255), nullable=True)

    # Campos Estruturados SOAP Institucional
    soap_subjetivo = db.Column(db.Text, nullable=False)
    soap_objetivo = db.Column(db.Text, nullable=False)
    soap_avaliacao = db.Column(db.Text, nullable=False)
    soap_plano = db.Column(db.Text, nullable=False)

    encaminhamento_sugerido = db.Column(db.String(150), nullable=True)
    sigilo_etico = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(30), default='Finalizado')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    aluno = db.relationship('Aluno', backref=db.backref('atendimentos_multi_soap', lazy=True, order_by='AtendimentoMultiSOAP.data_atendimento.desc()'))
    profissional = db.relationship('Usuario', foreign_keys=[profissional_id], lazy=True)
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], lazy=True)
    municipio = db.relationship('Municipio', lazy=True)

    def __init__(self, **kwargs):
        if 'usuario_id' in kwargs and 'profissional_id' not in kwargs:
            kwargs['profissional_id'] = kwargs['usuario_id']
        elif 'profissional_id' in kwargs and 'usuario_id' not in kwargs:
            kwargs['usuario_id'] = kwargs['profissional_id']
        if not kwargs.get('especialidade'):
            kwargs['especialidade'] = 'psicologo'
        if 'compareceu' not in kwargs:
            kwargs['compareceu'] = True
        super().__init__(**kwargs)


class RelatorioEscutaEncaminhamento(db.Model):
    """
    Emissão de Relatórios Técnicos de Escuta Qualificada e Encaminhamentos Intersetoriais
    para a Rede Municipal (SUS, CAPS, CRAS, CREAS, Conselho Tutelar) com Assistência de IA.
    """
    __tablename__ = 'relatorios_escuta_encaminhamentos'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    profissional_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    # Tipo de Instrumento Técnico
    tipo_documento = db.Column(db.String(80), nullable=True)
    especialidade_emissor = db.Column(db.String(50), nullable=True)
    
    # Órgão de Destino da Rede Municipal / Intersetorial
    orgao_destino = db.Column(db.String(150), nullable=False)
    
    # Conteúdo Técnico Estruturado
    motivo_demanda = db.Column(db.Text, nullable=False)
    sintese_escuta = db.Column(db.Text, nullable=True)
    sintese_escuta_qualificada = db.Column(db.Text, nullable=True)
    situacao_contextual = db.Column(db.Text, nullable=True)
    evidencias_observadas = db.Column(db.Text, nullable=True)
    acoes_ja_realizadas_escola = db.Column(db.Text, nullable=True)
    hipotese_ou_vulnerabilidade = db.Column(db.Text, nullable=True)
    providencias_recomendadas = db.Column(db.Text, nullable=True)
    sugestoes_encaminhamento = db.Column(db.Text, nullable=True)
    urgencia = db.Column(db.String(20), default='Média')

    # Recursos de IA
    gerado_com_ia = db.Column(db.Boolean, default=False)
    ia_prompt_ou_modelo = db.Column(db.String(100), nullable=True)

    # Autenticação e Chave de Impressão Timbrada
    chave_autenticidade = db.Column(db.String(64), unique=True, nullable=True)
    status = db.Column(db.String(30), default='Emitido')
    data_emissao = db.Column(db.Date, default=datetime.utcnow)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    aluno = db.relationship('Aluno', backref=db.backref('relatorios_escuta_multi', lazy=True, order_by='RelatorioEscutaEncaminhamento.id.desc()'))
    profissional = db.relationship('Usuario', foreign_keys=[profissional_id], lazy=True)
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], lazy=True)
    municipio = db.relationship('Municipio', lazy=True)

    def __init__(self, **kwargs):
        if 'usuario_id' in kwargs and 'profissional_id' not in kwargs:
            kwargs['profissional_id'] = kwargs['usuario_id']
        elif 'profissional_id' in kwargs and 'usuario_id' not in kwargs:
            kwargs['usuario_id'] = kwargs['profissional_id']

        if not kwargs.get('especialidade_emissor'):
            kwargs['especialidade_emissor'] = kwargs.get('especialidade') or 'Equipe Multidisciplinar'

        if 'sintese_escuta' in kwargs and 'sintese_escuta_qualificada' not in kwargs:
            kwargs['sintese_escuta_qualificada'] = kwargs['sintese_escuta']
        elif 'sintese_escuta_qualificada' in kwargs and 'sintese_escuta' not in kwargs:
            kwargs['sintese_escuta'] = kwargs['sintese_escuta_qualificada']

        if 'providencias_recomendadas' in kwargs and 'sugestoes_encaminhamento' not in kwargs:
            kwargs['sugestoes_encaminhamento'] = kwargs['providencias_recomendadas']
        elif 'sugestoes_encaminhamento' in kwargs and 'providencias_recomendadas' not in kwargs:
            kwargs['providencias_recomendadas'] = kwargs['sugestoes_encaminhamento']

        if 'situacao_contextual' in kwargs and 'evidencias_observadas' not in kwargs:
            kwargs['evidencias_observadas'] = kwargs['situacao_contextual']

        if not kwargs.get('acoes_ja_realizadas_escola'):
            kwargs['acoes_ja_realizadas_escola'] = kwargs.get('situacao_contextual') or 'Acompanhamento pedagógico regular.'

        if not kwargs.get('sintese_escuta_qualificada'):
            kwargs['sintese_escuta_qualificada'] = kwargs.get('sintese_escuta') or 'Escuta técnica realizada.'

        if not kwargs.get('sugestoes_encaminhamento'):
            kwargs['sugestoes_encaminhamento'] = kwargs.get('providencias_recomendadas') or 'Encaminhamento para avaliação pela rede intersetorial.'

        super().__init__(**kwargs)


class PlanoAcaoMensalMulti(db.Model):
    """
    Plano de Ação Mensal e Ata Técnica de Alinhamento da Equipe Multidisciplinar
    para discussão periódica de casos e prestação de contas à gestão municipal com impressão oficial.
    """
    __tablename__ = 'planos_acao_mensais_multi'

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey('municipios.id'), nullable=False, index=True)
    usuario_coordenador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    coordenador_reuniao_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    titulo = db.Column(db.String(150), nullable=True)
    pauta_discutida = db.Column(db.Text, nullable=True)
    mes_referencia = db.Column(db.String(30), nullable=True)
    ano_referencia = db.Column(db.Integer, nullable=True, default=2026)
    data_reuniao = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    local_reuniao = db.Column(db.String(150), default='Secretaria Municipal de Educação')

    profissionais_presentes = db.Column(db.Text, nullable=True)
    participantes_nomes = db.Column(db.Text, nullable=True)

    casos_discutidos_json = db.Column(db.Text, nullable=True)
    casos_discutidos = db.Column(db.Text, nullable=True)

    acoes_psicologia = db.Column(db.Text, nullable=True)
    acoes_psicopedagogia = db.Column(db.Text, nullable=True)
    acoes_servico_social = db.Column(db.Text, nullable=True)
    
    deliberacoes_gerais = db.Column(db.Text, nullable=True)
    encaminhamentos_gestao = db.Column(db.Text, nullable=True)
    metas_proximo_mes = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(40), default='Homologado')
    chave_documento = db.Column(db.String(64), nullable=True)
    chave_autenticidade = db.Column(db.String(64), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    coordenador = db.relationship('Usuario', foreign_keys=[usuario_coordenador_id], lazy=True)
    coordenador_reuniao = db.relationship('Usuario', foreign_keys=[coordenador_reuniao_id], lazy=True)
    municipio = db.relationship('Municipio', lazy=True)

    def __init__(self, **kwargs):
        if 'usuario_coordenador_id' in kwargs and 'coordenador_reuniao_id' not in kwargs:
            kwargs['coordenador_reuniao_id'] = kwargs['usuario_coordenador_id']
        elif 'coordenador_reuniao_id' in kwargs and 'usuario_coordenador_id' not in kwargs:
            kwargs['usuario_coordenador_id'] = kwargs['coordenador_reuniao_id']

        if 'titulo' in kwargs and 'pauta_discutida' not in kwargs:
            kwargs['pauta_discutida'] = kwargs['titulo']
        elif 'pauta_discutida' in kwargs and 'titulo' not in kwargs:
            kwargs['titulo'] = kwargs['pauta_discutida']

        if 'profissionais_presentes' in kwargs and 'participantes_nomes' not in kwargs:
            kwargs['participantes_nomes'] = kwargs['profissionais_presentes']
        elif 'participantes_nomes' in kwargs and 'profissionais_presentes' not in kwargs:
            kwargs['profissionais_presentes'] = kwargs['participantes_nomes']

        if 'casos_discutidos_json' in kwargs and 'casos_discutidos' not in kwargs:
            kwargs['casos_discutidos'] = kwargs['casos_discutidos_json']
        elif 'casos_discutidos' in kwargs and 'casos_discutidos_json' not in kwargs:
            kwargs['casos_discutidos_json'] = kwargs['casos_discutidos']

        if 'deliberacoes_gerais' in kwargs and 'encaminhamentos_gestao' not in kwargs:
            kwargs['encaminhamentos_gestao'] = kwargs['deliberacoes_gerais']
        elif 'encaminhamentos_gestao' in kwargs and 'deliberacoes_gerais' not in kwargs:
            kwargs['deliberacoes_gerais'] = kwargs['encaminhamentos_gestao']

        if 'chave_documento' in kwargs and 'chave_autenticidade' not in kwargs:
            kwargs['chave_autenticidade'] = kwargs['chave_documento']
        elif 'chave_autenticidade' in kwargs and 'chave_documento' not in kwargs:
            kwargs['chave_documento'] = kwargs['chave_autenticidade']

        if not kwargs.get('participantes_nomes'):
            kwargs['participantes_nomes'] = 'Equipe Multiprofissional'
        if not kwargs.get('pauta_discutida'):
            kwargs['pauta_discutida'] = kwargs.get('titulo') or 'Reunião Técnica Mensal'
        if not kwargs.get('casos_discutidos'):
            kwargs['casos_discutidos'] = 'Alinhamento geral de casos da rede municipal'
        if not kwargs.get('encaminhamentos_gestao'):
            kwargs['encaminhamentos_gestao'] = kwargs.get('deliberacoes_gerais') or 'Encaminhamentos pactuados em ata.'

        super().__init__(**kwargs)