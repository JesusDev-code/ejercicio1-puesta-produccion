"""mfa y oauth

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # MFA (TOTP): todas las columnas admiten NULL o traen valor por defecto, así que las cuentas
    # que ya existen quedan sin MFA y no hace falta rellenar nada
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mfa_secreto", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("mfa_pendiente", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("mfa_ultimo_paso", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("mfa_fallos", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("mfa_bloqueado_hasta", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "codigos_recuperacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("hash_codigo", sa.String(length=64), nullable=False),
        sa.Column("usado_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_codigos_recuperacion_usuario_id_usuarios"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_codigos_recuperacion")),
    )
    with op.batch_alter_table("codigos_recuperacion", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_codigos_recuperacion_usuario_id"), ["usuario_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_codigos_recuperacion_hash_codigo"), ["hash_codigo"], unique=False
        )

    # Cuentas de Google o GitHub vinculadas. Única por (proveedor, sujeto)
    op.create_table(
        "identidades_externas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("proveedor", sa.String(length=20), nullable=False),
        sa.Column("sujeto", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_identidades_externas_usuario_id_usuarios"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identidades_externas")),
        sa.UniqueConstraint("proveedor", "sujeto", name=op.f("uq_identidades_externas_proveedor")),
    )
    with op.batch_alter_table("identidades_externas", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_identidades_externas_usuario_id"), ["usuario_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("identidades_externas", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_identidades_externas_usuario_id"))
    op.drop_table("identidades_externas")

    with op.batch_alter_table("codigos_recuperacion", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_codigos_recuperacion_hash_codigo"))
        batch_op.drop_index(batch_op.f("ix_codigos_recuperacion_usuario_id"))
    op.drop_table("codigos_recuperacion")

    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_column("mfa_bloqueado_hasta")
        batch_op.drop_column("mfa_fallos")
        batch_op.drop_column("mfa_ultimo_paso")
        batch_op.drop_column("mfa_pendiente")
        batch_op.drop_column("mfa_secreto")
