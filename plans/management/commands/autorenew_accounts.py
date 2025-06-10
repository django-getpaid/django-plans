import logging

from django.core.management import BaseCommand

from plans import tasks


class Command(BaseCommand):
    help = "Autorenew accounts and with recurring payments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--providers",
            nargs="+",
            dest="providers",
            help="Renew only accounts with this providers",
        )
        parser.add_argument(
            "--throttle",
            type=int,
            dest="throttle",
            help="Throttle seconds between renewals",
        )
        parser.add_argument(
            "--catch-exceptions",
            action="store_true",
            dest="catch_exceptions",
            help="Catch exceptions during renewal and log them",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Dry run, do not change any data",
        )

    def handle(self, *args, **options):  # pragma: no cover
        logger = logging.getLogger("plans.tasks")
        handler = logging.StreamHandler(self.stdout)
        logger.addHandler(handler)
        verbosity = options.get("verbosity")
        if verbosity == 0:
            logger.setLevel(logging.WARNING)
        elif verbosity == 1:
            logger.setLevel(logging.INFO)
        else:  # verbosity > 1
            logger.setLevel(logging.DEBUG)

        try:
            providers = options.get("providers")
            dry_run = options.get("dry_run")
            self.stdout.write("Starting renewal")
            if dry_run:
                self.stdout.write("DRY RUN active")
            throttle_seconds = options.get("throttle")
            catch_exceptions = options.get("catch_exceptions")
            renewed_accounts = tasks.autorenew_account(
                providers,
                throttle_seconds=throttle_seconds,
                catch_exceptions=catch_exceptions,
                dry_run=dry_run,
            )
            if renewed_accounts:
                if dry_run:
                    self.stdout.write(
                        f"{len(renewed_accounts)} accounts would be submitted to renewal:"
                    )
                else:
                    self.stdout.write(
                        f"{len(renewed_accounts)} accounts submitted to renewal:"
                    )
                for a in renewed_accounts:
                    self.stdout.write(
                        f"\t{a.userplan.recurring.payment_provider:<30}{a.email:<40}{str(a).strip():<40}"
                        f"{a.userplan.expire}\t{a.userplan.active}"
                    )
            else:
                self.stdout.write("No accounts autorenewed")
        finally:
            logger.removeHandler(handler)
