# Generated by Django 4.0.4 on 2022-05-05 22:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0010_conformity_responsible'),
    ]

    operations = [
        migrations.AddField(
            model_name='mesure',
            name='order',
            field=models.IntegerField(default=1),
        ),
    ]
