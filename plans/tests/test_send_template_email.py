from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from model_bakery import baker

from plans.contrib import send_template_email

User = get_user_model()


class SendTemplateEmailTests(TestCase):
    def setUp(self):
        self.user = baker.make(User, username="customer", email="customer@example.com")
        baker.make("UserPlan", user=self.user, plan=baker.make("Plan", name="Pro"))

    def _send(self):
        send_template_email(
            [self.user.email],
            "mail/remind_expire_title.txt",
            "mail/remind_expire_body.txt",
            {"user": self.user, "userplan": self.user.userplan, "days": 3},
            None,
        )

    @override_settings(SITE_URL="plans.example.com")
    def test_links_use_the_site_url_setting(self):
        self._send()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            f"http://plans.example.com{reverse('current_plan')}", mail.outbox[0].body
        )

    def test_links_use_the_current_site_without_the_setting(self):
        Site.objects.filter(pk=Site.objects.get_current().pk).update(
            domain="site.example.com"
        )
        Site.objects.clear_cache()

        self._send()

        self.assertIn(
            f"http://site.example.com{reverse('current_plan')}", mail.outbox[0].body
        )
