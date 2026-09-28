from tests.unit.support import CALLER, EquipmentCase, equipment_create


class TestEquipmentUnits(EquipmentCase):
    def test_status_follows_unit_rows(self):
        plain = self.service.create_equipment(equipment_create(code="PLAIN"), CALLER)
        maintained = self.service.create_equipment(equipment_create(code="MAINT"), CALLER)
        damaged = self.service.create_equipment(equipment_create(code="DMG"), CALLER)
        available = self.service.create_equipment(equipment_create(code="OK"), CALLER)
        self.add_unit(maintained.equipmentId, "maintenance")
        self.add_unit(damaged.equipmentId, "damaged")
        self.add_unit(available.equipmentId, "available")

        self.assertEqual(self.service.get_equipment(plain.equipmentId).status, "available")
        self.assertEqual(self.service.get_equipment(maintained.equipmentId).status, "maintenance")
        self.assertEqual(self.service.get_equipment(damaged.equipmentId).status, "damaged")
        self.assertEqual(self.service.get_equipment(available.equipmentId).status, "available")
