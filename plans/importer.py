def import_name(name):
    """ import module given by str or pass the module if it is not str """
    if isinstance(name, str):
        components = name.split('.')
        mod = __import__('.'.join(components[0:-1]), globals(), locals(), [components[-1]] )
        return getattr(mod, components[-1])
    else:
        return name
