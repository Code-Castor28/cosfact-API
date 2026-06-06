from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0004_alter_historialpago_unique_together_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE pagos DROP COLUMN IF EXISTS fecha_corte;",
            migrations.RunSQL.noop,
        ),
    ]
