from fastapi.testclient import TestClient

from app.dao.organisation_dao import OrganisationDAO
from app.main import app
from app.models.organisation import Organisation
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase


def seed_organisation(db, **overrides):
    data = dict(organisationId="org-1", name="Apex Partners")
    data.update(overrides)
    organisation = Organisation(**data)
    db.add(organisation)
    db.commit()
    return organisation


class TestOrganisationDAO(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.dao = OrganisationDAO(self.db)

    def test_list_all_returns_an_empty_list_when_there_are_no_organisations(self):
        self.assertEqual(self.dao.list_all(), [])

    def test_list_all_returns_every_seeded_organisation(self):
        seed_organisation(self.db)
        seed_organisation(self.db, organisationId="org-2", name="Bright Events")

        organisations = self.dao.list_all()

        self.assertEqual(
            {org.organisationId for org in organisations},
            {"org-1", "org-2"},
        )


class TestOrganisationRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {
            "uid": "firebase-uid-1",
            "email": "amy@connectsphere.com",
        }
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_list_organisations_returns_id_and_name_for_each_organisation(self):
        seed_organisation(self.db)
        seed_organisation(self.db, organisationId="org-2", name="Bright Events")

        response = self.client.get("/organisations")

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.json(),
            [
                {"organisationId": "org-1", "name": "Apex Partners"},
                {"organisationId": "org-2", "name": "Bright Events"},
            ],
        )

    def test_list_organisations_returns_an_empty_list_when_there_are_none(self):
        response = self.client.get("/organisations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_organisations_requires_authentication(self):
        app.dependency_overrides.clear()

        response = self.client.get("/organisations")

        self.assertEqual(response.status_code, 401)
