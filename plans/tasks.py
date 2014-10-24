import datetime
import logging
from celery.schedules import crontab
from celery.task.base import periodic_task
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger('plans.tasks')

@periodic_task(run_every=crontab(hour=0, minute=5))
def expire_account():

    logger.info('Started expire_account periodic task')

    _user_model = get_user_model()

    for user in _user_model.objects.select_related('userplan').filter(userplan__active=True,
                                                                      userplan__expire__lt=datetime.date.today()).exclude(userplan__expire=None):
        user.userplan.expire_account()

    notifications_days_before = getattr(settings, 'PLAN_EXPIRATION_REMIND', [])

    if notifications_days_before:
        days = map(lambda x: datetime.date.today() + datetime.timedelta(days=x), notifications_days_before)
        for user in get_user_model().objects.select_related('userplan').filter(userplan__active=True, userplan__expire__in=days):
            user.userplan.remind_expire_soon()
