from django.core.exceptions import ImproperlyConfigured, FieldDoesNotExist
from django.urls import reverse
from django.conf import settings
import operator

from plans.contrib import get_buyer_for_user
from plans.models import BuyerPlan


def account_status(request):
    """
    Set following ``RequestContext`` variables:

     * ``ACCOUNT_EXPIRED = boolean``, account was expired state,
     * ``ACCOUNT_NOT_ACTIVE = boolean``, set when account is not expired, but it is over quotas so it is
                                        not active
     * ``EXPIRE_IN_DAYS = integer``, number of days to account expiration,
     * ``EXTEND_URL = string``, URL to account extend page.
     * ``ACTIVATE_URL = string``, URL to account activation needed if  account is not active

    """

    if request.user.is_authenticated:
        buyer = get_buyer_for_user(request.user)

        try:
            return {
                'ACCOUNT_EXPIRED': buyer.buyerplan.is_expired(),
                'ACCOUNT_NOT_ACTIVE': (
                    not buyer.buyerplan.is_active() and not buyer.buyerplan.is_expired()
                ),
                'EXPIRE_IN_DAYS': buyer.buyerplan.days_left(),
                'EXTEND_URL': reverse('current_plan'),
                'ACTIVATE_URL': reverse('account_activation'),
            }
        except BuyerPlan.DoesNotExist:
            pass
    return {}
