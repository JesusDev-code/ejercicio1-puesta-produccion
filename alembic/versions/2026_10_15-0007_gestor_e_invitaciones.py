"""gestor e invitaciones

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-15 17:00:00.000000

"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES_ANTES = "rol IN ('usuario', 'analista', 'admin')"
ROLES_AHORA = "rol IN ('usuario', 'gestor', 'analista', 'admin')"


def generar_codigo_invitacion() -> str:
    # Copia de app.modelos a propósito: una migración no puede depender del código de la app,
    # que cambia; si lo hiciera, dejaría de poder ejecutarse en una BD antigua
    alfabeto = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    simbolos = "".join(secrets.choice(alfabeto) for _ in range(12))
    return "-".join(simbolos[i : i + 4] for i in range(0, 12, 4))


def upgrade() -> None:
    """Upgrade schema."""
    # Nuevo rol: el responsable de una empresa cliente
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_usuarios_rol"), type_="check")
        batch_op.create_check_constraint(op.f("ck_usuarios_rol"), ROLES_AHORA)

    # Código de invitación por empresa. Se añade nullable, se rellena para las que ya existen
    # y solo entonces se hace obligatorio: así no se rompe una BD con clientes dados de alta
    with op.batch_alter_table("empresas", schema=None) as batch_op:
        batch_op.add_column(sa.Column("codigo_invitacion", sa.String(length=14), nullable=True))

    conexion = op.get_bind()
    empresas = sa.table("empresas", sa.column("id", sa.Integer), sa.column("codigo_invitacion"))
    for (empresa_id,) in conexion.execute(sa.select(empresas.c.id)).all():
        conexion.execute(
            empresas.update()
            .where(empresas.c.id == empresa_id)
            .values(codigo_invitacion=generar_codigo_invitacion())
        )

    with op.batch_alter_table("empresas", schema=None) as batch_op:
        batch_op.alter_column(
            "codigo_invitacion", existing_type=sa.String(length=14), nullable=False
        )
        batch_op.create_index(
            batch_op.f("ix_empresas_codigo_invitacion"), ["codigo_invitacion"], unique=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("empresas", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_empresas_codigo_invitacion"))
        batch_op.drop_column("codigo_invitacion")

    # Un gestor no cabe en el esquema anterior: vuelve a ser usuario de su empresa
    op.execute("UPDATE usuarios SET rol = 'usuario' WHERE rol = 'gestor'")
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_usuarios_rol"), type_="check")
        batch_op.create_check_constraint(op.f("ck_usuarios_rol"), ROLES_ANTES)
