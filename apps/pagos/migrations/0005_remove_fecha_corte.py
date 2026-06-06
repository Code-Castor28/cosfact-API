from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0004_alter_historialpago_unique_together_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pago',
            name='fecha_corte',
        ),
    ]
