from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from plans.importer import import_name


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_country_code(request):
    if getattr(settings, "PLANS_GET_COUNTRY_FROM_IP", False):
        try:
            from geolite2 import geolite2

            reader = geolite2.reader()
            ip_address = get_client_ip(request)
            ip_info = reader.get(ip_address)
        except ModuleNotFoundError:
            ip_info = None

        if ip_info and "country" in ip_info:
            country_code = ip_info["country"]["iso_code"]
            return country_code
    return getattr(settings, "PLANS_DEFAULT_COUNTRY", None)


def get_currency():
    CURRENCY = getattr(settings, "PLANS_CURRENCY", "")
    if len(CURRENCY) != 3:
        raise ImproperlyConfigured(
            "PLANS_CURRENCY should be configured as 3-letter currency code."
        )
    return CURRENCY


def country_code_transform(country_code):
    """Transform country code to the code used by VIES"""
    transform_dict = {
        "GR": "EL",
    }
    return transform_dict.get(country_code, country_code)


def calculate_tax_rate(tax_number, country_code, request=None):
    taxation_policy = getattr(settings, "PLANS_TAXATION_POLICY", None)
    if not taxation_policy:
        raise ImproperlyConfigured("PLANS_TAXATION_POLICY is not set")
    taxation_policy = import_name(taxation_policy)
    tax, request_successful = taxation_policy.get_tax_rate(
        tax_number, country_code, request
    )
    if request_successful and request:
        TaxCacheService.cache_tax_rate(request, tax, tax_number, country_code)
    return Decimal(tax) if tax is not None else None, request_successful


def get_tax_rate(country_code, tax_number, request=None):
    """Get tax rate for given country and tax number
    1. Try to get tax rate from cache
    2. If not in cache, calculate it (and possibly cache it)

    Returns tax rate and if the request was successful (False means default tax rate was used)
    """
    if request:
        try:
            tax_from_cache = TaxCacheService.get_tax_rate(
                request, tax_number, country_code
            )
            return tax_from_cache, True
        except KeyError:
            pass

    tax, request_successful = calculate_tax_rate(tax_number, country_code, request)
    return tax, request_successful


class TaxCacheService:
    @classmethod
    def get_cache_key(cls, tax_number, country):
        return "tax_%s_%s" % (tax_number, country)

    @classmethod
    def cache_tax_rate(cls, request, tax, tax_number, country):
        request.session[cls.get_cache_key(tax_number, country)] = str(tax)

    @classmethod
    def get_tax_rate(cls, request, tax_number, country):
        key = cls.get_cache_key(tax_number, country)
        if key not in request.session:
            raise KeyError(
                f"Tax rate for {tax_number} and {country} not found in cache"
            )
        raw = request.session[key]
        if raw == "None":
            return None
        return Decimal(raw)
