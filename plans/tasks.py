import datetime
import logging
from celery.schedules import crontab
from celery.task.base import periodic_task
from django.conf import settings
from django.contrib.auth import get_user_model


User = get_user_model()
logger = logging.getLogger('plans.tasks')

@periodic_task(run_every=crontab(hour=0, minute=5))
def expire_account():

    logger.info('Started')

    for user in User.objects.select_related('userplan').filter(userplan__active=True,         userplan__expire__lt=datetime.date.today()).exclude(userplan__expire=None):
        user.userplan.expire_account()

    notifications_days_before = getattr(settings, 'PLANS_EXPIRATION_REMIND', [])

    if notifications_days_before:
        days = map(lambda x: datetime.date.today() + datetime.timedelta(days=x), notifications_days_before)
        for user in User.objects.select_related('userplan').filter(userplan__active=True, userplan__expire__in=days):
            user.userplan.remind_expire_soon()
