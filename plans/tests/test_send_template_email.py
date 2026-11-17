from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from model_bakery import baker

from plans.contrib import send_template_email

User = get_user_model()

LOCMEM_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "title.txt": "{% load i18n %}{% trans 'Order' %}",
                        "body.txt": "{{ site_name }} {{ site_domain }}",
                        "body.html": "<p>{{ site_name }}</p>",
                    },
                )
            ]
        },
    }
]


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

    def test_nothing_is_sent_when_plans_e_mails_are_off(self):
        with override_settings(SEND_PLANS_EMAILS=False):
            self._send()

        self.assertEqual(mail.outbox, [])


@override_settings(TEMPLATES=LOCMEM_TEMPLATES, SITE_NAME="Plans shop")
class SendTemplateEmailRenderingTests(TestCase):
    def _send(self, language=None):
        send_template_email(
            ["customer@example.com"], "title.txt", "body.txt", {}, language
        )
        return mail.outbox[-1]

    def test_html_part_is_sent_when_its_template_exists(self):
        message = self._send()

        self.assertEqual(message.alternatives[0][0], "<p>example.com</p>")

    def test_title_is_rendered_in_the_given_language(self):
        message = self._send(language="pt-br")

        self.assertEqual(message.subject, "Pedido")
        self.assertEqual(translation.get_language(), "en")

    def test_without_the_sites_app_the_site_name_setting_is_used(self):
        with self.modify_settings(INSTALLED_APPS={"remove": "django.contrib.sites"}):
            message = self._send()

        self.assertTrue(message.body.startswith("Plans shop "))
