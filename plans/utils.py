from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_country_code(request):
    if getattr(settings, 'PLANS_GET_COUNTRY_FROM_IP', False):
        try:
            from geolite2 import geolite2

            reader = geolite2.reader()
            ip_address = get_client_ip(request)
            ip_info = reader.get(ip_address)
        except ModuleNotFoundError:
            ip_info = None

        if ip_info and 'country' in ip_info:
            country_code = ip_info['country']['iso_code']
            return country_code
    return getattr(settings, 'PLANS_DEFAULT_COUNTRY', None)


def get_currency():
    CURRENCY = getattr(settings, 'PLANS_CURRENCY', '')
    if len(CURRENCY) != 3:
        raise ImproperlyConfigured('PLANS_CURRENCY should be configured as 3-letter currency code.')
    return CURRENCY


def country_code_transform(country_code):
    """ Transform country code to the code used by VIES """
    transform_dict = {
        "GR": "EL",
    }
    return transform_dict.get(country_code, country_code)
