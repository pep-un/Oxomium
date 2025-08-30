import inspect
import importlib
from django.test import TestCase
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin


class SecurityCoverageTests(TestCase):
    """
    Security coverage tests:
    - All CBV defined in `conformity.views` must be protected by an auth-related mixin.
    """

    ALLOW_PUBLIC_VIEWS = set()

    def test_all_cbv_have_auth_mixin(self):
        """
        Every class-based view (CBV) declared in `conformity.views` must inherit from
        one of: LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin.
        This catches accidental public exposure of internal views.
        """
        try:
            views_mod = importlib.import_module("conformity.views")
        except ModuleNotFoundError:
            self.skipTest("Module 'conformity.views' not found; adjust module path if your app is named differently.")

        from django.views import View

        protected_mixins = (LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin)
        missing = []

        for name, obj in inspect.getmembers(views_mod, inspect.isclass):
            # Only classes defined in this module (ignore imports)
            if obj.__module__ != views_mod.__name__:
                continue
            if not issubclass(obj, View):
                continue
            if name in self.ALLOW_PUBLIC_VIEWS:
                continue
            if not any(issubclass(obj, mixin) for mixin in protected_mixins):
                missing.append(name)

        self.assertFalse(
            missing,
            msg=(
                "The following CBV lack an auth/permission mixin "
                f"(LoginRequiredMixin/PermissionRequiredMixin/UserPassesTestMixin): {missing}"
            ),
        )