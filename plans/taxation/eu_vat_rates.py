"""Standard VAT rates of the EU member states over time.

The static fallback for TEDB (``plans.taxation.tedb_client``): it is used
whenever TEDB does not answer, so a rate change has to be added here, with
the day it comes into force, before that day. ``differences_from_tedb``
compares the table with TEDB; run it for ``TEDB_CHECK_OFFSETS`` days ahead
(see ``plans.tests.test_eu_vat_rates``) to learn about changes TEDB
already lists.
"""

from bisect import bisect_right
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from plans.taxation.tedb_client import TEDBClient, retrieve_standard_rates

HISTORY_START = date(2023, 1, 1)

# Country code (VIES, so Greece is EL) -> (day the rate came into force, rate),
# oldest first. A first entry dated HISTORY_START was in force earlier as well.
# Checked against TEDB (retrieveVatRates situationOn) on 2026-11-24.
EU_STANDARD_VAT_RATES = {
    "AT": ((HISTORY_START, Decimal("20")),),
    "BE": ((HISTORY_START, Decimal("21")),),
    "BG": ((HISTORY_START, Decimal("20")),),
    "CY": ((HISTORY_START, Decimal("19")),),
    "CZ": ((HISTORY_START, Decimal("21")),),
    "DE": ((HISTORY_START, Decimal("19")),),
    "DK": ((HISTORY_START, Decimal("25")),),
    "EE": (
        (HISTORY_START, Decimal("20")),
        (date(2024, 1, 1), Decimal("22")),
        (date(2025, 7, 1), Decimal("24")),
    ),
    "EL": ((HISTORY_START, Decimal("24")),),
    "ES": ((HISTORY_START, Decimal("21")),),
    "FI": (
        (HISTORY_START, Decimal("24")),
        (date(2024, 9, 1), Decimal("25.5")),
    ),
    "FR": ((HISTORY_START, Decimal("20")),),
    "HR": ((HISTORY_START, Decimal("25")),),
    "HU": ((HISTORY_START, Decimal("27")),),
    "IE": ((HISTORY_START, Decimal("23")),),
    "IT": ((HISTORY_START, Decimal("22")),),
    "LT": ((HISTORY_START, Decimal("21")),),
    "LU": (
        (HISTORY_START, Decimal("16")),
        (date(2024, 1, 1), Decimal("17")),
    ),
    "LV": ((HISTORY_START, Decimal("21")),),
    "MT": ((HISTORY_START, Decimal("18")),),
    "NL": ((HISTORY_START, Decimal("21")),),
    "PL": ((HISTORY_START, Decimal("23")),),
    "PT": ((HISTORY_START, Decimal("23")),),
    "RO": (
        (HISTORY_START, Decimal("19")),
        (date(2025, 8, 1), Decimal("21")),
    ),
    "SE": ((HISTORY_START, Decimal("25")),),
    "SI": ((HISTORY_START, Decimal("22")),),
    "SK": (
        (HISTORY_START, Decimal("20")),
        (date(2025, 1, 1), Decimal("23")),
    ),
}

# Days ahead of today that a check against TEDB covers: tomorrow's switch,
# and changes announced a week, a month and a year ahead.
TEDB_CHECK_OFFSETS = tuple(timedelta(days=days) for days in (0, 1, 7, 30, 365))


def latest_standard_vat_rates() -> dict[str, Decimal]:
    """Country code -> the newest rate in the table (in force today, or from a
    future day once a change is added)."""
    return {code: rates[-1][1] for code, rates in EU_STANDARD_VAT_RATES.items()}


def standard_vat_rate(country_code: str, on: date) -> Decimal:
    """Standard VAT rate of ``country_code`` in force on ``on``."""
    rates = EU_STANDARD_VAT_RATES[country_code]
    index = bisect_right(rates, on, key=lambda entry: entry[0])
    if index == 0:
        raise ValueError(
            f"No VAT rate of {country_code} is known before {rates[0][0]} (asked for {on})."
        )
    return rates[index - 1][1]


def differences_from_tedb(days: Iterable[date]) -> list[str]:
    """Where the table disagrees with TEDB's standard rate on each of ``days``.

    One line per country and day, e.g. ``FI on 2027-01-01: table 25.5 %,
    TEDB 26 % (valid from 2027-01-01)``. Raises ``TEDB_ERRORS`` when TEDB
    does not answer.
    """
    soap_client = TEDBClient.create_soap_client()
    differences = []
    for day in days:
        tedb_rates = retrieve_standard_rates(soap_client, EU_STANDARD_VAT_RATES, day)
        for code, tedb in tedb_rates.items():
            table_rate = standard_vat_rate(code, day)
            if tedb is None:
                differences.append(
                    f"{code} on {day}: table {table_rate} %, TEDB has no standard rate"
                )
            elif tedb.rate != table_rate:
                differences.append(
                    f"{code} on {day}: table {table_rate} %, TEDB {tedb.rate} % "
                    f"(valid from {tedb.valid_from})"
                )
    return differences
