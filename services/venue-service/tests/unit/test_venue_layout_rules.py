import unittest

from pydantic import ValidationError

from app.schemas.venue import Layout


class TestVenueLayoutRules(unittest.TestCase):
    def test_a_layout_capacity_of_one_is_the_smallest_accepted(self):
        self.assertEqual(Layout(name="Boardroom", capacity=1).capacity, 1)

    def test_a_layout_capacity_of_zero_is_rejected(self):
        with self.assertRaises(ValidationError):
            Layout(name="Boardroom", capacity=0)

    def test_a_negative_layout_capacity_is_rejected(self):
        with self.assertRaises(ValidationError):
            Layout(name="Boardroom", capacity=-1)

    def test_a_blank_layout_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            Layout(name="", capacity=10)
