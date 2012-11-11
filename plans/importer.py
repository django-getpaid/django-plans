def import_name(name):
    components = name.split('.')
    mod = __import__('.'.join(components[0:-1]), globals(), locals(), [components[-1]] )
    return getattr(mod, components[-1])
