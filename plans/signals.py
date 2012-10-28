from django.dispatch import Signal

order_started = Signal()
order_started.__doc__ = """
Sent after order was started (awaiting payment)
"""

order_completed = Signal()
order_completed.__doc__ = """
Sent after order was completed (payment accepted, account extended)
"""


user_language = Signal(providing_args=['user', 'language'])
user_language.__doc__ = """Sent to receive information about language for user account"""



account_expired = Signal(providing_args=['user'])
account_expired.__doc__ = """
Sent on account expiration.
"""
account_activated = Signal(providing_args=['user'])
account_activated.__doc__ = """
Sent on account activation after expiration
"""
account_change_plan = Signal(providing_args=['user'])
account_change_plan.__doc__ = """
Sent on account when plan was changed after order completion
"""
