from django.core.management import call_command
from django.test import TestCase

from conformity.models import (
    Action,
    Audit,
    Control,
    ControlPoint,
    Finding,
    FindingEvidence,
    Framework,
    HumanEvidence,
    Indicator,
    IndicatorPoint,
    ManualEvidence,
    Organization,
)


class SeedDemoDataCommandTests(TestCase):
    def test_seed_demo_data_builds_connected_dataset_and_is_idempotent(self):
        call_command("seed_demo_data", verbosity=0)
        call_command("seed_demo_data", verbosity=0)

        self.assertEqual(
            Framework.objects.filter(name__startswith="Demo ").count(),
            2,
        )
        self.assertEqual(
            Organization.objects.filter(
                name__in=[
                    "Acme Manufacturing",
                    "Northstar Services",
                    "Contoso Research",
                ]
            ).count(),
            3,
        )

        acme = Organization.objects.get(name="Acme Manufacturing")
        northstar = Organization.objects.get(name="Northstar Services")
        contoso = Organization.objects.get(name="Contoso Research")
        self.assertEqual(acme.applicable_frameworks.count(), 2)
        self.assertEqual(northstar.applicable_frameworks.count(), 1)
        self.assertEqual(contoso.applicable_frameworks.count(), 1)

        self.assertEqual(
            Control.objects.filter(title__startswith="Demo - ").count(),
            4,
        )
        self.assertEqual(
            Indicator.objects.filter(name__startswith="Demo - ").count(),
            3,
        )
        self.assertEqual(
            Audit.objects.filter(name__startswith="Demo - ").count(),
            2,
        )
        self.assertEqual(Finding.objects.filter(reference="DEMO").count(), 5)
        self.assertEqual(
            Action.objects.filter(title__startswith="Demo - ").count(),
            3,
        )

        self.assertGreater(
            ControlPoint.objects.filter(
                control__title__startswith="Demo - "
            ).count(),
            0,
        )
        self.assertEqual(
            IndicatorPoint.objects.filter(
                indicator__name__startswith="Demo - ",
                value__isnull=False,
            ).count(),
            3,
        )

        self.assertEqual(
            ManualEvidence.objects.filter(title__startswith="Demo - ").count(),
            3,
        )
        self.assertEqual(
            HumanEvidence.objects.filter(
                comment="Demo arbitration - logging is partially compliant."
            ).count(),
            1,
        )
        self.assertEqual(
            FindingEvidence.objects.filter(
                finding__reference="DEMO"
            ).count(),
            4,
        )
