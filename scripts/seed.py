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
    "event": "mysql+pymysql://connectsphere:connectsphere@localhost:3307/event",
    "venue": "mysql+pymysql://connectsphere:connectsphere@localhost:3307/venue",
    "equipment": "mysql+pymysql://connectsphere:connectsphere@localhost:3307/equipment",
    "registration": "mysql+pymysql://connectsphere:connectsphere@localhost:3307/registration",
    "notification": "mysql+pymysql://connectsphere:connectsphere@localhost:3307/notification",
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
        for org_id, name in (
            ("org-1", "Apex Partners"),
            ("org-2", "Beacon Media"),
            ("org-3", "Solo Studio"),
        ):
            existing_org = conn.execute(
                text("SELECT organisation_id FROM organisations WHERE organisation_id = :id"),
                {"id": org_id},
            ).first()
            if not existing_org:
                conn.execute(
                    text(
                        "INSERT INTO organisations (organisation_id, name, created_at) "
                        "VALUES (:id, :name, :created_at)"
                    ),
                    {"id": org_id, "name": name, "created_at": now},
                )

        users = [
            ("u1", "organiser@connectsphere.com", "Alice Tan", "organiser", "org-1", None, "organiser123"),
            ("u7", "organiser2@connectsphere.com", "Dana Koh", "organiser", "org-2", None, "organiser456"),
            ("u8", "organiser3@connectsphere.com", "Evan Ng", "organiser", "org-1", None, "organiser789"),
            ("u9", "organiser4@connectsphere.com", "Fay Lim", "organiser", "org-3", None, "organiser000"),
            ("u10", "attendee2@connectsphere.com", "Gwen Ong", "attendee", None, None, "attend456"),
            ("u2", "coordinator@connectsphere.com", "Ben Lee", "coordinator", None, "Events", "coord123"),
            ("u6", "coordinator2@connectsphere.com", "Cara Ng", "coordinator", None, "Events", "coord456"),
            ("u3", "venue@connectsphere.com", "Vinod Kumar", "venue", None, "Venues", "venue123"),
            ("u11", "venue2@connectsphere.com", "Vera Lim", "venue", None, "Venues", "venue456"),
            ("u4", "tech@connectsphere.com", "Tia Ho", "techsupport", None, "Technical Support", "tech123"),
            ("u12", "tech2@connectsphere.com", "Tom Teo", "techsupport", None, "Technical Support", "tech456"),
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


def _insert_event(conn, row: dict, now: datetime, assign_coordinator: bool = True) -> None:
    row = {**row, "created_at": now, "updated_at": now}
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
    if assign_coordinator:
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
            "changed_by": row["organiser_id"],
            "note": "Seeded demo status",
            "created_at": now,
        },
    )


