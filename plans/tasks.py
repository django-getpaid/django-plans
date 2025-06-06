import datetime
import logging
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import mail_admins

from .base.models import AbstractRecurringUserPlan
from .signals import account_automatic_renewal

User = get_user_model()
logger = logging.getLogger("plans.tasks")


def get_active_plans():
    return (
        User.objects.select_related("userplan")
        .filter(userplan__active=True)
        .exclude(userplan__expire=None)
    )


def autorenew_account(providers=None, throttle_seconds=0, catch_exceptions=False):
    logger.info("Started automatic account renewal")
    PLANS_AUTORENEW_BEFORE_DAYS = getattr(settings, "PLANS_AUTORENEW_BEFORE_DAYS", 0)
    PLANS_AUTORENEW_BEFORE_HOURS = getattr(settings, "PLANS_AUTORENEW_BEFORE_HOURS", 0)

    accounts_for_renewal = get_active_plans().filter(
        userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
        userplan__recurring__token_verified=True,
        userplan__expire__lt=datetime.date.today()
        + datetime.timedelta(
            days=PLANS_AUTORENEW_BEFORE_DAYS, hours=PLANS_AUTORENEW_BEFORE_HOURS
        ),
    )

    if providers:
        accounts_for_renewal = accounts_for_renewal.filter(
            userplan__recurring__payment_provider__in=providers
        )

    logger.info(f"{len(accounts_for_renewal)} accounts to be renewed.")

    for user in accounts_for_renewal.all():
        if throttle_seconds:
            time.sleep(throttle_seconds)
        if catch_exceptions:
            try:
                account_automatic_renewal.send(sender=None, user=user)
            except Exception as e:
                logger.error(
                    f"Error renewing account for user {user.pk} ({user.email}): {e}",
                    exc_info=True,
                )
                subject = f"Failed to renew account for user {user.pk} ({user.email})"
                message = f"""
                An error occurred while trying to automatically renew the account for user:
                User ID: {user.pk}
                User email: {user.email}

                Error details:
                {e}
                """
                mail_admins(subject, message, fail_silently=True)
        else:
            account_automatic_renewal.send(sender=None, user=user)
    return accounts_for_renewal


def expire_account():
    logger.info("Started account expiration")

    expired_accounts = get_active_plans().filter(
        userplan__expire__lt=datetime.date.today()
    )

    for user in expired_accounts.all():
        user.userplan.expire_account()

    notifications_days_before = getattr(settings, "PLANS_EXPIRATION_REMIND", [])

    if notifications_days_before:
        days = map(
            lambda x: datetime.date.today() + datetime.timedelta(days=x),
            notifications_days_before,
        )
        for user in User.objects.select_related("userplan").filter(
            userplan__active=True, userplan__expire__in=days
        ):
            user.userplan.remind_expire_soon()
