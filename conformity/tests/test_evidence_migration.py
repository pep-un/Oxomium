from datetime import date, timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class EvidenceMigrationTests(TransactionTestCase):
    migrate_from = [('conformity', '0072_attachment_sha256')]
    migrate_to = [('conformity', '0073_evidence_models')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps

        User = old_apps.get_model('auth', 'User')
        Framework = old_apps.get_model('conformity', 'Framework')
        Requirement = old_apps.get_model('conformity', 'Requirement')
        Organization = old_apps.get_model('conformity', 'Organization')
        Conformity = old_apps.get_model('conformity', 'Conformity')
        Control = old_apps.get_model('conformity', 'Control')
        ControlPoint = old_apps.get_model('conformity', 'ControlPoint')
        Indicator = old_apps.get_model('conformity', 'Indicator')
        IndicatorPoint = old_apps.get_model('conformity', 'IndicatorPoint')
        Attachment = old_apps.get_model('conformity', 'Attachment')
        Audit = old_apps.get_model('conformity', 'Audit')
        Finding = old_apps.get_model('conformity', 'Finding')

        user = User.objects.create(username='migration-user')
        framework = Framework.objects.create(name='Migration framework')
        requirement = Requirement.objects.create(
            framework=framework, code='M1', name='Migration requirement',
            level=0, tree_id=1, lft=1, rght=2,
        )
        organization = Organization.objects.create(name='Migration organization')
        conformity = Conformity.objects.create(
            organization=organization, requirement=requirement,
            status=50, status_justification='EXPT',
            status_last_update=timezone.now(), responsible_id=user.pk,
            comment='Legacy expert conclusion',
        )
        attachment = Attachment.objects.create(file='attachments/legacy.txt')

        control = Control.objects.create(title='Legacy control', organization=organization)
        control.conformity.add(conformity)
        control_point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=2),
            period_end_date=date.today() + timedelta(days=2),
            status='NOK', comment='Legacy control result', control_user_id=user.pk,
        )
        control_point.attachment.add(attachment)

        indicator = Indicator.objects.create(
            name='Legacy indicator', responsible_id=user.pk,
            organization=organization,
        )
        indicator.conformity.add(conformity)
        indicator_point = IndicatorPoint.objects.create(
            indicator=indicator,
            period_start_date=date.today() - timedelta(days=2),
            period_end_date=date.today() + timedelta(days=2),
            status='OK', value=90, comment='Legacy indicator result',
            control_user_id=user.pk,
        )
        indicator_point.attachment.add(attachment)

        audit = Audit.objects.create(
            organization=organization, auditor='Legacy auditor',
            report_date=date.today(),
        )
        finding = Finding.objects.create(
            audit=audit, short_description='Legacy finding', severity='MAJ',
            observation='Legacy observation',
        )
        self.ids = {
            'conformity': conformity.pk,
            'control_point': control_point.pk,
            'indicator_point': indicator_point.pk,
            'attachment': attachment.pk,
            'finding': finding.pk,
        }

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_forward_backfill_and_reverse_preserve_legacy_records(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        apps = self.executor.loader.project_state(self.migrate_to).apps

        ControlPoint = apps.get_model('conformity', 'ControlPoint')
        IndicatorPoint = apps.get_model('conformity', 'IndicatorPoint')
        HumanEvidence = apps.get_model('conformity', 'HumanEvidence')
        FindingEvidence = apps.get_model('conformity', 'FindingEvidence')
        DocumentEvidence = apps.get_model('conformity', 'DocumentEvidence')

        control_point = ControlPoint.objects.get(pk=self.ids['control_point'])
        indicator_point = IndicatorPoint.objects.get(pk=self.ids['indicator_point'])
        self.assertEqual(control_point.evidence.result, 'NEG')
        self.assertEqual(indicator_point.evidence.result, 'POS')
        self.assertEqual(control_point.evidence.comment, 'Legacy control result')
        self.assertEqual(indicator_point.evidence.comment, 'Legacy indicator result')
        self.assertEqual(
            list(control_point.evidence.conformities.values_list('pk', flat=True)),
            [self.ids['conformity']],
        )
        self.assertEqual(
            list(control_point.evidence.attachments.values_list('pk', flat=True)),
            [self.ids['attachment']],
        )
        human = HumanEvidence.objects.get()
        self.assertEqual(human.decision, 'PAR')
        self.assertEqual(human.comment, 'Legacy expert conclusion')
        self.assertTrue(FindingEvidence.objects.filter(finding_id=self.ids['finding']).exists())
        self.assertTrue(
            DocumentEvidence.objects.filter(document_id=self.ids['attachment']).exists()
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        old_control_point = old_apps.get_model('conformity', 'ControlPoint').objects.get(
            pk=self.ids['control_point']
        )
        old_indicator_point = old_apps.get_model('conformity', 'IndicatorPoint').objects.get(
            pk=self.ids['indicator_point']
        )
        self.assertEqual(old_control_point.status, 'NOK')
        self.assertEqual(old_control_point.comment, 'Legacy control result')
        self.assertEqual(old_indicator_point.status, 'OK')
        self.assertEqual(old_indicator_point.value, 90)
