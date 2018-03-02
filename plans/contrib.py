import logging
import operator

from django.core import mail
from django.conf import settings
from django.apps import apps
from django.template import loader
from django.utils import translation
from django.db.models import FieldDoesNotExist
from plans.signals import buyer_language
from django.core.exceptions import ImproperlyConfigured

email_logger = logging.getLogger('emails')


USER_BUYER_RELATION_SETTING = 'PLANS_USER_BUYER_RELATION'
try:
    USER_BUYER_RELATION = getattr(settings, USER_BUYER_RELATION_SETTING)
except AttributeError:
    raise ImproperlyConfigured(
        f"Please set {USER_BUYER_RELATION_SETTING} in order to create relation between user and buyer."
    )


def send_template_email(recipients, title_template, body_template, context, language):
    """Sends e-mail using templating system"""

    send_emails = getattr(settings, 'SEND_PLANS_EMAILS', True)
    if not send_emails:
        return

    domain = getattr(settings, 'SITE_URL', None)
    context.update({'site_domain': domain})

    if language is not None:
        translation.activate(language)

    mail_title_template = loader.get_template(title_template)
    mail_body_template = loader.get_template(body_template)
    title = mail_title_template.render(context)
    body = mail_body_template.render(context)

    try:
        email_from = getattr(settings, 'DEFAULT_FROM_EMAIL')
    except AttributeError:
        raise ImproperlyConfigured('DEFAULT_FROM_EMAIL setting needed for sending e-mails')

    mail.send_mail(title, body, email_from, recipients)

    if language is not None:
        translation.deactivate()

    email_logger.info(u"Email (%s) sent to %s\nTitle: %s\n%s\n\n" % (language, recipients, title, body))


def get_buyer_language(buyer):
    """ Simple helper that will fire django signal in order to get User language possibly given by other part of application.
    :param buyer:
    :return: string or None
    """
    return_value = {}
    buyer_language.send(sender=buyer, buyer=buyer, return_value=return_value)
    return return_value.get('language')


def get_buyer_for_user(user):
    """
    Returns buyer associated with user using relation defined in settings as PLANS_USER_BUYER_RELATION.
    :param user:
    :return: plans.models.Buyer
    """
    try:
        return operator.attrgetter(USER_BUYER_RELATION)(user)
    except AttributeError:
        raise FieldDoesNotExist(
            f'User model should have defined a ForeignKey named {USER_BUYER_RELATION} '
            f'to the model set in {USER_BUYER_RELATION_SETTING}'
        )
