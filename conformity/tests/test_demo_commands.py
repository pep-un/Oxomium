import os
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.conf import settings
from django.test import TestCase, override_settings
from conformity.models import Action, Audit, Framework, Indicator, Organization

class SeedDemoCommandTests(TestCase):
    @patch.dict(os.environ, {"DEMO_PASSWORD": "demo-test-password"}, clear=False)
    def test_seed_demo_creates_representative_dataset(self):
        call_command("seed_demo", verbosity=0)
        self.assertTrue(get_user_model().objects.filter(username="demo").exists())
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(Framework.objects.count(), 1)
        self.assertEqual(Audit.objects.count(), 1)
        self.assertEqual(Action.objects.count(), 1)
        self.assertEqual(Indicator.objects.count(), 1)

    @patch.dict(os.environ, {"DEMO_PASSWORD": "demo-test-password"}, clear=False)
    def test_seed_demo_refuses_non_empty_database(self):
        Organization.objects.create(name="Existing")
        with self.assertRaisesMessage(CommandError, "non-empty database"):
            call_command("seed_demo", verbosity=0)

    def test_seed_demo_requires_password(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(CommandError, "DEMO_PASSWORD"):
                call_command("seed_demo", verbosity=0)

class ResetDemoSafetyTests(TestCase):
    def test_reset_demo_requires_explicit_demo_flag(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(CommandError, "OXOMIUM_DEMO_INSTANCE"):
                call_command("reset_demo", verbosity=0)

    @patch.dict(os.environ, {"OXOMIUM_DEMO_INSTANCE": "true", "DEMO_PASSWORD": "demo-test-password"}, clear=False)
    def test_reset_demo_refuses_default_database(self):
        database = settings.DATABASES["default"].copy()
        database["NAME"] = settings.BASE_DIR / "db.sqlite3"
        with override_settings(DATABASES={"default": database}):
            with self.assertRaisesMessage(CommandError, "default development database"):
                call_command("reset_demo", verbosity=0)
