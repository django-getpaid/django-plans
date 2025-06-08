import datetime
import logging
import time
import warnings

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import mail_admins
from django.db.models import F, Q
from django.utils import timezone

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


def autorenew_account(
    providers=None, throttle_seconds=0, catch_exceptions=False, dry_run=False
):
    logger.info("Started automatic account renewal")
    PLANS_AUTORENEW_SCHEDULE = getattr(settings, "PLANS_AUTORENEW_SCHEDULE", None)
    PLANS_AUTORENEW_BEFORE_DAYS = getattr(settings, "PLANS_AUTORENEW_BEFORE_DAYS", 0)
    PLANS_AUTORENEW_BEFORE_HOURS = getattr(settings, "PLANS_AUTORENEW_BEFORE_HOURS", 0)

    accounts_to_check = User.objects.select_related(
        "userplan", "userplan__recurring"
    ).filter(
        userplan__recurring__renewal_triggered_by=AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY.TASK,
        userplan__recurring__token_verified=True,
    )

    if PLANS_AUTORENEW_SCHEDULE is not None:
        if PLANS_AUTORENEW_BEFORE_DAYS or PLANS_AUTORENEW_BEFORE_HOURS:
            logger.warning(
                "PLANS_AUTORENEW_SCHEDULE is set, ignoring PLANS_AUTORENEW_BEFORE_DAYS and PLANS_AUTORENEW_BEFORE_HOURS"
            )
        now_dt = timezone.now()
        q = Q()
        max_renew_after = getattr(
            settings,
            "PLANS_AUTORENEW_MAX_DAYS_AFTER_EXPIRY",
            datetime.timedelta(days=30),
        )
        for schedule in PLANS_AUTORENEW_SCHEDULE:
            q |= Q(
                Q(userplan__recurring__last_renewal_attempt__isnull=True)
                | Q(
                    userplan__recurring__last_renewal_attempt__lt=F("userplan__expire")
                    - schedule
                ),
                userplan__expire__lte=now_dt + schedule,
                userplan__expire__gte=now_dt + schedule - max_renew_after,
            )
        accounts_for_renewal = accounts_to_check.filter(q).distinct()
    else:
        warnings.warn(
            "PLANS_AUTORENEW_BEFORE_DAYS and PLANS_AUTORENEW_BEFORE_HOURS are deprecated "
            "and will be removed in a future version. "
            "Please use PLANS_AUTORENEW_SCHEDULE instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        accounts_for_renewal = accounts_to_check.filter(
            userplan__expire__lt=timezone.now()
            + datetime.timedelta(
                days=PLANS_AUTORENEW_BEFORE_DAYS, hours=PLANS_AUTORENEW_BEFORE_HOURS
            ),
        )

    if providers:
        accounts_for_renewal = accounts_for_renewal.filter(
            userplan__recurring__payment_provider__in=providers
        )

    logger.info(f"{accounts_for_renewal.count()} accounts to be renewed.")

    accounts_for_renewal = accounts_for_renewal.all()

    if dry_run:
        logger.info("Dry run mode: No changes will be made.")
        for user in accounts_for_renewal:
            logger.info(f"DRY RUN: Would renew user {user.pk} ({user.email})")
            if hasattr(user, "userplan") and not user.userplan.is_active():
                logger.info(
                    f"DRY RUN: Would activate userplan for user {user.pk} ({user.email})"
                )
            logger.info(
                f"DRY RUN: Would send account_automatic_renewal signal for user {user.pk} ({user.email})"
            )
        return accounts_for_renewal

    renewed_accounts = []
    for user in accounts_for_renewal:
        if hasattr(user, "userplan") and hasattr(user.userplan, "recurring"):
            user.userplan.recurring.last_renewal_attempt = timezone.now()
            user.userplan.recurring.save(update_fields=["last_renewal_attempt"])
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
        renewed_accounts.append(user)
    return renewed_accounts


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
