Caveats
=======

Problem with generic Suds client
--------------------------------

``Suds`` client is used by ``vatnumber`` module to query VIES system for VAT ID numbers. The problem was it was
making an error (exception that NoneType does not have str method). This error was shown only with
django (with possibly django-debug-toolbar enabled). As we can read here
http://stackoverflow.com/questions/9664705/django-and-suds-nonetype-object-has-no-attribute-str-in-suds
this is a bug in ``Suds`` that is caused by some logging problem. In console this bug fails silently, but
when called from django make an Exception.

As stackoverflow answers, the solution is to use fixed version of ``Suds`` that unfortunately is not in PyPi.
Working suds version can be clone from:
https://github.com/cypreess/suds-htj.git

Version: 0.4.1-htj  is reported to be working.