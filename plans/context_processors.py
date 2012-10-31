from datetime import date, datetime
from django.core.urlresolvers import reverse
from pytz import utc
from plans.models import UserPlan

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

    if request.user.is_authenticated():
        return {
            'ACCOUNT_EXPIRED' : request.user_plan.is_expired(),
            'ACCOUNT_NOT_ACTIVE' : (not request.user_plan.is_active() and not request.user_plan.is_expired()),
            'EXPIRE_IN_DAYS' : (request.user_plan.expire - date.today()).days,
            'EXTEND_URL' :  reverse('current_plan'),
            'ACTIVATE_URL' : reverse('account_activation'),
        }
    return {}
