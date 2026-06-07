from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0004_alter_historialpago_unique_together_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='pago',
                    name='fecha_corte',
                    field=models.PositiveSmallIntegerField(blank=True, help_text='Día fijo de facturación (1-30). Se copia de la suscripción al generar el pago.', null=True, validators=[django.core.validators.MaxValueValidator(30)]),
                ),
            ],
            database_operations=[],
        ),
    ]
