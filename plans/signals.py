from django.dispatch import Signal

order_started = Signal()
order_started.__doc__ = """
Sent after order was started (awaiting payment)
"""

order_completed = Signal()
order_completed.__doc__ = """
Sent after order was completed (payment accepted, account extended)
"""


buyer_language = Signal(providing_args=['buyer', 'language'])
buyer_language.__doc__ = """Sent to receive information about language for buyer"""



account_expired = Signal(providing_args=['buyer'])
account_expired.__doc__ = """
Sent on account expiration. This signal is send regardless ``account_deactivated`` it only means that account has expired due to plan expire date limit.
"""

account_deactivated = Signal(providing_args=['buyer'])
account_deactivated.__doc__ = """
Sent on account deactivation, account is not operational (it could be not expired, but does not meet quota limits).
"""

account_activated = Signal(providing_args=['buyer'])
account_activated.__doc__ = """
Sent on account activation, account is now fully operational.
"""
account_change_plan = Signal(providing_args=['buyer'])
account_change_plan.__doc__ = """
Sent on account when plan was changed after order completion
"""

activate_buyer_plan = Signal(providing_args=['buyer'])
activate_buyer_plan.__doc__ = """
This signal should be called when user has succesfully registered (e.g. he activated account via e-mail activation). If you are using django-registration there is no need to call this signal.
"""
