from fabric.api import lcd, local, task


@task
def push_lang():
    with lcd('demo/example'):
        local('django-admin.py makemessages -l en')

    with lcd('./plans'):
        local('django-admin.py makemessages -l en')

    local('tx push -s')


@task
def pull_lang():
    local('tx pull')
