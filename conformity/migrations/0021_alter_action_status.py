# Generated by Django 4.1.5 on 2023-02-06 22:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0020_alter_action_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='status',
            field=models.CharField(choices=[('1', 'Analysing'), ('2', 'Planning'), ('3', 'Implementing'), ('4', 'Controlling'), ('7', 'Frozen'), ('8', 'Closed'), ('9', 'Canceled')], default='1', max_length=5),
        ),
    ]
