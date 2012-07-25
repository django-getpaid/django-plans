from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.conf import settings
import datetime

class Command(BaseCommand):
    args = ''
    help = 'Manages account expiration process'

    def handle(self, *args, **options):
        
        for user in User.objects.select_related('userplan').filter(userplan__expire__lt = datetime.date.today()):
            user.userplan.expire()
        
        notifications_days_before = getattr(settings, 'PLAN_EXPIRATION_REMIND', [])
        
        if notifications_days_before :
            days = map(lambda x: datetime.date.today() + datetime.timedelta(days=x), notifications_days_before)
            for user in User.objects.select_related('userplan').filter(userplan__expire__in=days):
                user.userplan.remind_expire_soon()
