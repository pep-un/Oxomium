# Generated by Django 4.1.6 on 2023-02-25 21:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0033_alter_controlpoint_control_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='controlpoint',
            name='control_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
