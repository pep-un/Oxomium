# Generated by Django 4.0.4 on 2022-07-09 16:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0008_audit_finding'),
    ]

    operations = [
        migrations.RenameField(
            model_name='audit',
            old_name='auditors',
            new_name='auditor',
        ),
    ]