def seed_event() -> None:
    engine = create_engine(URLS["event"])
    now = datetime.utcnow()
    day = timedelta(days=1)
    foreign_event = {
        "event_id": "e5",
        "organiser_id": "u7",
        "organisation_id": "org-2",
        "coordinator_id": None,
        "name": "Beacon Q4 Showcase",
        "purpose": "Private planning for Beacon Media.",
        "description": "Internal client showcase. Must stay invisible to Apex organisers.",
        "category": "meeting",
        "proposed_start_at": now + 18 * day,
        "proposed_end_at": now + 18 * day + timedelta(hours=3),
        "expected_attendance": 30,
        "venue_requirements": "Boardroom.",
        "accessibility_needs": "",
        "equipment_requirements": "Video-conferencing.",
        "layout_preference": "Boardroom",
        "registration_enabled": True,
        "registration_opens_at": now - 1 * day,
        "registration_closes_at": now + 10 * day,
        "capacity": 40,
        "status": "confirmed",
        "submitted_at": now - 6 * day,
    }
    with engine.begin() as conn:
        if _empty(conn, "events"):
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
                _insert_event(conn, row, now)
        if not conn.execute(text("SELECT event_id FROM events WHERE event_id = 'e5'")).first():
            _insert_event(conn, foreign_event, now, assign_coordinator=False)
        if not conn.execute(text("SELECT event_id FROM events WHERE event_id = 'e6'")).first():
            _insert_event(
                conn,
                {
                    "event_id": "e6",
                    "organiser_id": "u1",
                    "organisation_id": "org-1",
                    "coordinator_id": None,
                    "name": "Unassigned Client Brief",
                    "purpose": "Waiting for a coordinator to pick it up.",
                    "description": "Submitted request with no coordinator yet.",
                    "category": "meeting",
                    "proposed_start_at": now + 10 * day,
                    "proposed_end_at": now + 10 * day + timedelta(hours=2),
                    "expected_attendance": 16,
                    "venue_requirements": "Boardroom.",
                    "accessibility_needs": "",
                    "equipment_requirements": "",
                    "layout_preference": "Boardroom",
                    "registration_enabled": False,
                    "registration_opens_at": None,
                    "registration_closes_at": None,
                    "capacity": 20,
                    "status": "submitted",
                    "submitted_at": now - 3 * day,
                },
                now,
                assign_coordinator=False,
            )
        _ensure_change_requests(conn, now, day)
        if not conn.execute(text("SELECT event_id FROM events WHERE event_id = 'e7'")).first():
            _insert_event(
                conn,
                {
                    "event_id": "e7",
                    "organiser_id": "u8",
                    "organisation_id": "org-1",
                    "coordinator_id": "u2",
                    "name": "Colleague Town Hall",
                    "purpose": "Created by a colleague in Apex Partners.",
                    "description": "Must appear on EO-01's organiser dashboard.",
                    "category": "meeting",
                    "proposed_start_at": now + 12 * day,
                    "proposed_end_at": now + 12 * day + timedelta(hours=2),
                    "expected_attendance": 40,
                    "venue_requirements": "Theatre.",
                    "accessibility_needs": "",
                    "equipment_requirements": "",
                    "layout_preference": "Theatre",
                    "registration_enabled": False,
                    "registration_opens_at": None,
                    "registration_closes_at": None,
                    "capacity": 40,
                    "status": "confirmed",
                    "submitted_at": now - 4 * day,
                },
                now,
            )
        if not conn.execute(text("SELECT event_id FROM events WHERE event_id = 'e8'")).first():
            _insert_event(
                conn,
                {
                    "event_id": "e8",
                    "organiser_id": "u1",
                    "organisation_id": "org-1",
                    "coordinator_id": "u2",
                    "name": "Cancelled Briefing",
                    "purpose": "Cancelled after registrations were taken.",
                    "description": "Attendees who registered must see this as cancelled.",
                    "category": "meeting",
                    "proposed_start_at": now + 8 * day,
                    "proposed_end_at": now + 8 * day + timedelta(hours=1),
                    "expected_attendance": 10,
                    "venue_requirements": "",
                    "accessibility_needs": "",
                    "equipment_requirements": "",
                    "layout_preference": None,
                    "registration_enabled": False,
                    "registration_opens_at": None,
                    "registration_closes_at": None,
                    "capacity": 10,
                    "status": "cancelled",
                    "submitted_at": now - 9 * day,
                },
                now,
            )
        if not conn.execute(text("SELECT review_id FROM event_reviews WHERE review_id = 'rv-clarify-e3'")).first():
            conn.execute(
                text(
                    "INSERT INTO event_reviews (review_id, event_id, reviewer_id, action, comment, created_at) "
                    "VALUES ('rv-clarify-e3', 'e3', 'u2', 'request_clarification', "
                    "'Please confirm expected attendance.', :created_at)"
                ),
                {"created_at": now - 1 * day},
            )


