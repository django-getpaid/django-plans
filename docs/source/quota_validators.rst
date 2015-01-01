Validation of quota
===================

The model of plans introduced in this application make use of quota, which are just some arbitrarily given limits.
Quota definition is quite flexible and allows to define many different types of restrictions. Conceptually you may need
one of following types of quota in your system.

* **limiting resources** - limiting number of some entities on user account (typically an entities is a single django
  model instance); e.g. an image gallery system could limit number of images per account as one of the system
  parameter. Each image is represented by one instance of e.g. UploadedImage model.

* **limiting states** - limiting that some entities on user account can be in a given state (typically some model instance
  attributes can have specific values)

* **limiting actions** - limiting if user can perform some kind of action (typically an action is a specific POST request
  which creates/updates/delete a model instance)


.. note::

    Presented list of quota types is only a conceptual classification. It may not be directly addressed in django-plans
    API, however django-plans aims to support those kind of limitations.


Account complete validation
---------------------------

Complete account validation is needed when user is switching a plan (or in a general - activating a plan). The reason is that user account can be in the state that exhausting limits of new plan (e.g. on downgrade). Plan should not be activated on the user account until user will not remove over limit resources until the account could validate in limits of the new plan.

In django-plans there is a common validation mechanism which requires defining ``PLANS_VALIDATORS`` variable in ``settings.py``.

The format of ``PLANS_VALIDATORS`` variable is given as a dict::

    PLANS_VALIDATORS = {
        '<QUOTA_CODE_NAME>' :  '<full.python.path.to.validator.class>',
        [...]
    }

First of all this variable defines all quota that should be validated on any plan activation.

.. note::

    Please note that the only quota that can be added to ``PLANS_VALIDATORS`` are "limiting resources quota" and "limiting states" quota. Those are the kind of quota that conceptually can be validated within the database state. The third kind of quota ("limiting actions quota") are to be checked on to go when user is just using it's account and performing certain actions.

Secondly each quota has a specific validator defined that is custom to your need of validations.

Quota validators
----------------

Each validator should inherit from :class:`plans.validators.QuotaValidator`.

.. autoclass:: plans.validators.QuotaValidator
    :members:
    :undoc-members:

Validator should have defined ``__call__(self, user, **kwargs)`` method which should raise :class:`django.core.exceptions.ValidationError` if account does not meet limits requirement.


Model count validator
`````````````````````

Currently django-plans is shipped with one handy validator. It can easily validate number of instances of any model for a given user.

.. autoclass:: plans.validators.ModelCountValidator
    :members:
    :undoc-members:

We recommend to create ``validators.py`` in your application path with your own custom validators.

E.g. this limits number of ``Foo`` instances in the example project, in ``foo/validators.py``::

    from example.foo.models import Foo
    from plans.validators import ModelCountValidator


    class MaxFoosValidator(ModelCountValidator):
        code = 'MAX_FOO_COUNT'
        model = Foo

        def get_queryset(self, user):
            return super(MaxFoosValidator, self).get_queryset(user).filter(user=user)

    max_foos_validator = MaxFoosValidator()

You can easily re-use it also in create model form for this object to check if user can add a number of instances regarding his quota, in ``foo/forms.py``::

    from django.forms import ModelForm, HiddenInput
    from example.foo.models import Foo
    from example.foo.validators import max_foos_validator


    class FooForm(ModelForm):
        class Meta:
            model = Foo
            widgets = {'user' : HiddenInput,}

        def clean(self):
            cleaned_data = super(FooForm, self).clean()
            max_foos_validator(cleaned_data['user'], add=1)
            return cleaned_data


Model attribute validator
`````````````````````````

This validator can validate that every object returned from a queryset have correct value of attribute.


.. autoclass:: plans.validators.ModelAttributeValidator
    :members:
    :undoc-members:

E.g.::


    from example.foo.models import Foo
    from plans.validators import ModelCountValidator


    class MaxFooSizeValidator(ModelAttributeValidator):
        code = 'MAX_FOO_SIZE'
        model = Foo
        attribute = 'size'

        def get_queryset(self, user):
            return super(MaxFoosValidator, self).get_queryset(user).filter(user=user)

    max_foo_size_validator = MaxFooSizeValidator()

This validator will ensure that user does not have any object with attribute 'size' which is greater then the quota. If you need to provide any custom comparison other than "greater than" just override method ``check_attribute_value(attribute_value, quota_value)``.