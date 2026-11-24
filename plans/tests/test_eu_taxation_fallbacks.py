from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from freezegun import freeze_time

from plans.taxation.eu import EUTaxationPolicy
from plans.taxation.tedb_client import TEDBClient
from plans.tests.test_tedb_client import start_tedb_stub


def tedb_answering(**kwargs):
    """Stand in for the TEDB web service, the policy's only network dependency."""
    return mock.patch.object(
        EUTaxationPolicy,
        "_get_tedb_client",
        return_value=mock.Mock(get_vat_rate=mock.Mock(**kwargs)),
    )


@override_settings(PLANS_TAX_COUNTRY="PL")
class EUTaxationFallbackTests(TestCase):
    def test_rate_comes_from_tedb_when_it_answers(self):
        with tedb_answering(return_value=Decimal("19.5")):
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "DE"), (Decimal("19.5"), True)
            )

    def test_static_table_is_used_when_tedb_has_no_rate(self):
        with tedb_answering(return_value=None):
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "DE"), (Decimal("19"), True)
            )

    def test_static_table_is_used_when_tedb_answers_http_504(self):
        """Blendkit #4556: the EU gateway's 504 raised requests.HTTPError."""
        for request in ("GET", "POST"):
            with (
                self.subTest(request),
                mock.patch.object(
                    TEDBClient,
                    "WSDL_URL",
                    start_tedb_stub(self, gateway_timeout=request),
                ),
                mock.patch.object(
                    EUTaxationPolicy, "_tedb_client", TEDBClient(), create=True
                ),
            ):
                cache.clear()
                self.assertEqual(
                    EUTaxationPolicy.get_tax_rate(None, "SK"), (Decimal("23"), True)
                )
                self.assertEqual(EUTaxationPolicy.get_default_tax(), Decimal("23"))

    def test_static_table_is_used_when_the_rate_lookup_returns_none(self):
        """``_get_vat_rate_from_tedb`` may return None; overrides and mocks do."""
        with mock.patch.object(
            EUTaxationPolicy, "_get_vat_rate_from_tedb", return_value=None
        ):
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "DE"), (Decimal("19"), True)
            )
            with mock.patch.object(
                EUTaxationPolicy, "validate_vies", return_value=False
            ):
                self.assertEqual(
                    EUTaxationPolicy.get_tax_rate("DE123456789", "DE"),
                    (Decimal("19"), True),
                )
            with mock.patch.object(
                EUTaxationPolicy, "validate_vies", side_effect=TimeoutError
            ):
                self.assertEqual(
                    EUTaxationPolicy.get_tax_rate("DE123456789", "DE"),
                    (Decimal("19"), False),
                )

    def test_lower_case_country_codes_are_taxed_like_upper_case_ones(self):
        with tedb_answering(return_value=None):
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "de"), (Decimal("19"), True)
            )
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "gr"), (Decimal("24"), True)
            )
            with mock.patch.object(
                EUTaxationPolicy, "validate_vies", side_effect=TimeoutError
            ):
                self.assertEqual(
                    EUTaxationPolicy.get_tax_rate("DE123456789", "de"),
                    (Decimal("19"), False),
                )
            with mock.patch.object(
                EUTaxationPolicy, "validate_vies", return_value=False
            ):
                self.assertEqual(
                    EUTaxationPolicy.get_tax_rate("DE123456789", "de"),
                    (Decimal("19"), True),
                )

    @override_settings(PLANS_TAX_COUNTRY="US")
    def test_issuer_outside_the_eu_is_a_configuration_error(self):
        with tedb_answering(return_value=None):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                "EUTaxationPolicy requires that issuer country is in EU",
            ):
                EUTaxationPolicy.get_default_tax()
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                "EUTaxationPolicy requires that issuer country is in EU",
            ):
                EUTaxationPolicy.get_tax_rate(None, "DE")


@override_settings(PLANS_TAX_COUNTRY="SK")
class EUTaxationDayTests(TestCase):
    """The rate is the one in force on the day the tax arises."""

    def test_static_rate_of_the_given_day(self):
        with tedb_answering(return_value=None):
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "FI", on=date(2024, 8, 31)),
                (Decimal("24"), True),
            )
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "FI", on=date(2024, 9, 1)),
                (Decimal("25.5"), True),
            )
            self.assertEqual(
                EUTaxationPolicy.get_default_tax(on=date(2024, 12, 31)), Decimal("20")
            )
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(
                    "SK2020202020", "SK", on=date(2025, 1, 1)
                ),
                (Decimal("23"), True),
            )
            with mock.patch.object(
                EUTaxationPolicy, "validate_vies", side_effect=TimeoutError
            ):
                self.assertEqual(
                    EUTaxationPolicy.get_tax_rate(
                        "RO123456789", "RO", on=date(2025, 7, 31)
                    ),
                    (Decimal("19"), False),
                )

    def test_tedb_is_asked_for_the_given_day(self):
        with tedb_answering(return_value=Decimal("26")) as client:
            EUTaxationPolicy.get_tax_rate(None, "FI", on=date(2027, 1, 1))

        client.return_value.get_vat_rate.assert_called_once_with("FI", date(2027, 1, 1))

    @freeze_time("2025-01-01 05:30:00")  # 2024-12-31 in Chicago (TIME_ZONE)
    def test_default_day_is_the_local_day(self):
        with tedb_answering(return_value=None) as client:
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "SK"), (Decimal("20"), True)
            )

        client.return_value.get_vat_rate.assert_called_once_with(
            "SK", date(2024, 12, 31)
        )
