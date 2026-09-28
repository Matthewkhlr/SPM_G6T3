from app.models.user import User


def seed_user(db, **overrides):
    data = dict(
        userId="u-1",
        email="amy@connectsphere.com",
        userName="Amy Wong",
        role="organiser",
        firebaseUid=None,
    )
    data.update(overrides)
    user = User(**data)
    db.add(user)
    db.commit()
    return user
