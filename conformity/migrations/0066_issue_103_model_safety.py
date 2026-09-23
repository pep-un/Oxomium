from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import conformity.models


class Migration(migrations.Migration):
    dependencies = [
        ('conformity', '0065_alter_control_conformity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='framework',
            name='language',
            field=models.CharField(
                max_length=2, choices=conformity.models.language_choices, default='en'
            ),
        ),
        migrations.AlterField(
            model_name='requirement',
            name='framework',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='requirements',
                to='conformity.framework',
            ),
        ),
        migrations.AlterField(
            model_name='conformity',
            name='organization',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conformities',
                to='conformity.organization',
            ),
        ),
        migrations.AlterField(
            model_name='conformity',
            name='requirement',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conformities',
                to='conformity.requirement',
            ),
        ),
        migrations.AlterField(
            model_name='conformity',
            name='responsible',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterUniqueTogether(name='conformity', unique_together=set()),
        migrations.AddConstraint(
            model_name='conformity',
            constraint=models.UniqueConstraint(
                fields=('organization', 'requirement'),
                name='uq_conformity_org_req',
            ),
        ),
        migrations.AddConstraint(
            model_name='conformity',
            constraint=models.CheckConstraint(
                condition=models.Q(status__isnull=True) |
                          (models.Q(status__gte=0) & models.Q(status__lte=100)),
                name='chk_conformity_status_0_100',
            ),
        ),
    ]
