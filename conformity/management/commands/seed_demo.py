"""Create a deterministic demonstration dataset for Oxomium."""

import os
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from conformity.models import Action, Audit, Conformity, Control, Finding, Framework, Indicator, IndicatorPoint, Organization, Requirement

class Command(BaseCommand):
    help = "Create the deterministic Oxomium demonstration dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        if Organization.objects.exists() or Framework.objects.exists():
            raise CommandError("Refusing to seed a non-empty database.")
        username = os.environ.get("DEMO_USERNAME", "demo")
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("DEMO_PASSWORD must be set.")
        user = get_user_model().objects.create_user(username=username, password=password, email="demo@example.invalid")
        framework = Framework.objects.create(name="Oxomium Demo Security Framework", version=1, publish_by="Oxomium", type=Framework.Type.OTHER, language="en")
        root = Requirement.objects.create(framework=framework, code="SEC", name="demo-security", title="Security management")
        requirements = [
            Requirement.objects.create(framework=framework, parent=root, code="IAM", name="demo-iam", title="Identity and access management", description="Control privileged and user access."),
            Requirement.objects.create(framework=framework, parent=root, code="VULN", name="demo-vulnerability", title="Vulnerability management", description="Identify and remediate vulnerabilities."),
            Requirement.objects.create(framework=framework, parent=root, code="BCP", name="demo-continuity", title="Business continuity", description="Maintain tested recovery capabilities."),
        ]
        organization = Organization.objects.create(name="Acme Demo Corporation", administrative_id="DEMO-001", description="Fictitious organization used to demonstrate Oxomium.")
        organization.applicable_frameworks.add(framework)
        conformities = []
        for requirement, status in zip(requirements, (85, 55, 30)):
            conformities.append(Conformity.objects.create(organization=organization, requirement=requirement, status=status, status_last_update=timezone.now(), comment="Demonstration assessment generated automatically."))
        audit = Audit.objects.create(name="Annual security review", organization=organization, auditor="Demo Internal Audit", type=Audit.Type.INTERNAL, start_date=date.today()-timedelta(days=45), end_date=date.today()-timedelta(days=40), report_date=date.today()-timedelta(days=35), conclusion="Demo audit showing representative findings and remediation.")
        audit.audited_frameworks.add(framework)
        finding = Finding.objects.create(short_description="Privileged access review is incomplete", description="A sample major finding for the demonstration environment.", recommendation="Complete and document the quarterly privileged access review.", audit=audit, severity=Finding.Severity.MAJOR)
        action = Action.objects.create(title="Complete privileged access review", owner=user, organization=organization, status=Action.Status.IMPLEMENTING, priority=Action.Priority.PRIORITY_1, description="Demo remediation action linked to the audit finding.", plan_start_date=date.today()-timedelta(days=20), plan_end_date=date.today()+timedelta(days=20), implement_status=60)
        action.associated_findings.add(finding); action.associated_conformity.add(conformities[0])
        control = Control.objects.create(title="Quarterly privileged access review", description="Review privileged accounts and their business justification.", organization=organization, frequency=Control.Frequency.QUARTERLY, level=Control.Level.FIRST)
        control.conformity.add(conformities[0]); Control.controlpoint_bootstrap(control)
        indicator = Indicator.objects.create(name="Security remediation completion", goal="Track completion of security remediation work.", source="Demo security programme", formula="Completed remediation actions / total remediation actions", worst=0, critical=40, warning=75, best=100, responsible=user, organization=organization, frequency=Indicator.Frequency.QUARTERLY)
        today=date.today()
        IndicatorPoint.objects.create(indicator=indicator, period_start_date=today.replace(day=1), period_end_date=today, control_date=timezone.now(), control_user=user, value=82, comment="Representative demo measurement.")
        self.stdout.write(self.style.SUCCESS(f"Demo dataset created for user '{username}'."))