def _ensure_change_requests(conn, now: datetime, day: timedelta) -> None:
    rows = [
        {
            "change_request_id": "cr-old",
            "event_id": "e1",
            "requested_by": "u1",
            "status": "pending",
            "summary": "Old date change",
            "proposed_changes": json.dumps({"proposedStartAt": "shifted earlier"}),
            "affects_venue": False,
            "affects_equipment": False,
            "affects_registration": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now - 5 * day,
        },
        {
            "change_request_id": "cr-new",
            "event_id": "e1",
            "requested_by": "u1",
            "status": "pending",
            "summary": "New AV change",
            "proposed_changes": json.dumps({"equipmentRequirements": "extra handheld mics"}),
            "affects_venue": False,
            "affects_equipment": True,
            "affects_registration": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now - timedelta(hours=1),
        },
        {
            "change_request_id": "cr-reverify",
            "event_id": "e2",
            "requested_by": "u1",
            "status": "applied",
            "summary": "Venue date moved",
            "proposed_changes": json.dumps({"proposedStartAt": "moved by two hours"}),
            "affects_venue": True,
            "affects_equipment": False,
            "affects_registration": False,
            "reviewed_by": "u2",
            "reviewed_at": now - 1 * day,
            "created_at": now - 2 * day,
        },
        {
            "change_request_id": "cr-eq-reverify",
            "event_id": "e2",
            "requested_by": "u1",
            "status": "applied",
            "summary": "Equipment window moved",
            "proposed_changes": json.dumps({"proposedStartAt": "moved with the venue"}),
            "affects_venue": False,
            "affects_equipment": True,
            "affects_registration": True,
            "reviewed_by": "u2",
            "reviewed_at": now - 1 * day,
            "created_at": now - 2 * day,
        },
    ]
    for row in rows:
        if conn.execute(
            text("SELECT change_request_id FROM event_change_requests WHERE change_request_id = :id"),
            {"id": row["change_request_id"]},
        ).first():
            continue
        conn.execute(
            text(
                "INSERT INTO event_change_requests ("
                "change_request_id, event_id, requested_by, status, summary, proposed_changes, "
                "affects_venue, affects_equipment, affects_registration, reviewed_by, reviewed_at, created_at"
                ") VALUES ("
                ":change_request_id, :event_id, :requested_by, :status, :summary, :proposed_changes, "
                ":affects_venue, :affects_equipment, :affects_registration, :reviewed_by, :reviewed_at, :created_at"
                ")"
            ),
            row,
        )


def _hours(days: list[str], opens: str, closes: str) -> list[dict]:
    return [{"day": d, "opens": opens, "closes": closes} for d in days]


def _layouts(pairs: list[tuple[str, int]]) -> list[dict]:
    return [{"name": name, "capacity": cap} for name, cap in pairs]


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
ALL_DAYS = WEEKDAYS + ["Sat", "Sun"]


