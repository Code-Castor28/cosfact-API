# ─── 0002_IMMUTABILITY_TRIGGERS.PY — apps/comprobantes/migrations/0002_immutability_triggers.py ───
"""
apps/comprobantes/migrations/0002_immutability_triggers.py

Triggers de base de datos para garantizar inmutabilidad real.

CONTEXTO:
- El save() de Python es bypasseable con .update() o acceso directo a la DB.
- Estos triggers aplican la inmutabilidad a nivel de motor de base de datos.
- Usar PostgreSQL (recomendado para este proyecto).

INSTRUCCIONES:
1. Crear este archivo en la carpeta migrations de la app correspondiente.
2. Ajustar los números de migración (0002) según lo que ya exista.
3. Aplicar con: python manage.py migrate
"""
from django.db import migrations


# ── Trigger: Comprobante inmutable cuando está ACEPTADO o ANULADO ──────────────
SQL_TRIGGER_COMPROBANTE = """
CREATE OR REPLACE FUNCTION prevent_comprobante_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.estado IN ('ACEPTADO', 'ANULADO') THEN
        RAISE EXCEPTION
            'Comprobante % está en estado % y no puede ser modificado.',
            OLD.id, OLD.estado;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_comprobante_immutable
    BEFORE UPDATE ON comprobantes
    FOR EACH ROW EXECUTE FUNCTION prevent_comprobante_update();
"""

SQL_DROP_TRIGGER_COMPROBANTE = """
DROP TRIGGER IF EXISTS trg_comprobante_immutable ON comprobantes;
DROP FUNCTION IF EXISTS prevent_comprobante_update();
"""

# ── Trigger: Detalle de Comprobante inmutable si el padre está ACEPTADO/ANULADO ─
SQL_TRIGGER_DETALLE = """
CREATE OR REPLACE FUNCTION prevent_detalle_update()
RETURNS TRIGGER AS $$
DECLARE
    estado_padre VARCHAR(15);
BEGIN
    SELECT estado INTO estado_padre FROM comprobantes WHERE id = OLD.comprobante_id;
    IF estado_padre IN ('ACEPTADO', 'ANULADO') THEN
        RAISE EXCEPTION
            'No se puede modificar el detalle del comprobante % en estado %.',
            OLD.comprobante_id, estado_padre;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_detalle_immutable
    BEFORE UPDATE OR DELETE ON comprobante_detalles
    FOR EACH ROW EXECUTE FUNCTION prevent_detalle_update();
"""

SQL_DROP_TRIGGER_DETALLE = """
DROP TRIGGER IF EXISTS trg_detalle_immutable ON comprobante_detalles;
DROP FUNCTION IF EXISTS prevent_detalle_update();
"""

# ── Trigger: AuditLog append-only ──────────────────────────────────────────────
SQL_TRIGGER_AUDIT = """
CREATE OR REPLACE FUNCTION prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Los registros de auditoría son inmutables.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_update();
"""

SQL_DROP_TRIGGER_AUDIT = """
DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_logs;
DROP FUNCTION IF EXISTS prevent_audit_update();
"""

# ── Trigger: DGIILog append-only ───────────────────────────────────────────────
SQL_TRIGGER_DGIILOG = """
CREATE OR REPLACE FUNCTION prevent_dgiilog_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Los logs DGII son inmutables.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_dgiilog_immutable
    BEFORE UPDATE OR DELETE ON dgii_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_dgiilog_update();
"""

SQL_DROP_TRIGGER_DGIILOG = """
DROP TRIGGER IF EXISTS trg_dgiilog_immutable ON dgii_logs;
DROP FUNCTION IF EXISTS prevent_dgiilog_update();
"""


def _run_if_postgres(sql, reverse_sql):
    """Ejecuta SQL solo si el motor de DB es PostgreSQL."""
    from django.db import connection

    def forward(apps, schema_editor):
        if connection.vendor == "postgresql":
            schema_editor.execute(sql)

    def backward(apps, schema_editor):
        if connection.vendor == "postgresql":
            schema_editor.execute(reverse_sql)

    return migrations.RunPython(forward, backward)


class Migration(migrations.Migration):

    dependencies = [
        ("comprobantes", "0001_initial"),
        ("audit", "0001_initial"),
        ("dgii", "0001_initial"),
    ]

    operations = [
        _run_if_postgres(SQL_TRIGGER_COMPROBANTE, SQL_DROP_TRIGGER_COMPROBANTE),
        _run_if_postgres(SQL_TRIGGER_DETALLE, SQL_DROP_TRIGGER_DETALLE),
        _run_if_postgres(SQL_TRIGGER_AUDIT, SQL_DROP_TRIGGER_AUDIT),
        _run_if_postgres(SQL_TRIGGER_DGIILOG, SQL_DROP_TRIGGER_DGIILOG),
    ]