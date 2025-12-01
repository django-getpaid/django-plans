# django-plans development instructions

## Testing

Please run tests before submitting code and include/extend tests for
added/changed features to ensure they keep working long-term.

`plans` python module contains tests at [plans/tests/](plans/tests/).

`demo/` project runs `plans` tests by default.

To run tests across supported Python and django versions in isolated testing
environments, simply use `tox` in repo root:

```
tox
```

You can use `-e` to run only a specific testing environment(s), for example:

```
tox -e py311-django
```

See [tox.ini](tox.ini).

You can also run the tests manually in `demo/` dir (presumably using `venv`):

```
cd demo
python manage.py test
```

You can also run coverage tests in a similar manner:

```
cd demo
coverage run manage.py test
```
