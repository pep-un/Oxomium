# Generated by Django 4.2.9 on 2024-10-12 04:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0046_alter_attachment_mime_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='create_date',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]