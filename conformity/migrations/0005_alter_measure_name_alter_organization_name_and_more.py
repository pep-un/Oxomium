# Generated by Django 4.0.4 on 2022-05-26 21:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0004_conformity_comment_alter_measure_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='measure',
            name='name',
            field=models.CharField(blank=True, max_length=50, unique=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='name',
            field=models.CharField(max_length=256, unique=True),
        ),
        migrations.AlterField(
            model_name='policy',
            name='name',
            field=models.CharField(max_length=256, unique=True),
        ),
        migrations.AlterUniqueTogether(
            name='conformity',
            unique_together={('organization', 'measure')},
        ),
    ]
