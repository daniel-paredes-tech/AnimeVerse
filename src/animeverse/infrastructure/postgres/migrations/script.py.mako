"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Created: ${create_date}

Expand/contract: an "expand" migration only adds (tables, nullable columns,
indexes). Removing or renaming goes in a later migration whose file name
contains "contract". See docs/migrations.md.
"""

from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    op.execute("""
    """)


def downgrade() -> None:
    op.execute("""
    """)
