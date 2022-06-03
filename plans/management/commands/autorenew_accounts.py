from django.core.management import BaseCommand

from plans import tasks


class Command(BaseCommand):
    help = 'Autorenew accounts and with recurring payments'

    def handle(self, *args, **options):  # pragma: no cover
        self.stdout.write("Starting renewal")
        renewed_accounts = tasks.autorenew_account()
        if renewed_accounts:
            self.stdout.write("Accounts autorenewed: " + ", ".join(str(s) for s in renewed_accounts))
        else:
            self.stdout.write("No accounts autorenewed")
