from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible

from plans.models import Buyer


@python_2_unicode_compatible
class Foo(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default="A new foo")

    def __str__(self):
        return self.name


class Company(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    buyer = models.OneToOneField(Buyer, null=True, on_delete=models.SET_NULL, related_name='company')

    def __str__(self):
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, null=True)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        company = Company.objects.create(name=instance.username+'_COMPANY', email=instance.username+'@email.com')
        profile = Profile.objects.create(user=instance, company=company)
        profile.save()


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
