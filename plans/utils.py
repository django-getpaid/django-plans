
def country_code_transform(country_code):
    """ Transform country code to the code used by VIES """
    transform_dict = {
        "GR": "EL",
    }
    return transform_dict.get(country_code, country_code)
