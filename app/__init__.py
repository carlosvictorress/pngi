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
                    "ALTER TABLE lista_espera_aee ALTER COLUMN status DROP NOT NULL;"
                ]
                for ddl in ddl_comandos:
                    try:
                        conn.execute(text(ddl))
                    except Exception:
                        pass
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