def _ensure_venue_bookings(conn, now: datetime, day: timedelta) -> None:
    soon_start = now + 2 * day
    soon_end = soon_start + timedelta(hours=8)
    later_start = now + 14 * day
    later_end = later_start + timedelta(hours=8)
    rows = [
        {
            "booking_id": "vb-pending",
            "venue_id": "v1",
            "event_id": "e1",
            "requested_by": "u2",
            "status": "pending",
            "starts_at": later_start,
            "ends_at": later_end,
            "setup_starts_at": later_start - timedelta(hours=1),
            "teardown_ends_at": later_end + timedelta(hours=1),
            "requirements_snapshot": "Pending decision for AI in Events Summit",
            "decision_reason": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now - 1 * day,
        },
        {
            "booking_id": "vb-soon",
            "venue_id": "v1",
            "event_id": "e1",
            "requested_by": "u2",
            "status": "approved",
            "starts_at": soon_start,
            "ends_at": soon_end,
            "setup_starts_at": soon_start - timedelta(hours=1),
            "teardown_ends_at": soon_end + timedelta(hours=1),
            "requirements_snapshot": "Confirmed setup in the next few days",
            "decision_reason": "Available",
            "reviewed_by": "u3",
            "reviewed_at": now - timedelta(hours=2),
            "created_at": now - 3 * day,
        },
        {
            "booking_id": "vb-reverify",
            "venue_id": "v1",
            "event_id": "e2",
            "requested_by": "u2",
            "status": "approved",
            "starts_at": now + 21 * day,
            "ends_at": now + 21 * day + timedelta(hours=4),
            "setup_starts_at": now + 21 * day - timedelta(hours=1),
            "teardown_ends_at": now + 21 * day + timedelta(hours=5),
            "requirements_snapshot": "Needs re-verification after venue date move",
            "decision_reason": "Originally approved",
            "reviewed_by": "u3",
            "reviewed_at": now - 4 * day,
            "created_at": now - 5 * day,
        },
    ]
    for row in rows:
        if conn.execute(
            text("SELECT booking_id FROM venue_bookings WHERE booking_id = :id"),
            {"id": row["booking_id"]},
        ).first():
            continue
        conn.execute(
            text(
                "INSERT INTO venue_bookings ("
                "booking_id, venue_id, event_id, requested_by, status, starts_at, ends_at, "
                "setup_starts_at, teardown_ends_at, requirements_snapshot, decision_reason, "
                "reviewed_by, reviewed_at, created_at"
                ") VALUES ("
                ":booking_id, :venue_id, :event_id, :requested_by, :status, :starts_at, :ends_at, "
                ":setup_starts_at, :teardown_ends_at, :requirements_snapshot, :decision_reason, "
                ":reviewed_by, :reviewed_at, :created_at"
                ")"
            ),
            row,
        )


def seed_venue() -> None:
    engine = create_engine(URLS["venue"])
    now = datetime.utcnow()
    day = timedelta(days=1)
    with engine.begin() as conn:
        if _empty(conn, "venues"):
            # "location" is the building/complex name, "address" is the full
            # street address with postal code, and "floor" is separate again --
            # three distinct fields, not the same string repeated three times.
            venues = [
            (
                "v1", "MH-A", "Marina Hall A", "HarbourFront Centre",
                "1 HarbourFront Walk, Singapore 098585", "2",
                "ConnectSphere's largest multipurpose hall.",
                ["Projector", "PA system", "Video-conferencing", "Stage"],
                ["Wheelchair accessible", "Accessible restrooms nearby"],
                _layouts([("Theatre", 300), ("Classroom", 180), ("Banquet", 220)]),
                _hours(ALL_DAYS, "08:00", "22:00"),
                60,
            ),
            (
                "v2", "RS-204", "Riverside Room 204", "HarbourFront Centre",
                "1 HarbourFront Walk, Singapore 098585", "2",
                "Mid-sized meeting room.",
                ["Projector", "Whiteboard"],
                ["Wheelchair accessible"],
                _layouts([("Boardroom", 20), ("Classroom", 80)]),
                _hours(WEEKDAYS + ["Sat"], "08:00", "20:00"),
                30,
            ),
            (
                "v3", "EH-B", "Exhibition Hall B", "Suntec Singapore Convention & Exhibition Centre",
                "1 Raffles Boulevard, Singapore 039593", "1",
                "Large exhibition space with loading dock access.",
                ["Loading dock", "PA system", "Booth power points"],
                ["Wheelchair accessible", "Accessible restrooms nearby"],
                _layouts([("Exhibition", 500), ("Theatre", 350)]),
                _hours(ALL_DAYS, "07:00", "23:00"),
                120,
            ),
            (
                "v4", "SB-18", "Skyline Boardroom", "One Raffles Place",
                "1 Raffles Place, Singapore 048616", "18",
                "Executive boardroom with skyline views.",
                ["Video-conferencing", "Smart TV"],
                ["Wheelchair accessible"],
                _layouts([("Boardroom", 20)]),
                _hours(WEEKDAYS, "08:00", "18:00"),
                15,
            ),
            ]
            for row in venues:
                conn.execute(
                    text(
                        "INSERT INTO venues (venue_id, code, name, location, address, floor, description, "
                        "facilities, accessibility, layouts, operating_hours, turnaround_minutes, "
                        "is_active, created_at) VALUES ("
                        ":venue_id, :code, :name, :location, :address, :floor, :description, "
                        ":facilities, :accessibility, :layouts, :operating_hours, :turnaround_minutes, 1, "
                        ":created_at)"
                    ),
                    {
                        "venue_id": row[0],
                        "code": row[1],
                        "name": row[2],
                        "location": row[3],
                        "address": row[4],
                        "floor": row[5],
                        "description": row[6],
                        "facilities": json.dumps(row[7]),
                        "accessibility": json.dumps(row[8]),
                        "layouts": json.dumps(row[9]),
                        "operating_hours": json.dumps(row[10]),
                        "turnaround_minutes": row[11],
                        "created_at": now,
                    },
                )
        _ensure_venue_bookings(conn, now, day)


