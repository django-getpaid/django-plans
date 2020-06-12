import six


class Enumeration(object):
    """
    A small helper class for more readable enumerations,
    and compatible with Django's choice convention.
    You may just pass the instance of this class as the choices
    argument of model/form fields.

    Example:
            MY_ENUM = Enumeration([
                    (100, 'MY_NAME', 'My verbose name'),
                    (200, 'MY_AGE', 'My verbose age'),
            ])
            assert MY_ENUM.MY_AGE == 200
            assert MY_ENUM[1] == (200, 'My verbose age')
    """

    def __init__(self, enum_list):
        self.enum_list_full = enum_list
        self.enum_list = [(item[0], item[2]) for item in enum_list]
        self.enum_dict = {}
        self.enum_code = {}
        self.enum_display = {}
        for item in enum_list:
            self.enum_dict[item[1]] = item[0]
            self.enum_display[item[0]] = item[2]
            self.enum_code[item[0]] = item[1]

    def __contains__(self, v):
        return (v in self.enum_list)

    def __len__(self):
        return len(self.enum_list)

    def __getitem__(self, v):
        if isinstance(v, six.string_types):
            return self.enum_dict[v]
        elif isinstance(v, int):
            return self.enum_list[v]

    def __getattr__(self, name):
        try:
            return self.enum_dict[name]
        except KeyError:
            raise AttributeError

    def __iter__(self):
        return self.enum_list.__iter__()

    def __repr__(self):
        return 'Enum(%s)' % self.enum_list_full.__repr__()

    def get_display_name(self, v):
        return self.enum_display[v]

    def get_display_code(self, v):
        return self.enum_code[v]