# Generated by Django 4.1.6 on 2023-02-13 01:08

from django.db import migrations
import tinymce.models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0026_alter_action_control_comment_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='description',
            field=tinymce.models.HTMLField(blank=True, max_length=4096),
        ),
    ]