def _ensure_equipment_requests(conn, now: datetime, day: timedelta) -> None:
    start = now + 14 * day
    end = start + timedelta(hours=8)
    requests = [
        {
            "request_id": "eq-pending",
            "event_id": "e1",
            "equipment_id": "eq1",
            "quantity": 1,
            "technical_requirements": "Pending review for AI in Events Summit",
            "requested_by": "u2",
            "status": "pending",
            "starts_at": start,
            "ends_at": end,
            "reviewed_by": None,
            "review_note": "",
            "created_at": now - 1 * day,
        },
        {
            "request_id": "eq-upcoming",
            "event_id": "e1",
            "equipment_id": "eq2",
            "quantity": 2,
            "technical_requirements": "Confirmed supply for AI in Events Summit",
            "requested_by": "u2",
            "status": "approved",
            "starts_at": start,
            "ends_at": end,
            "reviewed_by": "u4",
            "review_note": "Approved",
            "created_at": now - 6 * day,
        },
        {
            "request_id": "eq-reverify",
            "event_id": "e2",
            "equipment_id": "eq1",
            "quantity": 1,
            "technical_requirements": "Re-check after venue date move",
            "requested_by": "u2",
            "status": "approved",
            "starts_at": now + 21 * day,
            "ends_at": now + 21 * day + timedelta(hours=4),
            "reviewed_by": "u4",
            "review_note": "Needs re-verification",
            "created_at": now - 4 * day,
        },
        {
            "request_id": "eq-shortfall",
            "event_id": "e3",
            "equipment_id": "eq3",
            "quantity": 2,
            "technical_requirements": "LED wall — one unit still unavailable",
            "requested_by": "u2",
            "status": "approved",
            "starts_at": now + 30 * day,
            "ends_at": now + 30 * day + timedelta(hours=3),
            "reviewed_by": "u4",
            "review_note": "Partly fulfilled; one panel still unavailable",
            "created_at": now - 2 * day,
        },
    ]
    for row in requests:
        if conn.execute(
            text("SELECT request_id FROM equipment_requests WHERE request_id = :id"),
            {"id": row["request_id"]},
        ).first():
            continue
        conn.execute(
            text(
                "INSERT INTO equipment_requests ("
                "request_id, event_id, equipment_id, quantity, technical_requirements, requested_by, "
                "status, starts_at, ends_at, reviewed_by, review_note, created_at"
                ") VALUES ("
                ":request_id, :event_id, :equipment_id, :quantity, :technical_requirements, :requested_by, "
                ":status, :starts_at, :ends_at, :reviewed_by, :review_note, :created_at"
                ")"
            ),
            row,
        )
    reservations = [
        {
            "reservation_id": "er-e1",
            "request_id": "eq-upcoming",
            "event_id": "e1",
            "equipment_id": "eq2",
            "quantity": 2,
            "starts_at": start,
            "ends_at": end,
            "status": "active",
        },
        {
            "reservation_id": "er-e2",
            "request_id": "eq-reverify",
            "event_id": "e2",
            "equipment_id": "eq1",
            "quantity": 1,
            "starts_at": now + 21 * day,
            "ends_at": now + 21 * day + timedelta(hours=4),
            "status": "reverify",
        },
        {
            "reservation_id": "er-e3",
            "request_id": "eq-shortfall",
            "event_id": "e3",
            "equipment_id": "eq3",
            "quantity": 1,
            "starts_at": now + 30 * day,
            "ends_at": now + 30 * day + timedelta(hours=3),
            "status": "partial",
        },
    ]
    for row in reservations:
        if conn.execute(
            text("SELECT reservation_id FROM equipment_reservations WHERE reservation_id = :id"),
            {"id": row["reservation_id"]},
        ).first():
            continue
        conn.execute(
            text(
                "INSERT INTO equipment_reservations ("
                "reservation_id, request_id, event_id, equipment_id, quantity, starts_at, ends_at, status"
                ") VALUES ("
                ":reservation_id, :request_id, :event_id, :equipment_id, :quantity, :starts_at, :ends_at, :status"
                ")"
            ),
            row,
        )


