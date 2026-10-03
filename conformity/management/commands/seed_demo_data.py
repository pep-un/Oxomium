from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from conformity.models import (
    Action,
    Audit,
    Conformity,
    Control,
    ControlPoint,
    Evidence,
    Finding,
    Framework,
    HumanEvidence,
    Indicator,
    IndicatorPoint,
    Organization,
    Requirement,
)
from conformity.services.conformities import set_frameworks


class Command(BaseCommand):
    help = "Create an idempotent demonstration dataset for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        owner = self._owner()
        frameworks = self._frameworks()
        requirements = self._requirements(frameworks)
        organizations = self._organizations(frameworks)
        conformities = self._conformities(organizations, requirements, owner)
        controls = self._controls(conformities)
        indicators = self._indicators(conformities, owner)
        audits, findings = self._audits_and_findings(
            organizations, frameworks
        )
        self._operational_evidence(
            controls, indicators, conformities, owner
        )
        self._other_evidence(findings, conformities, owner)
        self._actions(
            organizations, conformities, findings, controls, owner
        )

        self.stdout.write(self.style.SUCCESS(
            "Demo data ready: "
            f"{len(organizations)} organizations, "
            f"{len(frameworks)} frameworks, "
            f"{Control.objects.filter(title__startswith='Demo - ').count()} controls, "
            f"{Indicator.objects.filter(name__startswith='Demo - ').count()} indicators, "
            f"{len(audits)} audits and {len(findings)} findings."
        ))

    def _owner(self):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="demo-owner",
            defaults={"email": "demo-owner@example.invalid"},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user

    def _frameworks(self):
        security, _ = Framework.objects.update_or_create(
            name="Demo Security Baseline",
            defaults={
                "version": 1,
                "publish_by": "Oxomium Demo",
                "type": Framework.Type.POLICY,
                "language": "en",
            },
        )
        privacy, _ = Framework.objects.update_or_create(
            name="Demo Privacy Baseline",
            defaults={
                "version": 1,
                "publish_by": "Oxomium Demo",
                "type": Framework.Type.POLICY,
                "language": "en",
            },
        )
        return {"security": security, "privacy": privacy}

    def _requirement(self, framework, code, title, description, parent=None, order=1):
        requirement, _ = Requirement.objects.update_or_create(
            framework=framework,
            parent=parent,
            code=code,
            defaults={
                "title": title,
                "description": description,
                "order": order,
            },
        )
        return requirement

    def _requirements(self, frameworks):
        security = frameworks["security"]
        sec_root = self._requirement(
            security, "SEC", "Security baseline",
            "Demonstration security governance and operational controls."
        )
        sec_gov = self._requirement(
            security, "GOV", "Governance and access",
            "Governance, identity and accountability requirements.",
            sec_root, 1,
        )
        sec_iam = self._requirement(
            security, "IAM", "Privileged access review",
            "Privileged access is reviewed periodically and unnecessary access is removed.",
            sec_gov, 1,
        )
        sec_log = self._requirement(
            security, "LOG", "Security logging",
            "Security-relevant events are logged, retained and reviewed.",
            sec_gov, 2,
        )
        sec_ops = self._requirement(
            security, "OPS", "Security operations",
            "Operational resilience and vulnerability management requirements.",
            sec_root, 2,
        )
        sec_bkp = self._requirement(
            security, "BKP", "Backup and restoration",
            "Backups are protected and restoration procedures are tested.",
            sec_ops, 1,
        )
        sec_vul = self._requirement(
            security, "VUL", "Vulnerability management",
            "Vulnerabilities are identified, prioritized and remediated.",
            sec_ops, 2,
        )

        privacy = frameworks["privacy"]
        prv_root = self._requirement(
            privacy, "PRV", "Privacy baseline",
            "Demonstration privacy governance and data-subject requirements."
        )
        prv_data = self._requirement(
            privacy, "DATA", "Data governance",
            "Personal-data inventories and retention requirements.",
            prv_root, 1,
        )
        prv_inv = self._requirement(
            privacy, "INV", "Processing inventory",
            "Processing activities and data categories are inventoried.",
            prv_data, 1,
        )
        prv_ret = self._requirement(
            privacy, "RET", "Retention",
            "Personal data is retained only for approved periods.",
            prv_data, 2,
        )
        prv_right = self._requirement(
            privacy, "RGHT", "Data-subject rights",
            "Operational handling of data-subject requests and incidents.",
            prv_root, 2,
        )
        prv_dsr = self._requirement(
            privacy, "DSR", "Data-subject requests",
            "Requests are authenticated, tracked and completed within target times.",
            prv_right, 1,
        )
        prv_brch = self._requirement(
            privacy, "BRCH", "Privacy incidents",
            "Privacy incidents are assessed and escalated promptly.",
            prv_right, 2,
        )

        return {
            "sec_iam": sec_iam,
            "sec_log": sec_log,
            "sec_bkp": sec_bkp,
            "sec_vul": sec_vul,
            "prv_inv": prv_inv,
            "prv_ret": prv_ret,
            "prv_dsr": prv_dsr,
            "prv_brch": prv_brch,
        }

    def _organizations(self, frameworks):
        acme, _ = Organization.objects.update_or_create(
            name="Acme Manufacturing",
            defaults={
                "administrative_id": "DEMO-ACME",
                "description": (
                    "Industrial organization used to demonstrate a combined "
                    "security and privacy compliance scope."
                ),
            },
        )
        northstar, _ = Organization.objects.update_or_create(
            name="Northstar Services",
            defaults={
                "administrative_id": "DEMO-NORTH",
                "description": (
                    "Managed-services organization used to demonstrate a "
                    "security-only compliance scope."
                ),
            },
        )
        contoso, _ = Organization.objects.update_or_create(
            name="Contoso Research",
            defaults={
                "administrative_id": "DEMO-CONTOSO",
                "description": (
                    "Research organization used to demonstrate a privacy-focused "
                    "compliance scope."
                ),
            },
        )

        set_frameworks(acme, [frameworks["security"], frameworks["privacy"]])
        set_frameworks(northstar, [frameworks["security"]])
        set_frameworks(contoso, [frameworks["privacy"]])

        return {
            "acme": acme,
            "northstar": northstar,
            "contoso": contoso,
        }

    def _conformities(self, organizations, requirements, owner):
        result = {}
        for org_key, org in organizations.items():
            for req_key, requirement in requirements.items():
                if not org.applicable_frameworks.filter(
                    pk=requirement.framework_id
                ).exists():
                    continue
                conformity = Conformity.objects.get(
                    organization=org,
                    requirement=requirement,
                )
                if conformity.responsible_id != owner.pk:
                    conformity.responsible = owner
                    conformity.save(update_fields=["responsible"])
                result[f"{org_key}_{req_key}"] = conformity
        return result

    def _upsert_control(self, title, description, frequency, level, targets):
        control = Control.objects.filter(title=title).first()
        if control is None:
            control = Control.objects.create(
                title=title,
                description=description,
                frequency=frequency,
                level=level,
            )
        else:
            control.description = description
            control.frequency = frequency
            control.level = level
            control.save()
        control.conformity.set(targets)
        return control

    def _controls(self, conformities):
        return {
            "access": self._upsert_control(
                "Demo - Quarterly privileged access review",
                "Review privileged accounts, owners and current business justification.",
                Control.Frequency.QUARTERLY,
                Control.Level.FIRST,
                [
                    conformities["acme_sec_iam"],
                    conformities["northstar_sec_iam"],
                ],
            ),
            "backup": self._upsert_control(
                "Demo - Backup restoration test",
                "Restore a representative backup and document recovery results.",
                Control.Frequency.HALFYEARLY,
                Control.Level.SECOND,
                [conformities["acme_sec_bkp"]],
            ),
            "vulnerability": self._upsert_control(
                "Demo - Vulnerability remediation review",
                "Review open vulnerabilities against remediation targets.",
                Control.Frequency.MONTHLY,
                Control.Level.FIRST,
                [
                    conformities["acme_sec_vul"],
                    conformities["northstar_sec_vul"],
                ],
            ),
            "logging": self._upsert_control(
                "Demo - Security log review",
                "Verify collection and review of authentication and administrative events.",
                Control.Frequency.MONTHLY,
                Control.Level.FIRST,
                [conformities["acme_sec_log"]],
            ),
        }

    def _upsert_indicator(
        self, name, goal, source, formula, worst, critical, warning, best,
        frequency, responsible, targets
    ):
        indicator = Indicator.objects.filter(name=name).first()
        values = {
            "goal": goal,
            "source": source,
            "formula": formula,
            "worst": worst,
            "critical": critical,
            "warning": warning,
            "best": best,
            "frequency": frequency,
            "responsible": responsible,
        }
        if indicator is None:
            indicator = Indicator.objects.create(name=name, **values)
        else:
            for field, value in values.items():
                setattr(indicator, field, value)
            indicator.save()
        indicator.conformity.set(targets)
        return indicator

    def _indicators(self, conformities, owner):
        return {
            "patch": self._upsert_indicator(
                "Demo - Patch SLA compliance",
                "Keep remediation within the approved vulnerability SLA.",
                "Vulnerability management platform",
                "Closed within SLA / total closed vulnerabilities × 100",
                0, 20, 80, 100,
                Indicator.Frequency.MONTHLY,
                owner,
                [conformities["acme_sec_vul"]],
            ),
            "backup": self._upsert_indicator(
                "Demo - Successful backup jobs",
                "Maintain a high successful-backup ratio.",
                "Backup platform",
                "Successful jobs / total jobs × 100",
                0, 50, 90, 100,
                Indicator.Frequency.MONTHLY,
                owner,
                [conformities["acme_sec_bkp"]],
            ),
            "dsr": self._upsert_indicator(
                "Demo - Data-subject request completion time",
                "Reduce the average number of days needed to complete requests.",
                "Privacy case-management system",
                "Average calendar days from validated request to completion",
                60, 45, 30, 5,
                Indicator.Frequency.QUARTERLY,
                owner,
                [conformities["contoso_prv_dsr"]],
            ),
        }

    def _upsert_audit(self, organization, name, auditor, days_ago):
        audit = Audit.objects.filter(
            organization=organization, name=name
        ).first()
        values = {
            "auditor": auditor,
            "description": "Demonstration audit generated by seed_demo_data.",
            "conclusion": "Sample conclusion for UI and workflow testing.",
            "report_date": timezone.localdate() - timedelta(days=days_ago),
            "type": Audit.Type.INTERNAL,
        }
        if audit is None:
            audit = Audit.objects.create(
                organization=organization, name=name, **values
            )
        else:
            for field, value in values.items():
                setattr(audit, field, value)
            audit.save()
        return audit

    def _upsert_finding(self, audit, short_description, severity, description):
        finding = Finding.objects.filter(
            audit=audit, short_description=short_description
        ).first()
        values = {
            "severity": severity,
            "description": description,
            "observation": description,
            "recommendation": "Track remediation through an associated action.",
            "reference": "DEMO",
        }
        if finding is None:
            finding = Finding.objects.create(
                audit=audit,
                short_description=short_description,
                **values,
            )
        else:
            for field, value in values.items():
                setattr(finding, field, value)
            finding.save()
        return finding

    def _audits_and_findings(self, organizations, frameworks):
        acme_audit = self._upsert_audit(
            organizations["acme"],
            "Demo - Security internal audit",
            "Internal Assurance Team",
            45,
        )
        acme_audit.audited_frameworks.set([frameworks["security"]])

        privacy_audit = self._upsert_audit(
            organizations["contoso"],
            "Demo - Privacy operations review",
            "Privacy Assurance Team",
            20,
        )
        privacy_audit.audited_frameworks.set([frameworks["privacy"]])

        findings = {
            "access": self._upsert_finding(
                acme_audit,
                "Dormant privileged accounts remain enabled",
                Finding.Severity.MAJOR,
                "Several privileged accounts had no recent business justification.",
            ),
            "backup": self._upsert_finding(
                acme_audit,
                "Restore test exceeded recovery target",
                Finding.Severity.MINOR,
                "The sampled restoration completed after the internal recovery target.",
            ),
            "positive": self._upsert_finding(
                acme_audit,
                "Security logging coverage improved",
                Finding.Severity.POSITIVE,
                "Authentication and administrative logs are centrally collected.",
            ),
            "dsr": self._upsert_finding(
                privacy_audit,
                "Request handling is not consistently tracked",
                Finding.Severity.OBSERVATION,
                "Some privacy requests are tracked outside the central workflow.",
            ),
            "retention": self._upsert_finding(
                privacy_audit,
                "Retention exceptions lack expiry dates",
                Finding.Severity.MINOR,
                "Approved retention exceptions should include explicit expiry dates.",
            ),
        }
        return [acme_audit, privacy_audit], findings

    def _operational_evidence(self, controls, indicators, conformities, owner):
        now = timezone.now()

        control_results = {
            "access": (
                Evidence.Result.POSITIVE,
                "Sampled privileged accounts were reviewed.",
            ),
            "backup": (
                Evidence.Result.NEGATIVE,
                "Restoration completed outside the target recovery time.",
            ),
            "logging": (
                Evidence.Result.POSITIVE,
                "Expected authentication and admin event sources were present.",
            ),
        }
        for key, (result, comment) in control_results.items():
            point = ControlPoint.objects.filter(
                control=controls[key],
                valid_from__lte=now,
                valid_to__gt=now,
            ).first()
            if point is not None:
                point.result = result
                point.evaluator = owner
                point.evaluated_at = now
                point.comment = comment
                point.save()

        indicator_values = {
            "patch": 72,
            "backup": 96,
            "dsr": 50,
        }
        for key, value in indicator_values.items():
            point = IndicatorPoint.objects.filter(
                indicator=indicators[key],
                valid_from__lte=now,
                valid_to__gt=now,
            ).first()
            if point is not None:
                point.value = value
                point.comment = "Demonstration measurement."
                point.save()

    def _upsert_expert_assessment(
        self, title, conformity, result, comment, owner
    ):
        evidence = HumanEvidence.objects.filter(title=title).first()
        if evidence is None:
            evidence = HumanEvidence(
                title=title,
                decision=result,
                status=Evidence.Status.EVALUATED,
                valid_from=timezone.now() - timedelta(days=5),
                evaluator=owner,
                evaluated_at=timezone.now() - timedelta(days=5),
                comment=comment,
            )
        else:
            evidence.decision = result
            evidence.result = result
            evidence.comment = comment
            evidence.evaluator = owner
            evidence.status = Evidence.Status.EVALUATED
        evidence.save()
        evidence.conformities.set([conformity])
        return evidence

    def _other_evidence(self, findings, conformities, owner):
        self._upsert_expert_assessment(
            "Demo - Access governance procedure reviewed",
            conformities["acme_sec_iam"],
            Evidence.Result.POSITIVE,
            "Current access-governance procedure reviewed by the control owner.",
            owner,
        )

        self._upsert_expert_assessment(
            "Demo - Logging coverage confirmed",
            conformities["acme_sec_log"],
            Evidence.Result.POSITIVE,
            "Logging inventory confirms coverage of required systems.",
            owner,
        )
        self._upsert_expert_assessment(
            "Demo - Logging retention gap",
            conformities["acme_sec_log"],
            Evidence.Result.NEGATIVE,
            "One log source is retained for less than the target period.",
            owner,
        )

        human = HumanEvidence.objects.filter(
            comment="Demo arbitration - logging is partially compliant."
        ).first()
        if human is None:
            human = HumanEvidence(
                decision=HumanEvidence.Decision.PARTIAL,
                valid_from=timezone.now() - timedelta(days=1),
                evaluator=owner,
                evaluated_at=timezone.now() - timedelta(days=1),
                comment="Demo arbitration - logging is partially compliant.",
            )
        else:
            human.decision = HumanEvidence.Decision.PARTIAL
            human.result = Evidence.Result.PARTIAL
        human.save()
        human.conformities.set([conformities["acme_sec_log"]])

        finding_targets = {
            "access": conformities["acme_sec_iam"],
            "backup": conformities["acme_sec_bkp"],
            "dsr": conformities["contoso_prv_dsr"],
            "retention": conformities["contoso_prv_ret"],
        }
        for key, conformity in finding_targets.items():
            finding = findings[key]
            finding.comment = finding.observation or finding.description
            finding.evaluator = owner
            finding.evaluated_at = finding.evaluated_at or timezone.now()
            finding.save()
            finding.conformities.set([conformity])

    def _upsert_action(
        self, organization, title, status, priority, description, owner,
        conformities=(), findings=(), control_points=()
    ):
        action = Action.objects.filter(
            organization=organization, title=title
        ).first()
        values = {
            "status": status,
            "priority": priority,
            "description": description,
            "owner": owner,
            "status_comment": "Demonstration action generated by seed_demo_data.",
        }
        if action is None:
            action = Action.objects.create(
                organization=organization, title=title, **values
            )
        else:
            for field, value in values.items():
                setattr(action, field, value)
            action.save()
        action.associated_conformity.set(conformities)
        action.associated_findings.set(findings)
        action.associated_controlPoints.set(control_points)
        return action

    def _actions(self, organizations, conformities, findings, controls, owner):
        now = timezone.now()
        backup_point = ControlPoint.objects.filter(
            control=controls["backup"],
            valid_from__lte=now,
            valid_to__gt=now,
        ).first()

        self._upsert_action(
            organizations["acme"],
            "Demo - Improve backup restore reliability",
            Action.Status.IMPLEMENTING,
            Action.Priority.PRIORITY_1,
            "Tune the restore procedure and repeat the recovery exercise.",
            owner,
            conformities=[conformities["acme_sec_bkp"]],
            findings=[findings["backup"]],
            control_points=[backup_point] if backup_point else [],
        )
        self._upsert_action(
            organizations["acme"],
            "Demo - Close privileged access gaps",
            Action.Status.PLANNING,
            Action.Priority.PRIORITY_2,
            "Remove dormant privileged accounts and document access owners.",
            owner,
            conformities=[conformities["acme_sec_iam"]],
            findings=[findings["access"]],
        )
        self._upsert_action(
            organizations["contoso"],
            "Demo - Centralize privacy request tracking",
            Action.Status.CONTROLLING,
            Action.Priority.PRIORITY_3,
            "Move all data-subject requests into the central privacy workflow.",
            owner,
            conformities=[conformities["contoso_prv_dsr"]],
            findings=[findings["dsr"]],
        )
