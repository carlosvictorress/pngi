"""Adiciona tabelas e colunas para Sala de AEE (SRM) e Equipe Multiprofissional

Revision ID: f78e12a4b9c1
Revises: e2658e98ec63
Create Date: 2026-10-09 17:47:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f78e12a4b9c1'
down_revision = 'e2658e98ec63'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Colunas adicionais na tabela ALUNOS
    if 'alunos' in tables:
        cols_alunos = [c['name'] for c in inspector.get_columns('alunos')]
        with op.batch_alter_table('alunos', schema=None) as batch_op:
            if 'endereco' not in cols_alunos:
                batch_op.add_column(sa.Column('endereco', sa.String(length=255), nullable=True))
            if 'bairro' not in cols_alunos:
                batch_op.add_column(sa.Column('bairro', sa.String(length=120), nullable=True))
            if 'em_investigacao' not in cols_alunos:
                batch_op.add_column(sa.Column('em_investigacao', sa.Boolean(), server_default='false', nullable=True))
            if 'hipotese_diagnostica' not in cols_alunos:
                batch_op.add_column(sa.Column('hipotese_diagnostica', sa.String(length=255), nullable=True))

    # 2. Colunas adicionais na tabela ATENDIMENTOS_AEE
    if 'atendimentos_aee' in tables:
        cols_atend = [c['name'] for c in inspector.get_columns('atendimentos_aee')]
        with op.batch_alter_table('atendimentos_aee', schema=None) as batch_op:
            if 'municipio_id' not in cols_atend:
                batch_op.add_column(sa.Column('municipio_id', sa.Integer(), sa.ForeignKey('municipios.id'), nullable=True))
            if 'compareceu' not in cols_atend:
                batch_op.add_column(sa.Column('compareceu', sa.Boolean(), server_default='true', nullable=True))
            if 'o_que_foi_feito' not in cols_atend:
                batch_op.add_column(sa.Column('o_que_foi_feito', sa.Text(), nullable=True))
            if 'como_foi_feito' not in cols_atend:
                batch_op.add_column(sa.Column('como_foi_feito', sa.Text(), nullable=True))
            if 'recursos_utilizados' not in cols_atend:
                batch_op.add_column(sa.Column('recursos_utilizados', sa.String(length=255), nullable=True))
            if 'justificativa_falta' not in cols_atend:
                batch_op.add_column(sa.Column('justificativa_falta', sa.String(length=255), nullable=True))
            if 'profissional_id' not in cols_atend:
                batch_op.add_column(sa.Column('profissional_id', sa.Integer(), sa.ForeignKey('profissionais_aee.id'), nullable=True))
            if 'profissional_nome' not in cols_atend:
                batch_op.add_column(sa.Column('profissional_nome', sa.String(length=150), nullable=True))

    # 3. Tabela LISTA_ESPERA_AEE
    if 'lista_espera_aee' not in tables:
        op.create_table(
            'lista_espera_aee',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('municipio_id', sa.Integer(), nullable=False),
            sa.Column('aluno_id', sa.Integer(), nullable=True),
            sa.Column('nome_completo', sa.String(length=150), nullable=False),
            sa.Column('data_nascimento', sa.String(length=20), nullable=False),
            sa.Column('cpf', sa.String(length=20), nullable=True),
            sa.Column('telefone', sa.String(length=30), nullable=False),
            sa.Column('escola_origem', sa.String(length=150), nullable=True),
            sa.Column('serie_ano', sa.String(length=50), nullable=True),
            sa.Column('diagnostico_hipotese', sa.String(length=255), nullable=True),
            sa.Column('motivo_encaminhamento', sa.Text(), nullable=True),
            sa.Column('prioridade', sa.String(length=30), server_default='Média', nullable=False),
            sa.Column('status', sa.String(length=30), server_default='Aguardando Vaga', nullable=False),
            sa.Column('observacoes_triagem', sa.Text(), nullable=True),
            sa.Column('data_solicitacao', sa.DateTime(), nullable=True),
            sa.Column('data_atualizacao', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id']),
            sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id']),
            sa.PrimaryKeyConstraint('id')
        )

    # 4. Tabela ATENDIMENTOS_MULTI_SOAP
    if 'atendimentos_multi_soap' not in tables:
        op.create_table(
            'atendimentos_multi_soap',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('municipio_id', sa.Integer(), nullable=False),
            sa.Column('aluno_id', sa.Integer(), nullable=False),
            sa.Column('profissional_id', sa.Integer(), nullable=False),
            sa.Column('especialidade', sa.String(length=40), nullable=False),
            sa.Column('data_atendimento', sa.Date(), nullable=False),
            sa.Column('horario_inicio', sa.String(length=10), nullable=True),
            sa.Column('horario_fim', sa.String(length=10), nullable=True),
            sa.Column('tipo_sessao', sa.String(length=60), server_default='Individual', nullable=True),
            sa.Column('compareceu', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('justificativa_falta', sa.String(length=255), nullable=True),
            sa.Column('soap_subjetivo', sa.Text(), nullable=True),
            sa.Column('soap_objetivo', sa.Text(), nullable=True),
            sa.Column('soap_avaliacao', sa.Text(), nullable=True),
            sa.Column('soap_plano', sa.Text(), nullable=True),
            sa.Column('sigilo_etico', sa.Boolean(), server_default='false', nullable=True),
            sa.Column('data_registro', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id']),
            sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id']),
            sa.ForeignKeyConstraint(['profissional_id'], ['usuarios.id']),
            sa.PrimaryKeyConstraint('id')
        )

    # 5. Tabela RELATORIOS_ESCUTA_ENCAMINHAMENTOS
    if 'relatorios_escuta_encaminhamentos' not in tables:
        op.create_table(
            'relatorios_escuta_encaminhamentos',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('municipio_id', sa.Integer(), nullable=False),
            sa.Column('aluno_id', sa.Integer(), nullable=False),
            sa.Column('profissional_id', sa.Integer(), nullable=False),
            sa.Column('especialidade_emissor', sa.String(length=40), nullable=False),
            sa.Column('tipo_documento', sa.String(length=50), server_default='Encaminhamento Intersetorial', nullable=False),
            sa.Column('orgao_destino', sa.String(length=150), nullable=False),
            sa.Column('motivo_demanda', sa.String(length=255), nullable=False),
            sa.Column('sintese_escuta_qualificada', sa.Text(), nullable=False),
            sa.Column('evidencias_observadas', sa.Text(), nullable=True),
            sa.Column('acoes_ja_realizadas_escola', sa.Text(), nullable=True),
            sa.Column('sugestoes_encaminhamento', sa.Text(), nullable=False),
            sa.Column('gerado_com_ia', sa.Boolean(), server_default='false', nullable=True),
            sa.Column('chave_autenticidade', sa.String(length=64), nullable=True),
            sa.Column('data_emissao', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id']),
            sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id']),
            sa.ForeignKeyConstraint(['profissional_id'], ['usuarios.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('chave_autenticidade')
        )

    # 6. Tabela PLANOS_ACAO_MENSAIS_MULTI
    if 'planos_acao_mensais_multi' not in tables:
        op.create_table(
            'planos_acao_mensais_multi',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('municipio_id', sa.Integer(), nullable=False),
            sa.Column('mes_referencia', sa.Integer(), nullable=False),
            sa.Column('ano_referencia', sa.Integer(), nullable=False),
            sa.Column('data_reuniao', sa.Date(), nullable=False),
            sa.Column('coordenador_reuniao_id', sa.Integer(), nullable=False),
            sa.Column('participantes_nomes', sa.Text(), nullable=False),
            sa.Column('pauta_discutida', sa.Text(), nullable=False),
            sa.Column('casos_discutidos', sa.Text(), nullable=False),
            sa.Column('acoes_psicologia', sa.Text(), nullable=True),
            sa.Column('acoes_psicopedagogia', sa.Text(), nullable=True),
            sa.Column('acoes_servico_social', sa.Text(), nullable=True),
            sa.Column('encaminhamentos_gestao', sa.Text(), nullable=False),
            sa.Column('metas_proximo_mes', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=30), server_default='Finalizado e Assinado', nullable=False),
            sa.Column('chave_autenticidade', sa.String(length=64), nullable=True),
            sa.Column('data_criacao', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['coordenador_reuniao_id'], ['usuarios.id']),
            sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('chave_autenticidade')
        )


def downgrade():
    op.drop_table('planos_acao_mensais_multi')
    op.drop_table('relatorios_escuta_encaminhamentos')
    op.drop_table('atendimentos_multi_soap')
    op.drop_table('lista_espera_aee')
