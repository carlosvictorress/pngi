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
    
    # Tratamento da URL do banco de dados (Railway/PostgreSQL compatibility)
    db_url = (
        os.getenv('DATABASE_URL') or
        os.getenv('DATABASE_PRIVATE_URL') or
        os.getenv('DATABASE_PUBLIC_URL') or
        os.getenv('POSTGRES_URL') or
        os.getenv('POSTGRESQL_URL') or
        os.getenv('PG_URL') or
        os.getenv('URL_DO_BANCO_DE_DADOS')
    )

    # Se estiver no Railway e a URL for localhost ou vazia, tenta montar a partir das variáveis individuais do Postgres
    is_railway = bool(os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_SERVICE_ID'))
    if (not db_url or (is_railway and ('localhost' in db_url or '127.0.0.1' in db_url))) and os.getenv('PGHOST'):
        pghost = os.getenv('PGHOST')
        pgport = os.getenv('PGPORT', '5432')
        pguser = os.getenv('PGUSER', 'postgres')
        pgpass = os.getenv('PGPASSWORD', '')
        pgdb = os.getenv('PGDATABASE', 'railway')
        db_url = f"postgresql://{pguser}:{pgpass}@{pghost}:{pgport}/{pgdb}"

    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Validação e saneamento de integridade da URL do banco de dados
    if db_url and not db_url.startswith("sqlite"):
        try:
            import sqlalchemy as sa
            sa.engine.make_url(db_url)
        except Exception as e:
            print(f"[AVISO] URL de banco de dados inválida ({e}). Ativando fallback temporário SQLite.")
            db_url = None

    if not db_url:
        print("[AVISO] Nenhuma variável DATABASE_URL válida encontrada no ambiente. Ativando fallback temporário SQLite (sqlite:///inclusao.db). Configure DATABASE_URL no Railway para conectar ao PostgreSQL.")
        db_url = "sqlite:///inclusao.db"
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicialização das Extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # 🚀 GESTOOR 360: Registro do Filtro Global do Jinja2 para decodificação de matrizes JSON
    app.jinja_env.filters['from_json'] = json.loads

    # IMPORTANTE: Força o Flask a carregar as classes dos modelos e sincronizar tabelas
    with app.app_context():
        from app import models
        from app.models import Escola
        try:
            db.create_all()
            if db.engine.name == 'postgresql':
                from sqlalchemy import text
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE alunos ADD COLUMN IF NOT EXISTS endereco VARCHAR(255);"))
                    conn.execute(text("ALTER TABLE alunos ADD COLUMN IF NOT EXISTS bairro VARCHAR(120);"))
                    conn.execute(text("ALTER TABLE alunos ADD COLUMN IF NOT EXISTS em_investigacao BOOLEAN DEFAULT FALSE;"))
                    conn.execute(text("ALTER TABLE alunos ADD COLUMN IF NOT EXISTS hipotese_diagnostica VARCHAR(255);"))
                    
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS municipio_id INTEGER;"))
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS compareceu BOOLEAN DEFAULT TRUE;"))
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS o_que_foi_feito TEXT;"))
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS como_foi_feito TEXT;"))
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS recursos_utilizados VARCHAR(255);"))
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS justificativa_falta VARCHAR(255);"))
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS profissional_id INTEGER;"))
                    conn.execute(text("ALTER TABLE atendimentos_aee ADD COLUMN IF NOT EXISTS profissional_nome VARCHAR(150);"))
                    conn.commit()
        except Exception as e:
            print(f"[INFO] Sincronização inicial de tabelas: {e}")

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