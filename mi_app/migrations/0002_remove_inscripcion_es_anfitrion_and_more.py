# Generated by Django 5.1.6 on 2025-02-19 19:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mi_app', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='inscripcion',
            name='es_anfitrion',
        ),
        migrations.RemoveField(
            model_name='persona',
            name='a_pagar',
        ),
        migrations.RemoveField(
            model_name='persona',
            name='num_familiares',
        ),
        migrations.RemoveField(
            model_name='persona',
            name='pagado',
        ),
        migrations.RemoveField(
            model_name='persona',
            name='pendiente',
        ),
        migrations.RemoveField(
            model_name='persona',
            name='tipo_alojamiento_deseado',
        ),
        migrations.AddField(
            model_name='inscripcion',
            name='a_pagar',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='inscripcion',
            name='num_familiares',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='inscripcion',
            name='pagado',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='inscripcion',
            name='pendiente',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='inscripcion',
            name='tipo_alojamiento_deseado',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='reservahabitacion',
            name='es_anfitrion',
            field=models.BooleanField(default=False),
        ),
    ]
