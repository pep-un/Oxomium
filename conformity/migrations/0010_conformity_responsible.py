# Generated by Django 4.0.4 on 2022-05-01 19:13

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('conformity', '0009_alter_organization_administrative_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='conformity',
            name='responsible',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
