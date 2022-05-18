# Generated by Django 4.0.4 on 2022-04-20 08:00

from django.db import migrations
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='policy',
            name='pub_date',
        ),
        migrations.AlterField(
            model_name='mesure',
            name='parent',
            field=mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='conformity.mesure'),
        ),
    ]
