import inspect
import importlib
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class LogoutBehaviorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='logout-user', password='StrongPass123!')

    def test_logout_view_rejects_get_requests(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('logout'))

        self.assertEqual(response.status_code, 405)

    def test_logout_view_logs_user_out_on_post(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_main_template_uses_post_form_for_logout(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('conformity:home'))

        self.assertContains(response, 'form method="post" action="/accounts/logout/"')
        self.assertNotContains(response, 'href="/accounts/logout/"')


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