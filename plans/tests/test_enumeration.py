from django.test import SimpleTestCase

from plans.enumeration import Enumeration

COLOURS = Enumeration(
    [
        (1, "RED", "Red colour"),
        (2, "GREEN", "Green colour"),
    ]
)


class EnumerationTests(SimpleTestCase):
    def test_codes_names_and_choices(self):
        self.assertEqual(COLOURS.GREEN, 2)
        self.assertEqual(COLOURS["RED"], 1)
        self.assertEqual(COLOURS[1], (2, "Green colour"))
        self.assertEqual(list(COLOURS), [(1, "Red colour"), (2, "Green colour")])
        self.assertEqual(len(COLOURS), 2)
        self.assertIn((1, "Red colour"), COLOURS)
        self.assertEqual(COLOURS.get_display_name(2), "Green colour")
        self.assertEqual(COLOURS.get_display_code(2), "GREEN")

    def test_unknown_name_is_an_attribute_error(self):
        with self.assertRaises(AttributeError):
            COLOURS.BLUE
