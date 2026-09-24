from django.apps import AppConfig

class ConformityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "conformity"

    def ready(self):
        from . import signals  # noqa: F401
        from .audit import register_m2m_audit
        register_m2m_audit(self.get_models())
