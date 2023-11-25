import sqlalchemy as sa

metadata = sa.MetaData()

notes = sa.Table(
    'notes',
    metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('text', sa.String),
    sa.Column('completed', sa.Boolean),
)
