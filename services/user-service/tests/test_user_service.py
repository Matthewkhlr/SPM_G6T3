import pytest
from fastapi import HTTPException

from app.models.user import User


def seed_user(db_session, **overrides):
    defaults = dict(
        userId="u-1",
        email="amy@connectsphere.com",
        userName="Amy Wong",
        role="organiser",
        firebaseUid=None,
    )
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    db_session.commit()
    return user


def test_first_login_links_firebase_uid_by_email(user_service, db_session):
    seed_user(db_session)

    resolved = user_service.get_by_firebase_claims("firebase-uid-1", "amy@connectsphere.com")

    assert resolved.userId == "u-1"
    assert resolved.firebaseUid == "firebase-uid-1"


def test_subsequent_login_resolves_directly_by_firebase_uid(user_service, db_session):
    seed_user(db_session, firebaseUid="firebase-uid-1")

    resolved = user_service.get_by_firebase_claims("firebase-uid-1", None)

    assert resolved.userId == "u-1"


def test_unknown_email_raises_404(user_service, db_session):
    seed_user(db_session)

    with pytest.raises(HTTPException) as exc_info:
        user_service.get_by_firebase_claims("firebase-uid-2", "nobody@connectsphere.com")

    assert exc_info.value.status_code == 404


def test_unknown_uid_with_no_email_raises_404(user_service, db_session):
    seed_user(db_session)

    with pytest.raises(HTTPException) as exc_info:
        user_service.get_by_firebase_claims("firebase-uid-unlinked", None)

    assert exc_info.value.status_code == 404


def test_list_users_returns_every_seeded_user(user_service, db_session):
    seed_user(db_session, userId="u-1", email="amy@connectsphere.com")
    seed_user(db_session, userId="u-2", email="ben@connectsphere.com")

    users = user_service.list_users()

    assert {u.userId for u in users} == {"u-1", "u-2"}
