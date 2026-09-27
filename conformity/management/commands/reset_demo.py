"""Reset a dedicated demo SQLite database and recreate demo data."""
import os
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

class Command(BaseCommand):
    help = "Delete the SQLite demo database, migrate it, and recreate demo data."
    def handle(self, *args, **options):
        if os.environ.get("OXOMIUM_DEMO_INSTANCE") != "true":
            raise CommandError("Refusing to reset data unless OXOMIUM_DEMO_INSTANCE=true.")
        database=settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("reset_demo currently supports SQLite only.")
        db_path=Path(database["NAME"]).resolve()
        if db_path == Path(settings.BASE_DIR).resolve() / "db.sqlite3":
            raise CommandError("Refusing to delete the default development database.")
        connections.close_all()
        if db_path.exists(): db_path.unlink()
        call_command("migrate", interactive=False, verbosity=options["verbosity"])
        call_command("seed_demo", verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS("Demo database reset completed."))
