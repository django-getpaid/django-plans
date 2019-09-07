from django.core.management import BaseCommand

from plans.base.models import AbstractUserPlan

UserPlan = AbstractUserPlan.get_concrete_model()


class Command(BaseCommand):
    help = 'Creates UserPlans for all Users'

    def handle(self, *args, **options):  # pragma: no cover
        userplans = UserPlan.create_for_users_without_plan()
        self.stdout.write("%s user plans was created" % userplans.count())
