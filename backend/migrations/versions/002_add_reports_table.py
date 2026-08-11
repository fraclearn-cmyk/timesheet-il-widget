"""add reports table

Revision ID: 002
Revises: 001
Create Date: 2026-07-10 13:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('report_type', sa.String(length=50), nullable=False),
        sa.Column('report_format', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('generated_by', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_reports_account_id', 'reports', ['account_id'])
    op.create_index('ix_reports_report_type', 'reports', ['report_type'])
    op.create_index('ix_reports_created_at', 'reports', ['created_at'])
    op.create_index('ix_reports_user_id', 'reports', ['user_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_reports_user_id')
    op.drop_index('ix_reports_created_at')
    op.drop_index('ix_reports_report_type')
    op.drop_index('ix_reports_account_id')
    
    # Drop table
    op.drop_table('reports')
