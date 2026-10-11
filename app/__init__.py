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
    
    # Tratamento robusto da URL do banco de dados (Compatibilidade nativa Railway / PostgreSQL)
    import re
    db_url = (
        os.getenv('DATABASE_URL') or
        os.getenv('DATABASE_PUBLIC_URL') or
        os.getenv('DATABASE_PRIVATE_URL') or
        os.getenv('POSTGRES_URL') or
        os.getenv('POSTGRESQL_URL') or
        os.getenv('PG_URL') or
        os.getenv('URL_DO_BANCO_DE_DADOS')
    )

    # Varredura inteligente de variáveis de ambiente injetadas pelo Railway
    if not db_url:
        for k, v in os.environ.items():
            if isinstance(v, str) and (v.startswith('postgresql://') or v.startswith('postgres://')):
                db_url = v
                break

    # Se ainda não encontrou ou contém referência não resolvida do Railway, tenta montar a partir das variáveis individuais
    if not db_url or '${{' in str(db_url):
        pghost = os.getenv('PGHOST') or os.getenv('POSTGRES_HOST')
        if pghost:
            pgport = os.getenv('PGPORT') or os.getenv('POSTGRES_PORT', '5432')
            pguser = os.getenv('PGUSER') or os.getenv('POSTGRES_USER', 'postgres')
            pgpass = os.getenv('PGPASSWORD') or os.getenv('POSTGRES_PASSWORD', '')
            pgdb = os.getenv('PGDATABASE') or os.getenv('POSTGRES_DB', 'railway')
            db_url = f"postgresql://{pguser}:{pgpass}@{pghost}:{pgport}/{pgdb}"

    # Sanitização de portas e protocolos
    if db_url:
        db_url = re.sub(r':porta\b', ':5432', db_url, flags=re.IGNORECASE)
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

    is_railway = bool(os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_SERVICE_ID') or os.getenv('RAILWAY_PROJECT_ID'))
    if not db_url and is_railway:
        # No Railway, se nenhuma URL explícita foi injetada, conecta à rede interna do Postgres
        pghost = os.getenv('PGHOST', 'postgres.railway.internal')
        pgport = os.getenv('PGPORT', '5432')
        pguser = os.getenv('PGUSER', 'postgres')
        pgpass = os.getenv('PGPASSWORD', '')
        pgdb = os.getenv('PGDATABASE', 'railway')
        db_url = f"postgresql://{pguser}:{pgpass}@{pghost}:{pgport}/{pgdb}"

    # Fallback exclusivo para desenvolvimento local offline na máquina do desenvolvedor
    if not db_url:
        if not is_railway:
            db_url = "sqlite:///inclusao.db"
        else:
            db_url = "postgresql://postgres:postgres@localhost:5432/railway"

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicialização das Extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # 🚀 GESTOOR 360: Registro do Filtro Global do Jinja2 para decodificação de matrizes JSON
    app.jinja_env.filters['from_json'] = json.loads

    def sincronizar_schema_automatico():
        """Garante que todas as tabelas e novas colunas dos novos módulos existam no banco de dados com autocommit isolado."""
        try:
            from sqlalchemy import text
            if db.engine.name == 'postgresql':
                with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    comandos_colunas = [
                        "ALTER TABLE alunos ADD COLUMN IF NOT EXISTS endereco VARCHAR(255);",
                        "ALTER TABLE alunos ADD COLUMN IF NOT EXISTS bairro VARCHAR(120);",
                        "ALTER TABLE alunos ADD COLUMN IF NOT EXISTS em_investigacao BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE alunos ADD COLUMN IF NOT EXISTS hipotese_diagnostica VARCHAR(255);",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS municipio_id INTEGER;",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS compareceu BOOLEAN DEFAULT TRUE;",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS o_que_foi_feito TEXT;",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS como_foi_feito TEXT;",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS recursos_utilizados VARCHAR(255);",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS justificativa_falta VARCHAR(255);",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS profissional_id INTEGER;",
                        "ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS profissional_nome VARCHAR(150);",
                    ]
                    for cmd in comandos_colunas:
                        try:
                            conn.execute(text(cmd))
                        except Exception as ex_col:
                            print(f"[DDL-COL] Aviso ao alterar coluna: {ex_col}")

                    tabelas_ddl = [
                        """
                        CREATE TABLE IF NOT EXISTS lista_espera_aee (
                            id SERIAL PRIMARY KEY,
                            municipio_id INTEGER NOT NULL REFERENCES municipios(id),
                            aluno_id INTEGER REFERENCES alunos(id),
                            nome_completo VARCHAR(150) NOT NULL,
                            data_nascimento VARCHAR(20),
                            cpf VARCHAR(20),
                            telefone VARCHAR(30) NOT NULL,
                            nome_responsavel VARCHAR(150),
                            escola_origem VARCHAR(150),
                            ano_serie VARCHAR(50),
                            endereco VARCHAR(255),
                            diagnostico_hipotese VARCHAR(255),
                            em_investigacao BOOLEAN DEFAULT FALSE,
                            prioridade VARCHAR(30) DEFAULT 'Média',
                            status VARCHAR(40) DEFAULT 'Aguardando Vaga',
                            turno_pretendido VARCHAR(30) DEFAULT 'Contraturno',
                            observacoes_triagem TEXT,
                            data_solicitacao DATE DEFAULT CURRENT_DATE,
                            data_atendimento TIMESTAMP,
                            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """,
                        """
                        CREATE TABLE IF NOT EXISTS atendimentos_multi_soap (
                            id SERIAL PRIMARY KEY,
                            municipio_id INTEGER NOT NULL REFERENCES municipios(id),
                            aluno_id INTEGER NOT NULL REFERENCES alunos(id),
                            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                            especialidade VARCHAR(50) NOT NULL,
                            data_atendimento DATE DEFAULT CURRENT_DATE,
                            horario_inicio VARCHAR(10),
                            horario_fim VARCHAR(10),
                            tipo_sessao VARCHAR(50) DEFAULT 'Individual',
                            soap_subjetivo TEXT,
                            soap_objetivo TEXT,
                            soap_avaliacao TEXT,
                            soap_plano TEXT,
                            encaminhamento_sugerido VARCHAR(150),
                            sigilo_etico BOOLEAN DEFAULT FALSE,
                            status VARCHAR(30) DEFAULT 'Finalizado',
                            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """,
                        """
                        CREATE TABLE IF NOT EXISTS relatorios_escuta_encaminhamentos (
                            id SERIAL PRIMARY KEY,
                            municipio_id INTEGER NOT NULL REFERENCES municipios(id),
                            aluno_id INTEGER NOT NULL REFERENCES alunos(id),
                            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                            tipo_documento VARCHAR(80) NOT NULL,
                            orgao_destino VARCHAR(150) NOT NULL,
                            motivo_demanda TEXT NOT NULL,
                            sintese_escuta TEXT NOT NULL,
                            situacao_contextual TEXT,
                            hipotese_ou_vulnerabilidade TEXT,
                            providencias_recomendadas TEXT NOT NULL,
                            urgencia VARCHAR(20) DEFAULT 'Média',
                            gerado_com_ia BOOLEAN DEFAULT FALSE,
                            ia_prompt_ou_modelo VARCHAR(100),
                            chave_autenticidade VARCHAR(64) UNIQUE,
                            status VARCHAR(30) DEFAULT 'Emitido',
                            data_emissao DATE DEFAULT CURRENT_DATE,
                            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """,
                        """
                        CREATE TABLE IF NOT EXISTS planos_acao_mensais_multi (
                            id SERIAL PRIMARY KEY,
                            municipio_id INTEGER NOT NULL REFERENCES municipios(id),
                            usuario_coordenador_id INTEGER NOT NULL REFERENCES usuarios(id),
                            titulo VARCHAR(150) NOT NULL,
                            mes_referencia VARCHAR(30) NOT NULL,
                            ano_referencia INTEGER DEFAULT 2026,
                            data_reuniao DATE DEFAULT CURRENT_DATE,
                            local_reuniao VARCHAR(150) DEFAULT 'Secretaria Municipal de Educação',
                            profissionais_presentes TEXT NOT NULL,
                            casos_discutidos_json TEXT,
                            acoes_psicologia TEXT,
                            acoes_psicopedagogia TEXT,
                            acoes_servico_social TEXT,
                            deliberacoes_gerais TEXT,
                            metas_proximo_mes TEXT,
                            status VARCHAR(40) DEFAULT 'Homologado',
                            chave_documento VARCHAR(64) UNIQUE,
                            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    ]
                    for tbl_cmd in tabelas_ddl:
                        try:
                            conn.execute(text(tbl_cmd))
                        except Exception as ex_tbl:
                            print(f"[DDL-TBL] Aviso ao criar tabela: {ex_tbl}")

            try:
                db.create_all()
            except Exception as ex_all:
                print(f"[DDL-CREATE-ALL] Aviso: {ex_all}")
        except Exception as e:
            print(f"[INFO] Auto-sync notice: {e}")

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