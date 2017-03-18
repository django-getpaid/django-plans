from __future__ import unicode_literals
from django.db import models
from django.conf import settings

# Create your models here.
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Foo(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    name = models.CharField(max_length=100, default="A new foo")

    def __str__(self):
        return self.name