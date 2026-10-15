"""auth propia

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Vuelta a la autenticación propia (JWT + refresh tokens rotados). Las contraseñas vivían en
    # Firebase y no se pueden traer: "!" no es un hash argon2 válido, así que nadie entra hasta
    # que un admin le restablezca la contraseña (o `crear-admin` por CLI para el primero).
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("hash_contrasena", sa.String(length=255), nullable=False, server_default="!")
        )
        batch_op.drop_index(batch_op.f("ix_usuarios_firebase_uid"))
        batch_op.drop_column("firebase_uid")
        # Versión de sesión (claim "ver" del access token): subirla revoca los tokens ya emitidos
        batch_op.add_column(
            sa.Column("version_sesion", sa.Integer(), nullable=False, server_default="0")
        )
    # El "!" solo hacía falta para rellenar las filas existentes: las nuevas siempre traen hash
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.alter_column("hash_contrasena", server_default=None)

    op.create_table(
        "tokens_refresco",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("hash_token", sa.String(length=64), nullable=False),
        sa.Column("familia_id", sa.String(length=64), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocado_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name=op.f("fk_tokens_refresco_usuario_id_usuarios")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tokens_refresco")),
    )
    with op.batch_alter_table("tokens_refresco", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_tokens_refresco_usuario_id"), ["usuario_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_tokens_refresco_hash_token"), ["hash_token"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_tokens_refresco_familia_id"), ["familia_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("tokens_refresco", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tokens_refresco_familia_id"))
        batch_op.drop_index(batch_op.f("ix_tokens_refresco_hash_token"))
        batch_op.drop_index(batch_op.f("ix_tokens_refresco_usuario_id"))

    op.drop_table("tokens_refresco")
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(sa.Column("firebase_uid", sa.String(length=128), nullable=True))
        batch_op.create_index(batch_op.f("ix_usuarios_firebase_uid"), ["firebase_uid"], unique=True)
        batch_op.drop_column("version_sesion")
        batch_op.drop_column("hash_contrasena")
