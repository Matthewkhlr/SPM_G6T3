from fastapi import HTTPException

from app.schemas.equipment import EquipmentUpdate, OutOfServiceCounts
from tests.unit.support import CALLER, EquipmentCase, equipment_create


class TestEquipmentCatalogue(EquipmentCase):
    def test_session_dependency_closes_and_init_db_is_a_noop(self):
        self.close_db_dependency()

    def test_create_equipment_logs_the_opening_quantity(self):
        created = self.service.create_equipment(equipment_create(), CALLER)

        self.assertEqual(created.name, "Projector")
        self.assertEqual(created.serviceableQuantity, 4)
        self.assertEqual(created.status, "available")
        self.assertEqual(self.service.get_activity_log(created.equipmentId)[0].action, "created")

    def test_create_rejects_negative_quantities_and_counts_above_the_total(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.create_equipment(equipment_create(totalQuantity=-1), CALLER)
        self.assertEqual(ctx.exception.status_code, 422)

        with self.assertRaises(HTTPException) as ctx:
            self.service.create_equipment(
                equipment_create(outOfService=OutOfServiceCounts(damaged=3, maintenance=2, retired=0)),
                CALLER,
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_out_of_service_counts_may_use_the_whole_total_and_no_more(self):
        exact = self.service.create_equipment(
            equipment_create(
                code="EXACT",
                totalQuantity=4,
                outOfService=OutOfServiceCounts(damaged=2, maintenance=1, retired=1),
            ),
            CALLER,
        )
        self.assertEqual(exact.serviceableQuantity, 0)

        with self.assertRaises(HTTPException) as ctx:
            self.service.create_equipment(
                equipment_create(code="NEG", totalQuantity=4, outOfService=OutOfServiceCounts(damaged=-1)),
                CALLER,
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "Quantities cannot be negative")

    def test_create_rejects_a_duplicate_code(self):
        self.service.create_equipment(equipment_create(), CALLER)

        with self.assertRaises(HTTPException) as ctx:
            self.service.create_equipment(equipment_create(), CALLER)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_missing_equipment_and_request_are_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_equipment("missing")
        self.assertEqual(ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx:
            self.service.get_activity_log("missing")
        self.assertEqual(ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx:
            self.service.review_request("missing", "u-tech", True, "")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_list_equipment_sorts_by_id_length_then_id(self):
        first = self.service.create_equipment(equipment_create(code="A"), CALLER)
        second = self.service.create_equipment(equipment_create(code="B"), CALLER)

        listed = [row.equipmentId for row in self.service.list_equipment()]

        self.assertEqual(listed, sorted(listed, key=lambda value: (len(value), value)))
        self.assertCountEqual(listed, [first.equipmentId, second.equipmentId])

    def test_update_changes_every_catalogue_field(self):
        created = self.service.create_equipment(equipment_create(), CALLER)

        updated = self.service.update_equipment(
            created.equipmentId,
            EquipmentUpdate(
                code="PX-201",
                name="Projector Plus",
                category="audio",
                description="Updated",
                technicalNotes="New lamp",
                totalQuantity=6,
                homeLocation="Annex",
                outOfService=OutOfServiceCounts(damaged=1, maintenance=1, retired=1),
            ),
            CALLER,
        )

        self.assertEqual(updated.code, "PX-201")
        self.assertEqual(updated.homeLocation, "Annex")
        self.assertEqual(updated.serviceableQuantity, 3)
        self.assertEqual(updated.outOfService.damaged, 1)

    def test_update_with_the_same_values_does_not_write_a_log(self):
        created = self.service.create_equipment(equipment_create(), CALLER)

        self.service.update_equipment(
            created.equipmentId,
            EquipmentUpdate(
                code="PX-200",
                name="Projector",
                category="display",
                description="HDMI",
                technicalNotes="Spare lamp",
                totalQuantity=4,
                homeLocation="Store",
                outOfService=OutOfServiceCounts(),
            ),
            CALLER,
        )

        actions = [row.action for row in self.service.get_activity_log(created.equipmentId)]
        self.assertEqual(actions, ["created"])

    def test_empty_update_leaves_the_record_unchanged(self):
        created = self.service.create_equipment(equipment_create(), {"userId": "u-tech"})

        updated = self.service.update_equipment(created.equipmentId, EquipmentUpdate(), {})

        self.assertEqual(updated.totalQuantity, 4)
        self.assertEqual(updated.code, "PX-200")

    def test_update_rejects_a_duplicate_code(self):
        self.service.create_equipment(equipment_create(code="PX-200"), CALLER)
        other = self.service.create_equipment(equipment_create(code="PX-300"), CALLER)

        with self.assertRaises(HTTPException) as ctx:
            self.service.update_equipment(other.equipmentId, EquipmentUpdate(code="PX-200"), CALLER)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_blank_code_and_description_fall_back_on_the_output(self):
        created = self.service.create_equipment(
            equipment_create(code="TEMP", description="", homeLocation="", technicalNotes=""),
            CALLER,
        )
        row = self.service._require_equipment(created.equipmentId)
        row.code = ""
        row.description = ""
        row.homeLocation = ""
        row.location = ""
        row.damagedCount = 0
        self.db.commit()

        viewed = self.service.get_equipment(created.equipmentId)

        self.assertEqual(viewed.code, created.equipmentId)
        self.assertEqual(viewed.description, "")
        self.assertEqual(viewed.homeLocation, "")
