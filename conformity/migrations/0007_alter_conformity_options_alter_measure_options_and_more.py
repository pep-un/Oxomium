# Generated by Django 4.0.4 on 2022-06-05 17:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0006_alter_measure_parent'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='conformity',
            options={'ordering': ['organization', 'measure'], 'verbose_name': 'Conformity', 'verbose_name_plural': 'Conformities'},
        ),
        migrations.AlterModelOptions(
            name='measure',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='organization',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='policy',
            options={'ordering': ['name'], 'verbose_name': 'Policy', 'verbose_name_plural': 'Policies'},
        ),
        migrations.AddField(
            model_name='conformity',
            name='applicable',
            field=models.BooleanField(default=True),
        ),
    ]
