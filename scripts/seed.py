"""Idempotent demo data for local MySQL. Safe to re-run after migrate."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firebase_admin import auth as firebase_auth
from shared.auth.tokens import get_firebase_app

URLS = {
    "user": "mysql+pymysql://connectsphere:connectsphere@localhost:3307/user",
    "event": "mysql+pymysql://connectsphere:connectsphere@localhost:3309/event",
    "venue": "mysql+pymysql://connectsphere:connectsphere@localhost:3308/venue",
    "equipment": "mysql+pymysql://connectsphere:connectsphere@localhost:3310/equipment",
    "registration": "mysql+pymysql://connectsphere:connectsphere@localhost:3311/registration",
    "notification": "mysql+pymysql://connectsphere:connectsphere@localhost:3312/notification",
}


def _empty(conn, table: str) -> bool:
    return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == 0


def _ensure_firebase_user(email: str, password: str, display_name: str) -> str:
    """Create the Firebase Auth account for a demo user, or fetch it if it already exists."""
    app = get_firebase_app()
    try:
        record = firebase_auth.create_user(
            email=email, password=password, display_name=display_name, app=app
        )
    except firebase_auth.EmailAlreadyExistsError:
        record = firebase_auth.get_user_by_email(email, app=app)
    return record.uid


def seed_user() -> None:
    engine = create_engine(URLS["user"])
    now = datetime.utcnow()
    with engine.begin() as conn:
        if _empty(conn, "organisations"):
            conn.execute(
                text(
                    "INSERT INTO organisations (organisation_id, name, created_at) "
                    "VALUES (:id, :name, :created_at)"
                ),
                {"id": "org-1", "name": "Apex Partners", "created_at": now},
            )

        users = [
            ("u1", "organiser@connectsphere.com", "Alice Tan", "organiser", "org-1", None, "organiser123"),
            ("u2", "coordinator@connectsphere.com", "Ben Lee", "coordinator", None, "Events", "coord123"),
            ("u3", "venue@connectsphere.com", "Vinod Kumar", "venue", None, "Venues", "venue123"),
            ("u4", "tech@connectsphere.com", "Tia Ho", "techsupport", None, "Technical Support", "tech123"),
            ("u5", "attendee@connectsphere.com", "Amy Wong", "attendee", None, None, "attend123"),
        ]
        for user_id, email, name, role, org_id, department, password in users:
            firebase_uid = _ensure_firebase_user(email, password, name)
            existing = conn.execute(
                text("SELECT user_id FROM users WHERE email = :email"), {"email": email}
            ).first()
            if existing:
                conn.execute(
                    text("UPDATE users SET firebase_uid = :firebase_uid WHERE email = :email"),
                    {"firebase_uid": firebase_uid, "email": email},
                )
                continue
            conn.execute(
                text(
                    "INSERT INTO users (user_id, email, display_name, role, organisation_id, "
                    "department, phone, communication_preferences, firebase_uid, "
                    "created_at, updated_at) VALUES (:user_id, :email, :display_name, :role, "
                    ":organisation_id, :department, NULL, NULL, :firebase_uid, "
                    ":created_at, :updated_at)"
                ),
                {
                    "user_id": user_id,
                    "email": email,
                    "display_name": name,
                    "role": role,
                    "organisation_id": org_id,
                    "department": department,
                    "firebase_uid": firebase_uid,
                    "created_at": now,
                    "updated_at": now,
                },
            )


def seed_event() -> None:
    engine = create_engine(URLS["event"])
    now = datetime.utcnow()
    day = timedelta(days=1)
    with engine.begin() as conn:
        if not _empty(conn, "events"):
            return
        rows = [
            {
                "event_id": "e1",
                "organiser_id": "u1",
                "organisation_id": "org-1",
                "coordinator_id": "u2",
                "name": "AI in Events Summit",
                "purpose": "Share AI practices for event operations.",
                "description": "A one-day summit for ConnectSphere clients.",
                "category": "conference",
                "proposed_start_at": now + 14 * day,
                "proposed_end_at": now + 14 * day + timedelta(hours=8),
                "expected_attendance": 120,
                "venue_requirements": "Large hall with stage and video-conferencing.",
                "accessibility_needs": "Wheelchair access required.",
                "equipment_requirements": "Projector and PA system.",
                "layout_preference": "Theatre",
                "registration_enabled": True,
                "registration_opens_at": now - 5 * day,
                "registration_closes_at": now + 3 * day,
                "capacity": 3,
                "status": "confirmed",
                "submitted_at": now - 20 * day,
            },
            {
                "event_id": "e2",
                "organiser_id": "u1",
                "organisation_id": "org-1",
                "coordinator_id": "u2",
                "name": "Venue Ops Workshop",
                "purpose": "Train venue staff on turnaround procedures.",
                "description": "Hands-on workshop.",
                "category": "workshop",
                "proposed_start_at": now + 21 * day,
                "proposed_end_at": now + 21 * day + timedelta(hours=4),
                "expected_attendance": 40,
                "venue_requirements": "Classroom layout.",
                "accessibility_needs": "Wheelchair access required.",
                "equipment_requirements": "Whiteboard and projector.",
                "layout_preference": "Classroom",
                "registration_enabled": True,
                "registration_opens_at": now - 2 * day,
                "registration_closes_at": now + 10 * day,
                "capacity": 2,
                "status": "confirmed",
                "submitted_at": now - 15 * day,
            },
            {
                "event_id": "e3",
                "organiser_id": "u1",
                "organisation_id": "org-1",
                "coordinator_id": "u2",
                "name": "Partner Networking Night",
                "purpose": "Informal networking for partner organisations.",
                "description": "Evening reception. Registration not yet enabled.",
                "category": "networking",
                "proposed_start_at": now + 30 * day,
                "proposed_end_at": now + 30 * day + timedelta(hours=3),
                "expected_attendance": 80,
                "venue_requirements": "Banquet layout.",
                "accessibility_needs": "",
                "equipment_requirements": "PA system.",
                "layout_preference": "Banquet",
                "registration_enabled": False,
                "registration_opens_at": now + 4 * day,
                "registration_closes_at": now + 14 * day,
                "capacity": 100,
                "status": "planning",
                "submitted_at": now - 5 * day,
            },
            {
                "event_id": "e4",
                "organiser_id": "u1",
                "organisation_id": "org-1",
                "coordinator_id": "u2",
                "name": "Q1 Client Briefing",
                "purpose": "Quarterly briefing for Apex Partners.",
                "description": "Registration opens in the future.",
                "category": "meeting",
                "proposed_start_at": now + 45 * day,
                "proposed_end_at": now + 45 * day + timedelta(hours=2),
                "expected_attendance": 20,
                "venue_requirements": "Boardroom.",
                "accessibility_needs": "Wheelchair access required.",
                "equipment_requirements": "Video-conferencing.",
                "layout_preference": "Boardroom",
                "registration_enabled": True,
                "registration_opens_at": now + 2 * day,
                "registration_closes_at": now + 20 * day,
                "capacity": 50,
                "status": "confirmed",
                "submitted_at": now - 8 * day,
            },
        ]
        for row in rows:
            row["created_at"] = now
            row["updated_at"] = now
            conn.execute(
                text(
                    "INSERT INTO events (event_id, organiser_id, organisation_id, coordinator_id, name, "
                    "purpose, description, category, proposed_start_at, proposed_end_at, expected_attendance, "
                    "venue_requirements, accessibility_needs, equipment_requirements, layout_preference, "
                    "registration_enabled, registration_opens_at, registration_closes_at, capacity, status, "
                    "submitted_at, created_at, updated_at) VALUES ("
                    ":event_id, :organiser_id, :organisation_id, :coordinator_id, :name, :purpose, "
                    ":description, :category, :proposed_start_at, :proposed_end_at, :expected_attendance, "
                    ":venue_requirements, :accessibility_needs, :equipment_requirements, :layout_preference, "
                    ":registration_enabled, :registration_opens_at, :registration_closes_at, :capacity, "
                    ":status, :submitted_at, :created_at, :updated_at)"
                ),
                row,
            )
            conn.execute(
                text(
                    "INSERT INTO event_assignments (assignment_id, event_id, coordinator_id, assigned_by, assigned_at) "
                    "VALUES (:assignment_id, :event_id, :coordinator_id, :assigned_by, :assigned_at)"
                ),
                {
                    "assignment_id": f"asgn-{row['event_id']}",
                    "event_id": row["event_id"],
                    "coordinator_id": "u2",
                    "assigned_by": "u2",
                    "assigned_at": row["submitted_at"],
                },
            )
            conn.execute(
                text(
                    "INSERT INTO event_status_history (history_id, event_id, from_status, to_status, "
                    "changed_by, note, created_at) VALUES (:history_id, :event_id, :from_status, :to_status, "
                    ":changed_by, :note, :created_at)"
                ),
                {
                    "history_id": f"hist-{row['event_id']}",
                    "event_id": row["event_id"],
                    "from_status": "submitted",
                    "to_status": row["status"],
                    "changed_by": "u2",
                    "note": "Seeded demo status",
                    "created_at": now,
                },
            )


def seed_venue() -> None:
    engine = create_engine(URLS["venue"])
    now = datetime.utcnow()
    with engine.begin() as conn:
        if not _empty(conn, "venues"):
            return
        venues = [
            (
                "v1",
                "Marina Hall A",
                "3 Harbourfront Ave, Level 2",
                300,
                ["Projector", "PA system", "Video-conferencing", "Stage"],
                "Wheelchair accessible, accessible restrooms nearby",
                ["Theatre", "Classroom", "Banquet"],
                "Mon–Sun, 8:00 AM – 10:00 PM",
                60,
            ),
            (
                "v2",
                "Riverside Room 204",
                "3 Harbourfront Ave, Level 2",
                80,
                ["Projector", "Whiteboard"],
                "Wheelchair accessible",
                ["Boardroom", "Classroom"],
                "Mon–Sat, 8:00 AM – 8:00 PM",
                30,
            ),
            (
                "v3",
                "Exhibition Hall B",
                "12 Convention Way",
                500,
                ["Loading dock", "PA system", "Booth power points"],
                "Wheelchair accessible, accessible restrooms nearby",
                ["Exhibition", "Theatre"],
                "Mon–Sun, 7:00 AM – 11:00 PM",
                120,
            ),
            (
                "v4",
                "Skyline Boardroom",
                "3 Harbourfront Ave, Level 18",
                20,
                ["Video-conferencing", "Smart TV"],
                "Wheelchair accessible",
                ["Boardroom"],
                "Mon–Fri, 8:00 AM – 6:00 PM",
                15,
            ),
        ]
        for row in venues:
            conn.execute(
                text(
                    "INSERT INTO venues (venue_id, name, location, capacity, facilities, accessibility, "
                    "layouts, operating_hours, turnaround_minutes, is_active, created_at) VALUES ("
                    ":venue_id, :name, :location, :capacity, :facilities, :accessibility, :layouts, "
                    ":operating_hours, :turnaround_minutes, 1, :created_at)"
                ),
                {
                    "venue_id": row[0],
                    "name": row[1],
                    "location": row[2],
                    "capacity": row[3],
                    "facilities": json.dumps(row[4]),
                    "accessibility": row[5],
                    "layouts": json.dumps(row[6]),
                    "operating_hours": row[7],
                    "turnaround_minutes": row[8],
                    "created_at": now,
                },
            )


def seed_equipment() -> None:
    engine = create_engine(URLS["equipment"])
    with engine.begin() as conn:
        if not _empty(conn, "equipment_info"):
            return
        items = [
            ("eq1", "Projector PX-200", "display", "Includes HDMI + VGA adapters", "Marina Hall store", 4),
            ("eq2", "Wireless mic set", "audio", "Fully booked Thursday in the demo calendar", "Riverside store", 6),
            ("eq3", "LED wall panel", "display", "One unit flagged unavailable", "Exhibition store", 2),
        ]
        for equipment_id, name, category, description, location, qty in items:
            conn.execute(
                text(
                    "INSERT INTO equipment_info (equipment_id, name, category, description, location, total_quantity) "
                    "VALUES (:equipment_id, :name, :category, :description, :location, :total_quantity)"
                ),
                {
                    "equipment_id": equipment_id,
                    "name": name,
                    "category": category,
                    "description": description,
                    "location": location,
                    "total_quantity": qty,
                },
            )
        units = [
            ("u-eq1", "eq1", "available"),
            ("u-eq2", "eq2", "available"),
            ("u-eq3", "eq3", "maintenance"),
        ]
        for unit_id, equipment_id, status in units:
            conn.execute(
                text(
                    "INSERT INTO equipment_units (unit_id, equipment_id, status) "
                    "VALUES (:unit_id, :equipment_id, :status)"
                ),
                {"unit_id": unit_id, "equipment_id": equipment_id, "status": status},
            )


def seed_registration() -> None:
    engine = create_engine(URLS["registration"])
    now = datetime.utcnow()
    day = timedelta(days=1)
    with engine.begin() as conn:
        if not _empty(conn, "registration_windows"):
            return
        windows = [
            ("e1", 3, now - 5 * day, now + 3 * day),
            ("e2", 2, now - 2 * day, now + 10 * day),
            ("e4", 50, now + 2 * day, now + 20 * day),
        ]
        for event_id, capacity, opens_at, closes_at in windows:
            conn.execute(
                text(
                    "INSERT INTO registration_windows (event_id, capacity, opens_at, closes_at) "
                    "VALUES (:event_id, :capacity, :opens_at, :closes_at)"
                ),
                {
                    "event_id": event_id,
                    "capacity": capacity,
                    "opens_at": opens_at,
                    "closes_at": closes_at,
                },
            )
        attendees = [
            ("r1", "e1", "Demo Attendee", "one@example.com"),
            ("r2", "e2", "Full One", "full1@example.com"),
            ("r3", "e2", "Full Two", "full2@example.com"),
        ]
        for attendee_id, event_id, name, email in attendees:
            conn.execute(
                text(
                    "INSERT INTO attendee_registrations (attendee_registration_id, event_id, user_id, "
                    "attendee_name, attendee_email, status, created_at, withdrawn_at) VALUES ("
                    ":id, :event_id, NULL, :name, :email, 'registered', :created_at, NULL)"
                ),
                {
                    "id": attendee_id,
                    "event_id": event_id,
                    "name": name,
                    "email": email,
                    "created_at": now,
                },
            )


def seed_notification() -> None:
    engine = create_engine(URLS["notification"])
    now = datetime.utcnow()
    with engine.begin() as conn:
        if not _empty(conn, "notifications"):
            return
        conn.execute(
            text(
                "INSERT INTO notifications (notification_id, user_id, event_id, type, title, body, is_read, created_at) "
                "VALUES (:id, :user_id, :event_id, :type, :title, :body, 0, :created_at)"
            ),
            {
                "id": "n1",
                "user_id": "u1",
                "event_id": "e1",
                "type": "event_confirmed",
                "title": "AI in Events Summit is confirmed",
                "body": "Your event has been confirmed. Registration is open.",
                "created_at": now,
            },
        )


def seed_all() -> None:
    seed_user()
    seed_event()
    seed_venue()
    seed_equipment()
    seed_registration()
    seed_notification()


if __name__ == "__main__":
    seed_all()
    print("seed complete")
