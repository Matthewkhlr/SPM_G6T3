from fastapi import HTTPException

from app.dao.user_dao import UserDAO
from app.models.organisation import Organisation
from app.schemas.user import UserPublic
from app.services.user_service import UserService
from shared.testing.cases import ServiceTestCase
from tests.unit.support import seed_user


class TestUserService(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.service = UserService(self.db, UserDAO(self.db))

    def test_session_dependency_closes_and_init_db_is_a_noop(self):
        self.close_db_dependency()

    def test_first_login_links_firebase_uid_by_email(self):
        seed_user(self.db)

        resolved = self.service.get_by_firebase_claims("firebase-uid-1", "amy@connectsphere.com")

        self.assertEqual(resolved.userId, "u-1")
        self.assertEqual(resolved.firebaseUid, "firebase-uid-1")

    def test_subsequent_login_resolves_directly_by_firebase_uid(self):
        seed_user(self.db, firebaseUid="firebase-uid-1")

        resolved = self.service.get_by_firebase_claims("firebase-uid-1", None)

        self.assertEqual(resolved.userId, "u-1")

    def test_unknown_email_raises_404(self):
        seed_user(self.db)

        with self.assertRaises(HTTPException) as ctx:
            self.service.get_by_firebase_claims("firebase-uid-2", "nobody@connectsphere.com")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_a_blank_email_does_not_link_an_account(self):
        seeded = seed_user(self.db, email="")

        with self.assertRaises(HTTPException) as ctx:
            self.service.get_by_firebase_claims("firebase-uid-blank", "")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIsNone(seeded.firebaseUid)

    def test_unknown_uid_with_no_email_raises_404(self):
        seed_user(self.db)

        with self.assertRaises(HTTPException) as ctx:
            self.service.get_by_firebase_claims("firebase-uid-unlinked", None)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_list_users_returns_every_seeded_user(self):
        seed_user(self.db, userId="u-1", email="amy@connectsphere.com")
        seed_user(self.db, userId="u-2", email="ben@connectsphere.com", userName="Ben")

        users = self.service.list_users()

        self.assertEqual({user.userId for user in users}, {"u-1", "u-2"})

    def test_user_public_reads_an_organisation_member(self):
        self.db.add(Organisation(organisationId="org-1", name="ConnectSphere"))
        self.db.commit()
        seed_user(self.db, organisationId="org-1")

        public = UserPublic.model_validate(self.service.list_users()[0])

        self.assertEqual(public.organisationId, "org-1")
        self.assertEqual(public.userName, "Amy Wong")
