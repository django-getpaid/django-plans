import datetime
import logging
from celery.schedules import crontab
from celery.task.base import periodic_task
from django.conf import settings
from django.contrib.auth import get_user_model
from .signals import account_automatic_renewal


User = get_user_model()
logger = logging.getLogger('plans.tasks')


@periodic_task(run_every=crontab(hour=0, minute=5))
def autorenew_account():
    logger.info('Started')
    PLANS_AUTORENEW_BEFORE_DAYS = getattr(settings, 'PLANS_AUTORENEW_BEFORE_DAYS', 0)
    PLANS_AUTORENEW_BEFORE_HOURS = getattr(settings, 'PLANS_AUTORENEW_BEFORE_HOURS', 0)

    expired_accounts = User.objects.select_related('userplan').filter(
        userplan__active=True,
        userplan__expire__lt=datetime.date.today() + datetime.timedelta(days=PLANS_AUTORENEW_BEFORE_DAYS, hours=PLANS_AUTORENEW_BEFORE_HOURS),
    ).exclude(userplan__expire=None)

    renewed_accounts = []

    for user in expired_accounts.all():
        if hasattr(user.userplan, 'recurring') and getattr(user.userplan.recurring, 'automatic_renewal', False):
            account_automatic_renewal.send(sender=None, user=user)
            renewed_accounts.append(user)
    return renewed_accounts


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
