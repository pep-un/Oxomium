# Generated by Django 4.1.5 on 2023-02-07 04:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0021_alter_action_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='status_comment',
            field=models.CharField(blank=True, max_length=4096),
        ),
    ]