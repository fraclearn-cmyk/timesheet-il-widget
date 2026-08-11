"""add rbac tables and extend work_session

Revision ID: 003
Revises: 002
Create Date: 2026-08-11 15:19:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create departments table
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('work_start_time', sa.Time(), nullable=False),
        sa.Column('work_end_time', sa.Time(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_departments_id'), 'departments', ['id'], unique=False)
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('amocrm_user_id', sa.Integer(), nullable=False),
        sa.Column('amocrm_account_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('role', sa.Enum('employee', 'rop', 'admin', name='userrole'), nullable=False, server_default='employee'),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('allow_restart_session', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('amocrm_user_id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_amocrm_user_id'), 'users', ['amocrm_user_id'], unique=True)
    op.create_index(op.f('ix_users_amocrm_account_id'), 'users', ['amocrm_account_id'], unique=False)
    
    # Create rop_permissions table
    op.create_table(
        'rop_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rop_permissions_id'), 'rop_permissions', ['id'], unique=False)
    
    # Create work_comments table
    op.create_table(
        'work_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('work_session_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['work_session_id'], ['work_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_work_comments_id'), 'work_comments', ['id'], unique=False)
    
    # Create dashboard_settings table
    op.create_table(
        'dashboard_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('selected_kpis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('chart_metric', sa.String(length=50), nullable=True, server_default='work_time'),
        sa.Column('chart_period', sa.String(length=20), nullable=True, server_default='day'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_dashboard_settings_id'), 'dashboard_settings', ['id'], unique=False)
    
    # Extend work_sessions table with late arrival tracking
    op.add_column('work_sessions', sa.Column('is_late', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('work_sessions', sa.Column('late_minutes', sa.Integer(), nullable=True))
    op.add_column('work_sessions', sa.Column('late_reason', sa.String(length=500), nullable=True))
    
    # Extend work_sessions table with forced finish tracking
    op.add_column('work_sessions', sa.Column('forced_finish', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('work_sessions', sa.Column('forced_finish_by', sa.Integer(), nullable=True))
    op.add_column('work_sessions', sa.Column('forced_finish_reason', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove columns from work_sessions
    op.drop_column('work_sessions', 'forced_finish_reason')
    op.drop_column('work_sessions', 'forced_finish_by')
    op.drop_column('work_sessions', 'forced_finish')
    op.drop_column('work_sessions', 'late_reason')
    op.drop_column('work_sessions', 'late_minutes')
    op.drop_column('work_sessions', 'is_late')
    
    # Drop tables in reverse order
    op.drop_index(op.f('ix_dashboard_settings_id'), table_name='dashboard_settings')
    op.drop_table('dashboard_settings')
    
    op.drop_index(op.f('ix_work_comments_id'), table_name='work_comments')
    op.drop_table('work_comments')
    
    op.drop_index(op.f('ix_rop_permissions_id'), table_name='rop_permissions')
    op.drop_table('rop_permissions')
    
    op.drop_index(op.f('ix_users_amocrm_account_id'), table_name='users')
    op.drop_index(op.f('ix_users_amocrm_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
    op.execute('DROP TYPE userrole')
    
    op.drop_index(op.f('ix_departments_id'), table_name='departments')
    op.drop_table('departments')
