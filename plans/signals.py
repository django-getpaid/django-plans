from django.dispatch import Signal

order_started = Signal()
order_started.__doc__ = """
Sent after order was started (awaiting payment)
"""

order_completed = Signal()
order_completed.__doc__ = """
Sent after order was completed (payment accepted, account extended)
"""


user_language = Signal()
user_language.__doc__ = """
Sent to receive information about language for user account

sends arguments: 'user', 'language'
"""

account_automatic_renewal = Signal()
account_automatic_renewal.__doc__ = """
Try to renew the account automatically.
Should renew the user's UserPlan by recurring payments. If this succeeds, the plan should be extended.

sends arguments: 'user'
"""

account_expired = Signal()
account_expired.__doc__ = """
Sent on account expiration.
This signal is send regardless ``account_deactivated``
it only means that account has expired due to plan expire date limit.

sends arguments: 'user'
"""

account_deactivated = Signal()
account_deactivated.__doc__ = """
Sent on account deactivation, account is not operational (it could be not expired, but does not meet quota limits).

sends arguments: 'user'
"""

account_activated = Signal()
account_activated.__doc__ = """
Sent on account activation, account is now fully operational.

sends arguments: 'user'
"""
account_change_plan = Signal()
account_change_plan.__doc__ = """
Sent on account when plan was changed after order completion

sends arguments: 'user'
"""

activate_user_plan = Signal()
activate_user_plan.__doc__ = """
This signal should be called when user has succesfully registered (e.g. he activated account via e-mail activation).
If you are using django-registration there is no need to call this signal.

sends arguments: 'user'
"""
