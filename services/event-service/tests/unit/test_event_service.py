from tests.unit.support import EventCase, event_create


class TestEventService(EventCase):
    def test_session_dependency_closes_and_init_db_is_a_noop(self):
        self.close_db_dependency()

    def test_create_event_submits_it_for_the_organiser(self):
        created = self.service.create_event(event_create(), "org-1", "o1", "Bearer token")

        self.assertEqual(created.status, "submitted")
        self.assertEqual(created.registeredCount, 3)
        self.assertEqual(created.eventName, "Summit")
