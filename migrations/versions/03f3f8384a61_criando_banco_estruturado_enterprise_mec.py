"""Criando banco estruturado enterprise MEC

Revision ID: 03f3f8384a61
Revises: 
Create Date: 2026-05-22 13:04:59.523957

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '03f3f8384a61'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'municipios' not in tables:
        op.create_table('municipios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('estado', sa.String(length=2), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('brasao_url', sa.String(length=255), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.Column('limite_alunos', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome')
        )
        with op.batch_alter_table('municipios', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_municipios_slug'), ['slug'], unique=True)

    if 'usuarios' not in tables:
        op.create_table('usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('municipio_id', sa.Integer(), nullable=True),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('senha_hash', sa.String(length=256), nullable=False),
        sa.Column('perfil', sa.String(length=30), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('usuarios', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_usuarios_email'), ['email'], unique=True)

    if 'alunos' not in tables:
        op.create_table('alunos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('municipio_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('matricula', sa.String(length=30), nullable=False),
        sa.Column('escola', sa.String(length=100), nullable=False),
        sa.Column('turma', sa.String(length=50), nullable=False),
        sa.Column('cid', sa.String(length=15), nullable=True),
        sa.Column('tipo_deficiencia', sa.String(length=100), nullable=False),
        sa.Column('possui_tea', sa.Boolean(), nullable=False),
        sa.Column('possui_superdotacao', sa.Boolean(), nullable=False),
        sa.Column('medicacoes', sa.Text(), nullable=True),
        sa.Column('restricoes_alimentares', sa.Text(), nullable=True),
        sa.Column('acessibilidade_necessaria', sa.Text(), nullable=True),
        sa.Column('responsavel_id', sa.Integer(), nullable=True),
        sa.Column('contato_urgencia', sa.String(length=50), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id'], ),
        sa.ForeignKeyConstraint(['responsavel_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('matricula')
        )
        with op.batch_alter_table('alunos', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_alunos_municipio_id'), ['municipio_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_alunos_nome'), ['nome'], unique=False)

    if 'atendimentos_aee' not in tables:
        op.create_table('atendimentos_aee',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('data_atendimento', sa.Date(), nullable=False),
        sa.Column('horario_inicio', sa.Time(), nullable=False),
        sa.Column('horario_fim', sa.Time(), nullable=False),
        sa.Column('frequencia', sa.Boolean(), nullable=False),
        sa.Column('plano_sessao', sa.Text(), nullable=False),
        sa.Column('evolucao_registro', sa.Text(), nullable=False),
        sa.Column('recursos_utilizados', sa.String(length=200), nullable=True),
        sa.Column('registrado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    if 'peis' not in tables:
        op.create_table('peis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('professor_id', sa.Integer(), nullable=False),
        sa.Column('ano_letivo', sa.Integer(), nullable=False),
        sa.Column('periodo_trimestre', sa.Integer(), nullable=False),
        sa.Column('barreiras_arquitetonicas', sa.Text(), nullable=True),
        sa.Column('barreiras_atidudinais', sa.Text(), nullable=True),
        sa.Column('barreiras_pedagogicas', sa.Text(), nullable=True),
        sa.Column('potencialidades_cognitivas', sa.Text(), nullable=False),
        sa.Column('frequencia_srm_semanal', sa.Integer(), nullable=True),
        sa.Column('organizacao_atendimento', sa.String(length=30), nullable=True),
        sa.Column('objetivos_curto_prazo_acad', sa.Text(), nullable=False),
        sa.Column('objetivos_medio_prazo_acad', sa.Text(), nullable=False),
        sa.Column('objetivos_longo_prazo_acad', sa.Text(), nullable=False),
        sa.Column('estrategias_pedagogicas_acad', sa.Text(), nullable=False),
        sa.Column('objetivos_curto_prazo_auton', sa.Text(), nullable=False),
        sa.Column('objetivos_longo_prazo_auton', sa.Text(), nullable=False),
        sa.Column('estrategias_desenvolvimento_auton', sa.Text(), nullable=False),
        sa.Column('recursos_opticos_adicionais', sa.Boolean(), nullable=True),
        sa.Column('recursos_comunicacao_alternativa', sa.Boolean(), nullable=True),
        sa.Column('recursos_acessibilidade_informatica', sa.Boolean(), nullable=True),
        sa.Column('recursos_atendimento_libras', sa.Boolean(), nullable=True),
        sa.Column('necessita_profissional_apoio', sa.Boolean(), nullable=True),
        sa.Column('atividades_apoio_especificadas', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('assinado_professor', sa.Boolean(), nullable=True),
        sa.Column('assinado_professor_em', sa.DateTime(), nullable=True),
        sa.Column('assinado_coordenador_aee', sa.Boolean(), nullable=True),
        sa.Column('assinado_coordenador_aee_em', sa.DateTime(), nullable=True),
        sa.Column('homologado_secretaria', sa.Boolean(), nullable=True),
        sa.Column('homologado_secretaria_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id'], ),
        sa.ForeignKeyConstraint(['professor_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    if 'transporte_alunado' not in tables:
        op.create_table('transporte_alunado',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('necessita_veiculo_adaptado', sa.Boolean(), nullable=False),
        sa.Column('cadeirante', sa.Boolean(), nullable=False),
        sa.Column('necessita_acompanhante', sa.Boolean(), nullable=False),
        sa.Column('possui_monitor_rota', sa.Boolean(), nullable=False),
        sa.Column('rota_codigo', sa.String(length=50), nullable=True),
        sa.Column('ponto_embarque', sa.String(length=150), nullable=True),
        sa.Column('observacoes_logistica', sa.Text(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aluno_id')
        )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('transporte_alunado')
    op.drop_table('peis')
    op.drop_table('atendimentos_aee')
    with op.batch_alter_table('alunos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alunos_nome'))
        batch_op.drop_index(batch_op.f('ix_alunos_municipio_id'))

    op.drop_table('alunos')
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuarios_email'))

    op.drop_table('usuarios')
    with op.batch_alter_table('municipios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_municipios_slug'))

    op.drop_table('municipios')
    # ### end Alembic commands ###
