# Generated by Django 5.1.6 on 2025-02-21 11:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mi_app', '0003_remove_persona_es_anfitrion'),
    ]

    operations = [
        migrations.AddField(
            model_name='inscripcion',
            name='checkin_completado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='inscripcion',
            name='fecha_checkin',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
