import unittest

from app.services.venue_service import _as_list, _capacity, _diff_keyed_items, _diff_set


class TestVenueHelpers(unittest.TestCase):
    def test_as_list_accepts_a_list_json_text_and_empty_values(self):
        self.assertEqual(_as_list(["PA"]), ["PA"])
        self.assertEqual(_as_list(None), [])
        self.assertEqual(_as_list(""), [])
        self.assertEqual(_as_list('[{"capacity": 3}]'), [{"capacity": 3}])

    def test_capacity_is_zero_without_layouts_and_the_highest_layout_otherwise(self):
        self.assertEqual(_capacity([]), 0)
        self.assertEqual(_capacity([{"capacity": 1}]), 1)
        self.assertEqual(_capacity([{"capacity": 40}, {"capacity": 40}]), 40)
        self.assertEqual(_capacity([{"capacity": 2}, {"capacity": 5}]), 5)

    def test_diff_keyed_items_records_adds_removals_and_field_edits(self):
        old = [
            {"name": "Theatre", "capacity": 100},
            {"name": "Classroom", "capacity": 40, "note": "a"},
            {"name": "Banquet", "capacity": 20},
            {"name": "Boardroom", "capacity": 10},
        ]
        new = [
            {"name": "Theatre", "capacity": 120},
            {"name": "Classroom", "capacity": 40, "note": "b"},
            {"name": "Exhibition", "capacity": 80},
            {"name": "Boardroom", "capacity": 10},
        ]

        diff = _diff_keyed_items(old, new, "name", ["capacity"])

        self.assertEqual(diff["Theatre"], {"capacity": {"old": 100, "new": 120}})
        self.assertEqual(diff["Banquet"], {"removed": {"capacity": 20}})
        self.assertEqual(diff["Exhibition"], {"added": {"capacity": 80}})
        self.assertNotIn("Classroom", diff)

    def test_diff_set_records_added_and_removed_values(self):
        self.assertEqual(_diff_set(["A", "B"], ["B", "C"]), {"added": ["C"], "removed": ["A"]})
        self.assertEqual(_diff_set([], ["A"]), {"added": ["A"]})
        self.assertEqual(_diff_set(["A"], []), {"removed": ["A"]})
        self.assertEqual(_diff_set(["A"], ["A"]), {})
