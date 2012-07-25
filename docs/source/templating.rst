Templates
=========

Account expiration warnings
---------------------------
Via the ``plans.context_processors.expiration`` this module allows
to display in any template a message when:

* user account has expired,
* user account will expire soon.

First you need to add a context processor to your settings, e.g.::


    TEMPLATE_CONTEXT_PROCESSORS = global_settings.TEMPLATE_CONTEXT_PROCESSORS + (
        'plans.context_processors.expiration'
        )

The context processor is defined as follows:

.. autofunction:: plans.context_processors.expiration

What you might want to do now is to create a custom ``expiration_messages.html`` template::


    {% load i18n %}

    {% if ACCOUNT_EXPIRED %}
        <div class="messages_permanent error">
            {% blocktrans with extend_url=EXTEND_URL %}
                Your account has expired. You need to <a href="{{ extend_url }}">extend your account now</a> in order to use it.
            {% endblocktrans %}
        </div>
    {% else %}

        {% if EXPIRE_IN_DAYS >= 0 and EXPIRE_IN_DAYS <= 14 %}
            <div class="messages_permanent warning">
                {% blocktrans with extend_url=EXTEND_URL days_to_expire=EXPIRE_IN_DAYS %}
                    Your account will expire soon (in {{ days_to_expire }} days). We recommend to <a href="{{ extend_url }}">extend your account now.</a>
                {% endblocktrans %}
            </div>
        {% endif %}

    {% endif %}




and put ``(% include "expiration_messages.html" %}`` in suitable places (for example in base template of every user logged pages). Here in template you can customize when exactly you want to display notifications (e.g. how many days before expiration).