Extending django-plans: custom models
=====================================

Creating custom models
----------------------

In a ``custom_plans`` app, it is possible to use an updated version of the ``plans`` app model. 
We can achieve this by adding extra fields to the abstract models of the ``plans`` app. 
Let's consider the example where we want our ``custom_plans`` app to use the ``Order`` model 
of the ``plans`` app with a ``detail`` field added to it. We will create our ``CustomOrder`` 
model as follows:

.. code-block:: python

    from django.db import models
    from plans.base.models import AbstractOrder

    class DetailModel(models.Model):
        detail = models.CharField(max_length=12, blank=True, null=True)

        class Meta:
            abstract = True


    class CustomOrder(DetailModel, AbstractOrder):
        class Meta:
            abstract = False

Using custom models
-------------------

After creating our custom model (``CustomOrder``) we need to configure our ``custom_plans`` app 
to use the newly created ``CustomOrder`` model instead of the ``Order`` model from the ``plan`` app. 
We can achieve this by `updating <./setting.html#swappable-models>`_ our `settings.py` file.
