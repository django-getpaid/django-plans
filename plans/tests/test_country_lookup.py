from unittest import mock

from django.core.checks import run_checks
from django.test import RequestFactory, SimpleTestCase, override_settings

from plans.checks import check_country_lookup
from plans.utils import get_country_code

seen_requests = []


def fixed_country(request):
    seen_requests.append(request)
    return "DE"


class CountryLookupHookTests(SimpleTestCase):
    @override_settings(
        PLANS_GET_COUNTRY_CODE="plans.tests.test_country_lookup.fixed_country",
        PLANS_GET_COUNTRY_FROM_IP=True,
        PLANS_DEFAULT_COUNTRY="CZ",
    )
    def test_the_configured_lookup_replaces_the_built_in_one(self):
        request = RequestFactory().get("/")
        seen_requests.clear()

        self.assertEqual(get_country_code(request), "DE")
        self.assertEqual(seen_requests, [request])

    @override_settings(PLANS_GET_COUNTRY_FROM_IP=False, PLANS_DEFAULT_COUNTRY="CZ")
    def test_without_the_hook_the_default_country_applies(self):
        self.assertEqual(get_country_code(RequestFactory().get("/")), "CZ")


@mock.patch("plans.checks.find_spec", return_value=None)
class CountryLookupCheckTests(SimpleTestCase):
    @override_settings(PLANS_GET_COUNTRY_FROM_IP=True)
    def test_warns_when_the_ip_lookup_has_no_geolite2(self, find_spec):
        warnings = [w for w in run_checks() if w.id == "plans.W001"]
        self.assertEqual(len(warnings), 1)
        find_spec.assert_called_with("geolite2")

    @override_settings(
        PLANS_GET_COUNTRY_FROM_IP=True,
        PLANS_GET_COUNTRY_CODE="plans.tests.test_country_lookup.fixed_country",
    )
    def test_silent_with_a_configured_lookup(self, find_spec):
        self.assertEqual(check_country_lookup(None), [])

    @override_settings(PLANS_GET_COUNTRY_FROM_IP=False)
    def test_silent_when_the_ip_lookup_is_off(self, find_spec):
        self.assertEqual(check_country_lookup(None), [])

    @override_settings(PLANS_GET_COUNTRY_FROM_IP=True)
    def test_silent_when_geolite2_is_installed(self, find_spec):
        find_spec.return_value = object()
        self.assertEqual(check_country_lookup(None), [])
