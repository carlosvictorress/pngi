import os
import json
from datetime import datetime
from flask import Flask, g  # Importei o 'g' aqui
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

@login_manager.unauthorized_handler
def unauthorized():
    """Redireciona inteligentemente dependendo de qual rota o usuário tentou acessar."""
    from flask import request, redirect, url_for
    
    # Se tentou acessar a área global, manda para o login do desenvolvedor mestre
    if 'admin-global' in request.path:
        return redirect(url_for('auth.login_admin_global'))
        
    # Se tentou acessar uma rota interna, pega o primeiro pedaço da URL (o slug) e redireciona
    path_parts = request.path.strip('/').split('/')
    if path_parts and path_parts[0] not in ['auth', 'static', 'manifest.json', 'sw.js', '']:
        slug = path_parts[0]
        return redirect(url_for('auth.login', municipio_slug=slug))
        
    return redirect(url_for('auth.login_admin_global'))

login_manager.login_message = 'Por favor, faça o login para acessar esta página.'
login_manager.login_message_category = 'warning'

def create_app():
    app = Flask(__name__)
    
    # Configurações do Core
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'chave-temporaria-de-seguranca')
    
    # 1. Tratamento robusto da URL do banco de dados (Compatibilidade nativa Railway / PostgreSQL)
    import re
    db_url = (
        os.getenv('DATABASE_PUBLIC_URL') or
        os.getenv('DATABASE_URL') or
        os.getenv('DATABASE_PRIVATE_URL') or
        os.getenv('POSTGRES_URL') or
        os.getenv('POSTGRESQL_URL') or
        os.getenv('PG_URL') or
        os.getenv('URL_DO_BANCO_DE_DADOS')
    )

    # 2. Varredura inteligente de variáveis de ambiente do Railway
    if not db_url:
        for k, v in os.environ.items():
            if isinstance(v, str) and (v.startswith('postgresql://') or v.startswith('postgres://')):
                db_url = v
                break

    # 3. Se ainda não encontrou ou contém referência não resolvida do Railway, tenta montar a partir das variáveis individuais
    if not db_url or '${{' in str(db_url):
        pghost = os.getenv('PGHOST') or os.getenv('POSTGRES_HOST')
        if pghost:
            pgport = os.getenv('PGPORT') or os.getenv('POSTGRES_PORT', '5432')
            pguser = os.getenv('PGUSER') or os.getenv('POSTGRES_USER', 'postgres')
            pgpass = os.getenv('PGPASSWORD') or os.getenv('POSTGRES_PASSWORD', '')
            pgdb = os.getenv('PGDATABASE') or os.getenv('POSTGRES_DB', 'railway')
            db_url = f"postgresql://{pguser}:{pgpass}@{pghost}:{pgport}/{pgdb}"

    # 4. Sanitização de portas e protocolos
    if db_url:
        db_url = re.sub(r':porta\b', ':5432', db_url, flags=re.IGNORECASE)
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

    # 5. Se não houver nenhuma URL do banco de dados configurada, fallback local
    if not db_url:
        db_url = "sqlite:///inclusao.db"

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicialização das Extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # 🚀 GESTOOR 360: Registro do Filtro Global do Jinja2 para decodificação de matrizes JSON
    app.jinja_env.filters['from_json'] = json.loads

    def sincronizar_schema_automatico():
        """Garante a criação segura das novas tabelas e alinhamento de colunas no PostgreSQL."""
        try:
            db.create_all()
        except Exception as e:
            print(f"[INFO] DB check notice: {e}")

        # Alinhamento seguro de colunas nos 4 novos modelos sem alterar tabelas legadas
        try:
            from sqlalchemy import text
            with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                ddl_comandos = [
                    # 1. relatorios_escuta_encaminhamentos
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

                    # 2. atendimentos_multi_soap
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

                    # 3. planos_acao_mensais_multi
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
                    "ALTER TABLE planos_acao_mensais_multi ALTER COLUMN status DROP NOT NULL;",

                    # 4. lista_espera_aee
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS ano_serie VARCHAR(50);",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS serie_ano VARCHAR(50);",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS endereco VARCHAR(255);",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS nome_responsavel VARCHAR(150);",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS motivo_encaminhamento TEXT;",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS em_investigacao BOOLEAN DEFAULT FALSE;",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS turno_pretendido VARCHAR(30) DEFAULT 'Contraturno';",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS observacoes_triagem TEXT;",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS data_atendimento TIMESTAMP;",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
                    "ALTER TABLE lista_espera_aee ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",

                    # Relaxamento seguro de NOT NULL para lista de espera
                    "ALTER TABLE lista_espera_aee ALTER COLUMN data_nascimento DROP NOT NULL;",
                    "ALTER TABLE lista_espera_aee ALTER COLUMN telefone DROP NOT NULL;",
                    "ALTER TABLE lista_espera_aee ALTER COLUMN prioridade DROP NOT NULL;",
                    "ALTER TABLE lista_espera_aee ALTER COLUMN status DROP NOT NULL;",

                    # 5. atendimentos_aee (Sessões e Faltas na Sala de Recursos SRM)
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS municipio_id INTEGER;",
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS compareceu BOOLEAN DEFAULT TRUE;",
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS o_que_foi_feito TEXT;",
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS como_foi_feito TEXT;",
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS recursos_utilizados VARCHAR(255);",
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS justificativa_falta VARCHAR(255);",
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS profissional_id INTEGER;",
                    "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS profissional_nome VARCHAR(150);",
                    "ALTER TABLE atendimentos_aee ALTER COLUMN horario_inicio DROP NOT NULL;",
                    "ALTER TABLE atendimentos_aee ALTER COLUMN horario_fim DROP NOT NULL;",
                    "ALTER TABLE atendimentos_aee ALTER COLUMN plano_sessao DROP NOT NULL;",
                    "ALTER TABLE atendimentos_aee ALTER COLUMN evolucao_registro DROP NOT NULL;",
                    "ALTER TABLE atendimentos_aee ALTER COLUMN frequencia DROP NOT NULL;",

                    # 6. municipios (Módulos contratados por município)
                    "ALTER TABLE municipios ADD COLUMN IF NOT EXISTS modulo_pei BOOLEAN DEFAULT TRUE;",
                    "ALTER TABLE municipios ADD COLUMN IF NOT EXISTS modulo_aee BOOLEAN DEFAULT TRUE;",
                    "ALTER TABLE municipios ADD COLUMN IF NOT EXISTS modulo_equipe_multi BOOLEAN DEFAULT TRUE;",
                    "ALTER TABLE municipios ADD COLUMN IF NOT EXISTS modulo_transporte BOOLEAN DEFAULT TRUE;",
                    "ALTER TABLE municipios ADD COLUMN IF NOT EXISTS modulo_blindagem_juridica BOOLEAN DEFAULT TRUE;",

                    # 7. Unificação e Sincronização de Profissionais
                    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cpf VARCHAR(14);",
                    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS telefone VARCHAR(20);",
                    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cargo VARCHAR(100);",
                    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS escola_polo VARCHAR(100);",
                    "ALTER TABLE profissionais_aee ADD COLUMN IF NOT EXISTS usuario_id INTEGER;",
                    "ALTER TABLE profissionais_aee ALTER COLUMN cpf DROP NOT NULL;",
                    "ALTER TABLE profissionais_aee ALTER COLUMN escola_polo DROP NOT NULL;",
                    "ALTER TABLE profissionais_aee ALTER COLUMN cargo DROP NOT NULL;",

                    # 8. comunicacoes_aee, mensagens_familia e conquistas_estudante
                    "ALTER TABLE atendimentos_aee DROP CONSTRAINT IF EXISTS atendimentos_aee_profissional_id_fkey;",
                    "ALTER TABLE agenda_aee DROP CONSTRAINT IF EXISTS agenda_aee_profissional_id_fkey;",
                    """
                    CREATE TABLE IF NOT EXISTS comunicacoes_aee (
                        id SERIAL PRIMARY KEY,
                        municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
                        aluno_id INTEGER REFERENCES alunos(id) ON DELETE CASCADE,
                        titulo VARCHAR(200) DEFAULT 'Comunicado da Equipe',
                        tipo_registro VARCHAR(50) NOT NULL DEFAULT 'Orientação',
                        prioridade VARCHAR(20) DEFAULT 'Normal',
                        data_registro DATE NOT NULL DEFAULT CURRENT_DATE,
                        relato_descritivo TEXT NOT NULL,
                        compartilhado_com_familia BOOLEAN DEFAULT TRUE,
                        autor_nome VARCHAR(150) DEFAULT 'Equipe Escolar',
                        autor_cargo VARCHAR(100) DEFAULT 'Especialista AEE',
                        ciencia_familia BOOLEAN DEFAULT FALSE,
                        ciencia_data TIMESTAMP,
                        observacoes_familia TEXT,
                        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS conquistas_estudante (
                        id SERIAL PRIMARY KEY,
                        municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
                        aluno_id INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
                        profissional_nome VARCHAR(150),
                        titulo VARCHAR(150) NOT NULL,
                        descricao TEXT NOT NULL,
                        categoria VARCHAR(50) DEFAULT 'Autonomia',
                        icone VARCHAR(50) DEFAULT 'award',
                        data_registro DATE NOT NULL DEFAULT CURRENT_DATE,
                        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS mensagens_familia (
                        id SERIAL PRIMARY KEY,
                        municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
                        aluno_id INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
                        remetente_tipo VARCHAR(20) NOT NULL DEFAULT 'familia',
                        remetente_nome VARCHAR(150) NOT NULL,
                        destinatario_nome VARCHAR(150),
                        assunto VARCHAR(200),
                        mensagem TEXT NOT NULL,
                        data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        lida BOOLEAN DEFAULT FALSE,
                        lida_em TIMESTAMP
                    );
                    """,
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS titulo VARCHAR(200);",
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS prioridade VARCHAR(20) DEFAULT 'Normal';",
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS autor_nome VARCHAR(150);",
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS autor_cargo VARCHAR(100);",
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS ciencia_familia BOOLEAN DEFAULT FALSE;",
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS ciencia_data TIMESTAMP;",
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS observacoes_familia TEXT;",
                    "ALTER TABLE comunicacoes_aee ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
                    "ALTER TABLE comunicacoes_aee ALTER COLUMN aluno_id DROP NOT NULL;",
                    "ALTER TABLE agenda_aee ADD COLUMN IF NOT EXISTS sala_recurso VARCHAR(100);",
                    "ALTER TABLE agenda_aee ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'Agendado';",
                    "ALTER TABLE agenda_aee ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;"
                ]
                for ddl in ddl_comandos:
                    try:
                        conn.execute(text(ddl))
                    except Exception:
                        pass

                # Suporte para SQLite local
                if conn.dialect.name == 'sqlite':
                    for col in ['modulo_pei', 'modulo_aee', 'modulo_equipe_multi', 'modulo_transporte', 'modulo_blindagem_juridica']:
                        try:
                            conn.execute(text(f"ALTER TABLE municipios ADD COLUMN {col} BOOLEAN DEFAULT 1;"))
                        except Exception:
                            pass
                    for col in ['cpf', 'telefone', 'cargo', 'escola_polo']:
                        try:
                            conn.execute(text(f"ALTER TABLE usuarios ADD COLUMN {col} VARCHAR(100);"))
                        except Exception:
                            pass
                    try:
                        conn.execute(text("ALTER TABLE profissionais_aee ADD COLUMN usuario_id INTEGER;"))
                    except Exception:
                        pass
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS comunicacoes_aee (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            municipio_id INTEGER NOT NULL,
                            aluno_id INTEGER,
                            titulo VARCHAR(200),
                            tipo_registro VARCHAR(50),
                            prioridade VARCHAR(20),
                            data_registro DATE,
                            relato_descritivo TEXT,
                            compartilhado_com_familia BOOLEAN,
                            autor_nome VARCHAR(150),
                            autor_cargo VARCHAR(100),
                            ciencia_familia BOOLEAN,
                            ciencia_data TIMESTAMP,
                            observacoes_familia TEXT,
                            criado_em TIMESTAMP
                        );
                    """))
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS conquistas_estudante (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            municipio_id INTEGER NOT NULL,
                            aluno_id INTEGER NOT NULL,
                            profissional_nome VARCHAR(150),
                            titulo VARCHAR(150),
                            descricao TEXT,
                            categoria VARCHAR(50),
                            icone VARCHAR(50),
                            data_registro DATE,
                            criado_em TIMESTAMP
                        );
                    """))
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS mensagens_familia (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            municipio_id INTEGER NOT NULL,
                            aluno_id INTEGER NOT NULL,
                            remetente_tipo VARCHAR(20),
                            remetente_nome VARCHAR(150),
                            destinatario_nome VARCHAR(150),
                            assunto VARCHAR(200),
                            mensagem TEXT,
                            data_envio TIMESTAMP,
                            lida BOOLEAN,
                            lida_em TIMESTAMP
                        );
                    """))
                    for col in ['titulo', 'prioridade', 'autor_nome', 'autor_cargo', 'criado_em', 'ciencia_familia', 'observacoes_familia']:
                        try:
                            conn.execute(text(f"ALTER TABLE comunicacoes_aee ADD COLUMN {col} VARCHAR(200);"))
                        except Exception:
                            pass
                    for col in ['sala_recurso', 'status', 'ativo']:
                        try:
                            conn.execute(text(f"ALTER TABLE agenda_aee ADD COLUMN {col} VARCHAR(100);"))
                        except Exception:
                            pass

            # Sincronização automática inicial de usuários existentes para o quadro de profissionais
            try:
                from app.models import Usuario, ProfissionalAEE
                mapa_perfil_cargo = {
                    'aee': 'Professor(a) de AEE (SRM)',
                    'psicologo': 'Psicólogo(a) Escolar',
                    'psicopedagogo': 'Psicopedagogo(a)',
                    'assistente_social': 'Assistente Social',
                    'fonoaudiologo': 'Fonoaudiólogo(a)',
                    'terapeuta_ocupacional': 'Terapeuta Ocupacional',
                    'professor_libras': 'Tradutor e Intérprete de Libras',
                    'professor_braille': 'Especialista em Braille',
                    'cuidador': 'Profissional de Apoio Escolar / Cuidador',
                    'professor': 'Professor(a) de Sala Regular',
                    'diretor': 'Direção / Coordenação Escolar',
                    'secretaria': 'Secretaria Municipal de Educação',
                    'transporte': 'Monitor / Gestor de Transporte'
                }
                users_mun = Usuario.query.filter(Usuario.municipio_id.isnot(None), Usuario.perfil != 'superadmin').all()
                for u in users_mun:
                    p_exist = ProfissionalAEE.query.filter_by(municipio_id=u.municipio_id, usuario_id=u.id).first()
                    if not p_exist:
                        p_exist = ProfissionalAEE.query.filter(
                            ProfissionalAEE.municipio_id == u.municipio_id,
                            (ProfissionalAEE.email == u.email) | (ProfissionalAEE.nome == u.nome)
                        ).first()
                    if not p_exist:
                        cargo_nome = mapa_perfil_cargo.get(u.perfil, u.cargo or u.perfil.title())
                        novo_p = ProfissionalAEE(
                            municipio_id=u.municipio_id,
                            usuario_id=u.id,
                            nome=u.nome,
                            email=u.email,
                            cargo=cargo_nome,
                            escola_polo=u.escola_polo or 'Sede / Secretaria',
                            cpf=u.cpf or '',
                            telefone=u.telefone or '',
                            ativo=u.ativo,
                            status='Ativo' if u.ativo else 'Suspenso'
                        )
                        db.session.add(novo_p)
                    else:
                        if not p_exist.usuario_id:
                            p_exist.usuario_id = u.id
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[INFO] Auto-sync profissionais notice: {e}")
        except Exception as e:
            print(f"[INFO] DDL schema notice: {e}")

    # Força o Flask a carregar as classes dos modelos e sincronizar tabelas no startup
    with app.app_context():
        from app import models
        from app.models import Escola
        sincronizar_schema_automatico()

    # Registro de Blueprints - Nova Arquitetura SaaS Blindada
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.core.routes import core_bp
    from app.blueprints.alunos.routes import alunos_bp
    from app.blueprints.transporte.routes import transporte_bp
    from app.blueprints.pei.routes import pei_bp
    from app.routes import publico_bp
    from app.blueprints.aee.routes import aee_bp
    from app.blueprints.escolas.routes import escolas_bp
    from app.blueprints.equipe_multi.routes import equipe_multi_bp

    app.register_blueprint(publico_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(core_bp, url_prefix='/<municipio_slug>')
    app.register_blueprint(alunos_bp, url_prefix='/<municipio_slug>/alunos')
    app.register_blueprint(transporte_bp, url_prefix='/<municipio_slug>/transporte')
    app.register_blueprint(pei_bp, url_prefix='/<municipio_slug>/pei')
    app.register_blueprint(aee_bp, url_prefix='/<municipio_slug>/aee')
    app.register_blueprint(escolas_bp, url_prefix='/<municipio_slug>/escolas')
    app.register_blueprint(equipe_multi_bp, url_prefix='/<municipio_slug>/equipe-multi')

    # Injetor de contexto global para os templates (MOVIDO PARA DENTRO DA FUNÇÃO)
    @app.context_processor
    def inject_slug():
        return dict(municipio_slug=getattr(g, 'municipio_slug', None))

    @app.context_processor
    def inject_roles():
        return dict(
            PERFIS={
                'SUPERADMIN': 'superadmin',
                'SECRETARIA': 'secretaria',
                'PSICOPEDAGOGO': 'psicopedagogo',
                'PSICOLOGO': 'psicologo',
                'AEE': 'aee',
                'PROFESSOR': 'professor',
                'LIBRAS': 'professor_libras',
                'BRAILLE': 'professor_braille',
                'FONOAUDIOLOGO': 'fonoaudiologo',
                'TERAPEUTA_OCUPACIONAL': 'terapeuta_ocupacional',
                'ASSISTENTE_SOCIAL': 'assistente_social',
                'DIRETOR': 'diretor',
                'TRANSPORTE': 'transporte',
                'FAMILIA': 'familia'
            }
        )

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    # CARREGAMENTO SEGURO DAS ROTAS DA RAIZ MESTRE
    with app.app_context():
        from app import routes

    return app