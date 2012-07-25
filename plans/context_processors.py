from datetime import date
from django.core.urlresolvers import reverse
from plans.models import UserPlan

def expiration(request):
    """
    Set three ``RequestContext`` variables:

     * ``ACCOUNT_EXPIRED = boolean``, account was expired state,
     * ``EXPIRE_IN_DAYS = integer``, number of days to account expiration,
     * ``EXTEND_URL = string``, URL to account extend page.

    """

    if request.user.is_authenticated():
        try:
            user_plan = UserPlan.objects.all().get(user=request.user)
            return {
                'ACCOUNT_EXPIRED' : (not user_plan.active),
                'EXPIRE_IN_DAYS' : (user_plan.expire - date.today()).days,
                'EXTEND_URL' :  reverse('current_plan'),
            }
        except UserPlan.DoesNotExist:
            pass
    return {}
