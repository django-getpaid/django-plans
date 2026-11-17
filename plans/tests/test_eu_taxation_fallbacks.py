from decimal import Decimal
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from requests.exceptions import ConnectionError

from plans.taxation.eu import EUTaxationPolicy


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

    def test_static_table_is_used_when_tedb_is_unreachable(self):
        with tedb_answering(side_effect=ConnectionError("TEDB down")):
            self.assertEqual(
                EUTaxationPolicy.get_tax_rate(None, "SK"), (Decimal("23"), True)
            )
            self.assertEqual(EUTaxationPolicy.get_default_tax(), Decimal("23"))

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
