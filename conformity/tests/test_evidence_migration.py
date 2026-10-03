from datetime import date, timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class EvidenceMigrationTests(TransactionTestCase):
    migrate_from = [('conformity', '0072_attachment_sha256')]
    migrate_to = [('conformity', '0075_backfill_evidence_state')]

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
        Conformity = apps.get_model('conformity', 'Conformity')

        control_point = ControlPoint.objects.get()
        indicator_point = IndicatorPoint.objects.get()
        self.assertEqual(control_point.result, 'NEG')
        self.assertEqual(indicator_point.result, 'POS')
        self.assertEqual(control_point.comment, 'Legacy control result')
        self.assertEqual(indicator_point.comment, 'Legacy indicator result')
        self.assertEqual(
            list(control_point.conformities.values_list('pk', flat=True)),
            [self.ids['conformity']],
        )
        self.assertEqual(
            list(control_point.attachments.values_list('pk', flat=True)),
            [self.ids['attachment']],
        )
        human = HumanEvidence.objects.get()
        self.assertEqual(human.decision, 'PAR')
        self.assertEqual(human.comment, 'Legacy expert conclusion')
        self.assertTrue(FindingEvidence.objects.filter(finding_id=self.ids['finding']).exists())
        self.assertTrue(
            DocumentEvidence.objects.filter(document_id=self.ids['attachment']).exists()
        )
        self.assertEqual(
            Conformity.objects.get(pk=self.ids['conformity']).evidence_state,
            'PART',
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        old_control_point = old_apps.get_model('conformity', 'ControlPoint').objects.get()
        old_indicator_point = old_apps.get_model('conformity', 'IndicatorPoint').objects.get()
        self.assertEqual(old_control_point.status, 'NOK')
        self.assertEqual(old_control_point.comment, 'Legacy control result')
        self.assertEqual(old_indicator_point.status, 'OK')
        self.assertEqual(old_indicator_point.value, 90)

class FindingEvidenceMergeMigrationTests(TransactionTestCase):
    migrate_from = [('conformity', '0078_evidence_status')]
    migrate_to = [('conformity', '0079_merge_finding_into_evidence')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        apps = self.executor.loader.project_state(self.migrate_from).apps

        User = apps.get_model('auth', 'User')
        Framework = apps.get_model('conformity', 'Framework')
        Requirement = apps.get_model('conformity', 'Requirement')
        Organization = apps.get_model('conformity', 'Organization')
        Conformity = apps.get_model('conformity', 'Conformity')
        Audit = apps.get_model('conformity', 'Audit')
        Finding = apps.get_model('conformity', 'Finding')
        FindingEvidence = apps.get_model('conformity', 'FindingEvidence')
        Action = apps.get_model('conformity', 'Action')
        Attachment = apps.get_model('conformity', 'Attachment')

        user = User.objects.create(username='finding-migration-user')
        framework = Framework.objects.create(name='Finding migration framework')
        requirement = Requirement.objects.create(
            framework=framework,
            code='FM1',
            name='FM1',
            level=0,
            tree_id=1,
            lft=1,
            rght=2,
        )
        organization = Organization.objects.create(name='Finding migration organization')
        conformity = Conformity.objects.create(
            organization=organization,
            requirement=requirement,
        )
        audit = Audit.objects.create(
            organization=organization,
            auditor='Migration auditor',
            report_date=date.today(),
        )
        finding = Finding.objects.create(
            audit=audit,
            short_description='Legacy merged finding',
            severity='MAJ',
            observation='Observed legacy problem',
            archived=True,
        )
        attachment = Attachment.objects.create(file='attachments/finding-legacy.txt')
        evidence = FindingEvidence.objects.create(
            finding=finding,
            result='NEU',
            valid_from=timezone.now() - timedelta(days=10),
            evaluator_id=user.pk,
            comment='Legacy finding evidence comment',
        )
        evidence.conformities.add(conformity)
        evidence.attachments.add(attachment)

        action = Action.objects.create(
            title='Legacy finding action',
            organization=organization,
            status='2',
        )
        action.associated_findings.add(finding)

        self.finding_description = finding.short_description
        self.conformity_pk = conformity.pk
        self.attachment_pk = attachment.pk
        self.action_pk = action.pk

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_finding_becomes_evidence_and_preserves_relations(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        apps = self.executor.loader.project_state(self.migrate_to).apps

        Finding = apps.get_model('conformity', 'Finding')
        Action = apps.get_model('conformity', 'Action')

        finding = Finding.objects.get(
            short_description=self.finding_description
        )
        self.assertEqual(finding.source_type, 'FIND')
        self.assertEqual(finding.status, 'EVAL')
        self.assertEqual(finding.result, 'NEG')
        self.assertIsNotNone(finding.valid_to)
        self.assertEqual(
            list(finding.conformities.values_list('pk', flat=True)),
            [self.conformity_pk],
        )
        self.assertEqual(
            list(finding.attachments.values_list('pk', flat=True)),
            [self.attachment_pk],
        )
        self.assertEqual(
            list(
                Action.objects.get(pk=self.action_pk)
                .associated_findings.values_list('pk', flat=True)
            ),
            [finding.pk],
        )

class ManualEvidenceToExpertMigrationTests(TransactionTestCase):
    migrate_from = [('conformity', '0080_finding_optional_audit')]
    migrate_to = [('conformity', '0081_simplify_evidence_types')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        apps = self.executor.loader.project_state(self.migrate_from).apps

        Framework = apps.get_model('conformity', 'Framework')
        Requirement = apps.get_model('conformity', 'Requirement')
        Organization = apps.get_model('conformity', 'Organization')
        Conformity = apps.get_model('conformity', 'Conformity')
        ManualEvidence = apps.get_model('conformity', 'ManualEvidence')
        Attachment = apps.get_model('conformity', 'Attachment')

        framework = Framework.objects.create(name='Manual conversion framework')
        requirement = Requirement.objects.create(
            framework=framework,
            code='MC1',
            name='MC1',
            level=0,
            tree_id=1,
            lft=1,
            rght=2,
        )
        organization = Organization.objects.create(name='Manual conversion org')
        conformity = Conformity.objects.create(
            organization=organization,
            requirement=requirement,
        )
        attachment = Attachment.objects.create(file='attachments/manual-conversion.txt')
        manual = ManualEvidence.objects.create(
            title='Legacy manual conclusion',
            result='NEU',
            status='EVAL',
            valid_from=timezone.now() - timedelta(days=2),
            comment='Legacy manual comment',
        )
        manual.conformities.add(conformity)
        manual.attachments.add(attachment)

        self.pk = manual.pk
        self.conformity_pk = conformity.pk
        self.attachment_pk = attachment.pk

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_manual_evidence_becomes_expert_assessment(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        apps = self.executor.loader.project_state(self.migrate_to).apps

        HumanEvidence = apps.get_model('conformity', 'HumanEvidence')

        expert = HumanEvidence.objects.get(pk=self.pk)
        self.assertEqual(expert.source_type, 'HUM')
        self.assertEqual(expert.decision, 'NEU')
        self.assertEqual(expert.result, 'NEU')
        self.assertEqual(expert.title, 'Legacy manual conclusion')
        self.assertEqual(expert.comment, 'Legacy manual comment')
        self.assertEqual(
            list(expert.conformities.values_list('pk', flat=True)),
            [self.conformity_pk],
        )
        self.assertEqual(
            list(expert.attachments.values_list('pk', flat=True)),
            [self.attachment_pk],
        )