def seed_equipment() -> None:
    engine = create_engine(URLS["equipment"])
    now = datetime.utcnow()
    day = timedelta(days=1)
    with engine.begin() as conn:
        if not _empty(conn, "equipment_info"):
            _ensure_equipment_requests(conn, now, day)
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
        _ensure_equipment_requests(conn, now, day)


def _ensure_registrations(conn, now: datetime, day: timedelta) -> None:
    if not conn.execute(
        text("SELECT event_id FROM registration_windows WHERE event_id = 'e8'")
    ).first():
        conn.execute(
            text(
                "INSERT INTO registration_windows (event_id, capacity, opens_at, closes_at) "
                "VALUES ('e8', 10, :opens_at, :closes_at)"
            ),
            {"opens_at": now - 10 * day, "closes_at": now - 1 * day},
        )
    rows = [
        {
            "id": "r-att-e1",
            "event_id": "e1",
            "user_id": "u5",
            "name": "Amy Wong",
            "email": "attendee@connectsphere.com",
            "status": "registered",
            "created_at": now - 4 * day,
        },
        {
            "id": "r-att-e2",
            "event_id": "e2",
            "user_id": "u5",
            "name": "Amy Wong",
            "email": "attendee@connectsphere.com",
            "status": "registered",
            "created_at": now - 8 * day,
        },
        {
            "id": "r-att-e8",
            "event_id": "e8",
            "user_id": "u5",
            "name": "Amy Wong",
            "email": "attendee@connectsphere.com",
            "status": "registered",
            "created_at": now - 7 * day,
        },
    ]
    for row in rows:
        if conn.execute(
            text(
                "SELECT attendee_registration_id FROM attendee_registrations "
                "WHERE attendee_registration_id = :id"
            ),
            {"id": row["id"]},
        ).first():
            continue
        conn.execute(
            text(
                "INSERT INTO attendee_registrations (attendee_registration_id, event_id, user_id, "
                "attendee_name, attendee_email, status, created_at, withdrawn_at) VALUES ("
                ":id, :event_id, :user_id, :name, :email, :status, :created_at, NULL)"
            ),
            row,
        )


def seed_registration() -> None:
    engine = create_engine(URLS["registration"])
    now = datetime.utcnow()
    day = timedelta(days=1)
    with engine.begin() as conn:
        if not _empty(conn, "registration_windows"):
            _ensure_registrations(conn, now, day)
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
        _ensure_registrations(conn, now, day)


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
