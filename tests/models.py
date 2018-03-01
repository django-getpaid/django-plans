from django.db import models
from django.contrib.auth import get_user_model

from plans.models import Buyer


class Team(models.Model):
    email = models.EmailField()
    buyer = models.OneToOneField(Buyer, null=True, on_delete=models.SET_NULL)


class Profile(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)


class Foo(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default="A new foo")

    def __str__(self):
        return self.name
