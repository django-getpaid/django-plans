Plans expiration and e-mail notifications
========================================

Plan expiration is done by ``plans.tasks.expire_account`` method, which is expected to run once a day.
Celery can be used to run the method as beat task, or alternatively it can be done by ``expire_accounts`` management command executed by cron or similar tool.

.. note::
   Celery dependency was removed in ``django-plans`` version 1.0.0, now the configuration is left to implementor.

In this action, all ``UserPlan`` objects which have ``expire`` date in the past are set ``active=False``.
Default plan quotas are applied (as described in :doc:`quota_validators`) even if the expire action doesn't run for expired plans.

E-mail notificatons are also send during this task depending on ``PLANS_EXPIRATION_REMIND`` setting (:ref:`settings-EXPIRATION_REMIND`).
