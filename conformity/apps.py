from django.apps import AppConfig

class ConformityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "conformity"

    def ready(self):
        from . import signals  # noqa: F401
