from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from django.utils.timezone import localdate

from plans.taxation.eu import EUTaxationPolicy
from plans.taxation.eu_vat_rates import (
    EU_STANDARD_VAT_RATES,
    HISTORY_START,
    TEDB_CHECK_OFFSETS,
    differences_from_tedb,
    standard_vat_rate,
)
from plans.taxation.tedb_client import TEDB_ERRORS, TEDBClient
from plans.tests.test_tedb_client import vat_row


class StandardVatRateTests(SimpleTestCase):
    def test_rate_in_force_on_the_day(self):
        cases = [
            ("FI", date(2024, 8, 31), Decimal("24")),
            ("FI", date(2024, 9, 1), Decimal("25.5")),
            ("SK", date(2024, 12, 31), Decimal("20")),
            ("SK", date(2025, 1, 1), Decimal("23")),
            ("EE", date(2023, 12, 31), Decimal("20")),
            ("EE", date(2024, 1, 1), Decimal("22")),
            ("EE", date(2025, 6, 30), Decimal("22")),
            ("EE", date(2025, 7, 1), Decimal("24")),
            ("RO", date(2025, 7, 31), Decimal("19")),
            ("RO", date(2025, 8, 1), Decimal("21")),
            ("LU", date(2023, 12, 31), Decimal("16")),
            ("LU", date(2024, 1, 1), Decimal("17")),
            ("DE", HISTORY_START, Decimal("19")),
            ("DE", date(2030, 1, 1), Decimal("19")),
        ]
        for country, day, rate in cases:
            with self.subTest(country=country, day=day):
                self.assertEqual(standard_vat_rate(country, day), rate)

    def test_day_before_the_history_is_an_error(self):
        with self.assertRaisesMessage(
            ValueError, "No VAT rate of DE is known before 2023-01-01"
        ):
            standard_vat_rate("DE", date(2022, 12, 31))

    def test_unknown_country_is_an_error(self):
        with self.assertRaises(KeyError):
            standard_vat_rate("GB", date(2025, 1, 1))

    def test_history_is_ordered_and_starts_together(self):
        for country, rates in EU_STANDARD_VAT_RATES.items():
            with self.subTest(country):
                days = [day for day, _ in rates]
                self.assertEqual(days[0], HISTORY_START)
                self.assertEqual(days, sorted(set(days)))

    def test_current_rates_mapping_is_the_latest_entry(self):
        self.assertEqual(
            EUTaxationPolicy.EU_COUNTRIES_VAT,
            {code: rates[-1][1] for code, rates in EU_STANDARD_VAT_RATES.items()},
        )
        self.assertEqual(len(EUTaxationPolicy.EU_COUNTRIES_VAT), 27)


def tedb_answering_for_all(rows_for_day):
    """TEDB answering ``rows_for_day(day)`` plus the table's rate for every other state."""

    def retrieve(**request):
        day = request["situationOn"]
        rows = rows_for_day(day)
        answered = {row.memberState for row in rows}
        rows += [
            vat_row(code, float(standard_vat_rate(code, day)))
            for code in request["memberStates"]["isoCode"]
            if code not in answered
        ]
        return SimpleNamespace(vatRateResults=rows)

    soap = mock.Mock()
    soap.service.retrieveVatRates.side_effect = retrieve
    return mock.patch.object(TEDBClient, "create_soap_client", return_value=soap)


class DifferencesFromTedbTests(SimpleTestCase):
    def test_no_differences_when_tedb_agrees(self):
        with tedb_answering_for_all(lambda day: []):
            self.assertEqual(
                differences_from_tedb([date(2024, 9, 1), date(2025, 8, 1)]), []
            )

    def test_reports_a_rate_the_table_does_not_know(self):
        def finland_raises_in_2027(day):
            if day >= date(2027, 1, 1):
                return [vat_row("FI", 26, situation_on=date(2027, 1, 1))]
            return []

        with tedb_answering_for_all(finland_raises_in_2027):
            differences = differences_from_tedb([date(2026, 12, 31), date(2027, 1, 1)])

        self.assertEqual(
            differences,
            ["FI on 2027-01-01: table 25.5 %, TEDB 26 % (valid from 2027-01-01)"],
        )

    def test_reports_a_state_without_standard_rate(self):
        with tedb_answering_for_all(
            lambda day: [vat_row("MT", 7, type="REDUCED", rate_type="REDUCED_RATE")]
        ):
            differences = differences_from_tedb([date(2025, 1, 1)])

        self.assertEqual(
            differences, ["MT on 2025-01-01: table 18 %, TEDB has no standard rate"]
        )

    def test_tedb_errors_are_raised(self):
        with mock.patch.object(
            TEDBClient, "create_soap_client", side_effect=TEDB_ERRORS[0]("down")
        ):
            with self.assertRaises(TEDB_ERRORS):
                differences_from_tedb([date(2025, 1, 1)])


class LiveTedbTests(SimpleTestCase):
    def test_table_matches_tedb_today_and_ahead(self):
        """Fails when TEDB lists a rate change the table lacks; skipped while TEDB is down."""
        today = localdate()
        try:
            differences = differences_from_tedb(
                [today + offset for offset in TEDB_CHECK_OFFSETS]
            )
        except TEDB_ERRORS as e:
            self.skipTest(f"TEDB did not answer: {e!r}")

        self.assertEqual(
            differences,
            [],
            "Add the changes to plans/taxation/eu_vat_rates.py:\n"
            + "\n".join(differences),
        )
