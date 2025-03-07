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

    def handle(self, *args, **options):  # pragma: no cover
        providers = options.get("providers")
        self.stdout.write("Starting renewal")
        throttle_seconds = options.get("throttle")
        renewed_accounts = tasks.autorenew_account(
            providers, throttle_seconds=throttle_seconds
        )
        if renewed_accounts:
            self.stdout.write("Accounts submitted to renewal:")
            for a in renewed_accounts:
                self.stdout.write(
                    f"\t{a.userplan.recurring.payment_provider}\t{a.email}\t{a}"
                )
        else:
            self.stdout.write("No accounts autorenewed")
