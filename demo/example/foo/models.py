from django.db import models

# Create your models here.

class Foo(models.Model):
    user = models.ForeignKey('auth.User')
    name = models.CharField(max_length=100, default="A new foo")

    def __unicode__(self):
        return self.name