Plans recurrence and automatic renewal
======================================

To support renewal of plans, use ``RecurringUserPlan`` model to store information about the recurrence.

The plans can be renewed automatically using this app, the ``RecurringUserPlan`` information can be used only to store information for one-click user initiated renewal (with ``renewal_triggered_by=USER``), or the ``RecurringUserPlan`` can indicate that another mechanism is used to automatically renew the plans (``renewal_triggered_by=OTHER``).

For plans, that should be renewed automatically using this app fill in information about the recurrence::

   self.order.user.userplan.set_plan_renewal(
       order=self.order,
       renewal_triggered_by=TASK,
       ...
       # Not required
       payment_provider='FooProvider',
       token=token,
       card_expire_year=card_expire_year,
       card_expire_month=card_expire_month,
       ...
   )

Then all active ``UserPlan`` with ``RecurringUserPlan.renewal_triggered_by=TASK`` will be picked by ``autorenew_account`` task, that will send ``account_automatic_renewal`` signal.
This signal can be used for your implementation of automatic plan renewal. You should implement following steps::

   @receiver(account_automatic_renewal)
   def renew_accounts(sender, user, *args, **kwargs):
       order = user.userplan.recurring.create_renew_order()

       ...
       payment = Payment(
           order=order,
           amount=order,
           variant=payment_variant,
           total=Decimal(order.total()),
           tax=Decimal(order.tax_total()),
           currency=order.currency,
           ...
           # Create your payment as your payment provider requires
       )

       payment.complete_payment(user.userplan.recurring.token)
       # Or whatever your implementation for automatic payment renewal needs to complete the payment
       ...

       if payment.status == 'confirmed':
           order.complete_order()

If there can be any time delay between the payment renewal initiation and renewal completion, you can fill in ``PLANS_AUTORENEW_BEFORE_DAYS`` and ``PLANS_AUTORENEW_BEFORE_HOURS`` settings, so the payment is given time before it expires.

You should also bear in mind, that the plans expiration reminders are send the same for recurring payments, so adjust your settings and mailing templates, so that your users will get correct information.
