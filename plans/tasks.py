import datetime
import logging
from celery.schedules import crontab
from celery.task.base import periodic_task
from django.conf import settings
from plans.models import Buyer


logger = logging.getLogger('plans.tasks')


@periodic_task(run_every=crontab(hour=0, minute=5))
def expire_account():

    logger.info('Started')

    buyers_with_plans = Buyer.objects.select_related('buyerplan')
    for buyer in buyers_with_plans.filter(
        buyerplan__active=True,
        buyerplan__expire__lt=datetime.date.today()
    ).exclude(
        buyerplan__expire=None
    ):
        buyer.buyerplan.expire_account()

    notifications_days_before = getattr(settings, 'PLANS_EXPIRATION_REMIND', [])

    if notifications_days_before:
        days = map(lambda x: datetime.date.today() + datetime.timedelta(days=x), notifications_days_before)
        for buyer in buyers_with_plans.filter(
            buyerplan__active=True,
            buyerplan__expire__in=days
        ):
            buyer.buyerplan.remind_expire_soon()
