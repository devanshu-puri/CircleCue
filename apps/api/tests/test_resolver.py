"""
Resolver tests: covers MEMORY.md §5.2 precedence layers and all 5 demo workflows.
Pure function, no DB required.
"""
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.resolver import UserBundle, resolve
from app.domain.expander import expand
from app.domain.freewindows import Segment, free_in_minutes, free_windows
from app.domain.visibility import project
from app.domain.models import (
    ActivityType, Calls, Messages, Status, ProvenanceSource, TravelPhase,
    AccessLevel, CardGrants, Grant,
)

IST = ZoneInfo("Asia/Kolkata")


def _now_ist(hour: int, minute: int = 0) -> datetime:
    """Return a fixed datetime at hour:minute IST today."""
    d = datetime(2026, 10, 3, hour, minute, tzinfo=IST)
    return d.astimezone(timezone.utc)


def _bundle(**kwargs) -> UserBundle:
    defaults = dict(
        owner_id="user1",
        tz="Asia/Kolkata",
        routine_prefs={"wake": "07:00", "sleep": "23:00", "min_call_window_min": 10, "buffer_min": 5},
        sharing_paused={"active": False},
    )
    defaults.update(kwargs)
    return UserBundle(**defaults)


# ── Layer tests ────────────────────────────────────────────────────────────────

class TestLayerPrecedence:
    def test_unknown_empty_user(self):
        """Layer 8: unknown for an empty user outside routine hours."""
        now = _now_ist(2)  # 2 AM, no activities, no schedule
        state = resolve(_bundle(), now)
        # Before wake time → unknown / no activity
        assert state.owner == "user1"
        assert state.activity is None or state.activity.layer >= 7

    def test_routine_baseline_free(self):
        """Layer 7: user is free during routine hours with no schedule."""
        now = _now_ist(15)  # 3 PM, within 07:00-23:00
        state = resolve(_bundle(), now)
        assert state.activity is not None
        assert state.activity.type == ActivityType.FREE
        assert state.activity.layer == 7
        assert state.reachability.calls == Calls.OK

    def test_schedule_layer_6_class(self):
        """Layer 6: in-class from a schedule template."""
        now = _now_ist(10)  # 10:00 IST
        tmpl = {
            "_id": "t1",
            "kind": "SCHEDULE_SLOT",
            "title": "Physics Lecture",
            "activity_type": "CLASS",
            "days": [5],  # Saturday = weekday 5
            "start_local": "09:30",
            "end_local": "11:00",
            "week_pattern": "every",
            "availability": {"calls": "no", "messages": "ok"},
        }
        state = resolve(_bundle(templates=[tmpl]), now)
        assert state.activity is not None
        assert state.activity.type == ActivityType.CLASS
        assert state.activity.label == "Physics Lecture"
        assert state.activity.layer == 6
        assert state.reachability.calls == Calls.NO

    def test_schedule_preserves_prefer_not_calls(self):
        now = _now_ist(10)
        template = {
            "_id": "slot", "title": "Quiet study", "activity_type": "STUDY",
            "days": [5], "start_local": "09:30", "end_local": "11:00",
            "availability": {"calls": "prefer_not"},
        }

        state = resolve(_bundle(templates=[template]), now)

        assert state.reachability.calls == Calls.PREFER_NOT

    def test_overlapping_schedule_uses_latest_start(self, caplog):
        now = _now_ist(10, 30)
        templates = [
            {"_id": "early", "title": "Long class", "activity_type": "CLASS",
             "days": [5], "start_local": "09:00", "end_local": "12:00"},
            {"_id": "late", "title": "Lab", "activity_type": "LAB",
             "days": [5], "start_local": "10:00", "end_local": "11:00"},
        ]

        state = resolve(_bundle(templates=templates), now)

        assert state.activity.label == "Lab"
        assert state.next_boundary_at == _now_ist(11)
        assert "Overlapping schedule segments detected" in caplog.text

    def test_schedule_layer_6_free_window(self):
        """Layer 6: free window between classes (> min_window after buffer)."""
        now = _now_ist(11, 15)  # Between class end 11:00 and next at 14:00
        tmpl1 = {
            "_id": "t1", "title": "Morning Class", "activity_type": "CLASS",
            "days": [5], "start_local": "09:30", "end_local": "11:00",
            "week_pattern": "every", "availability": {"calls": "no"},
        }
        tmpl2 = {
            "_id": "t2", "title": "Afternoon Lab", "activity_type": "LAB",
            "days": [5], "start_local": "14:00", "end_local": "16:00",
            "week_pattern": "every", "availability": {"calls": "no"},
        }
        state = resolve(_bundle(templates=[tmpl1, tmpl2]), now)
        assert state.activity is not None
        assert state.activity.type == ActivityType.FREE
        assert state.reachability.calls == Calls.OK
        assert state.reachability.free_in_min is not None

    def test_manual_activity_layer_2_overrides_schedule(self):
        """Layer 2: manual STUDY overrides a schedule free window."""
        now = _now_ist(15)
        act = {
            "_id": "a1",
            "owner": "user1",
            "type": "STUDY",
            "title": "Exam prep",
            "status": Status.ACTIVE.value,
            "start_at": _now_ist(14).isoformat(),
            "expected_end_at": _now_ist(17).isoformat(),
            "availability": {"calls": "prefer_not", "messages": "ok"},
            "provenance": {"source": "user_shared"},
        }
        state = resolve(_bundle(activities=[act]), now)
        assert state.activity is not None
        assert state.activity.type == ActivityType.STUDY
        assert state.activity.layer == 2
        assert state.reachability.calls == Calls.PREFER_NOT
        assert state.next_boundary_at == _now_ist(17)

        def test_changed_live_activity_remains_resolved(self):
            now = _now_ist(15)
            activity = {
                "_id": "changed-study", "type": "STUDY", "title": "Updated study",
                "status": Status.CHANGED.value, "start_at": _now_ist(14).isoformat(),
                "expected_end_at": _now_ist(17).isoformat(),
                "provenance": {"source": "user_shared"},
            }

            state = resolve(_bundle(activities=[activity]), now)

            assert state.activity.label == "Updated study"
            assert state.activity.layer == 2

        def test_changed_travel_remains_resolved(self):
            now = _now_ist(18)
            activity = {
                "_id": "changed-trip", "type": "TRAVEL", "title": "New destination",
                "status": Status.CHANGED.value, "phase": TravelPhase.DELAYED.value,
                "start_at": _now_ist(17).isoformat(),
                "expected_end_at": _now_ist(20).isoformat(),
                "metadata": {"eta": _now_ist(20).isoformat(), "destination": "Home"},
                "provenance": {"source": "user_shared"},
            }

            state = resolve(_bundle(activities=[activity]), now)

            assert state.activity.label == "New destination"
            assert state.activity.layer == 3
    def test_private_label_survives_resolution_and_projection(self):
        now = _now_ist(15)
        activity = {
            "_id": "private-study", "owner": "user1", "type": "STUDY",
            "title": "Personal appointment", "status": Status.ACTIVE.value,
            "start_at": _now_ist(14).isoformat(),
            "expected_end_at": _now_ist(16).isoformat(),
            "visibility": {"mode": "private_label", "label_override": "Personal"},
            "provenance": {"source": "user_shared"},
        }
        grant = Grant(
            owner="user1", viewer="viewer1",
            cards=CardGrants(live=AccessLevel.DETAILS),
        )

        projected = project(resolve(_bundle(activities=[activity]), now), grant, now, "viewer1")

        assert projected.activity["label"] == "Personal"

    def test_travel_layer_3(self):
        """Layer 3: active travel overrides everything below it."""
        now = _now_ist(18)
        eta = _now_ist(19)
        act = {
            "_id": "a2",
            "owner": "user1",
            "type": "TRAVEL",
            "title": "Heading Home",
            "status": Status.ACTIVE.value,
            "phase": TravelPhase.TRAVELLING.value,
            "start_at": _now_ist(17).isoformat(),
            "expected_end_at": eta.isoformat(),
            "availability": {"calls": "prefer_not", "messages": "ok"},
            "metadata": {
                "destination": "Home",
                "destination_kind": "home",
                "eta": eta.isoformat(),
                "companions": ["Rahul"],
                "mode": "cab",
            },
            "provenance": {"source": "user_shared"},
        }
        state = resolve(_bundle(activities=[act]), now)
        assert state.activity is not None
        assert state.activity.type == ActivityType.TRAVEL
        assert state.activity.layer == 3
        assert state.travel is not None
        assert state.travel["overdue"] is False

    def test_newest_active_travel_wins_within_layer(self):
        now = _now_ist(18)
        activities = [
            {"_id": "old", "type": "TRAVEL", "title": "Old trip",
             "status": Status.ACTIVE.value, "start_at": _now_ist(16).isoformat(),
             "expected_end_at": _now_ist(20).isoformat(), "metadata": {"eta": _now_ist(20).isoformat()}},
            {"_id": "new", "type": "TRAVEL", "title": "New trip",
             "status": Status.ACTIVE.value, "start_at": _now_ist(17).isoformat(),
             "expected_end_at": _now_ist(21).isoformat(), "metadata": {"eta": _now_ist(21).isoformat()}},
        ]

        state = resolve(_bundle(activities=activities), now)

        assert state.activity.label == "New trip"

    def test_travel_overdue(self):
        """ETA in the past → travel.overdue = True."""
        now = _now_ist(20)
        eta = _now_ist(19)  # already past!
        act = {
            "_id": "a3",
            "owner": "user1",
            "type": "TRAVEL",
            "title": "Going Home",
            "status": Status.ACTIVE.value,
            "phase": TravelPhase.TRAVELLING.value,
            "start_at": _now_ist(17).isoformat(),
            "expected_end_at": _now_ist(21).isoformat(),
            "metadata": {"eta": eta.isoformat(), "destination": "Home", "mode": "cab"},
            "provenance": {"source": "user_shared"},
        }
        state = resolve(_bundle(activities=[act]), now)
        assert state.travel["overdue"] is True

    def test_expired_activity_ignored(self):
        """Expired manual activities must NOT appear — fallthrough to schedule layer."""
        now = _now_ist(15)
        expired_act = {
            "_id": "a4",
            "owner": "user1",
            "type": "STUDY",
            "title": "Old Study",
            "status": Status.ACTIVE.value,   # not yet marked expired in DB
            "start_at": _now_ist(8).isoformat(),
            "expected_end_at": _now_ist(12).isoformat(),   # ended 3h ago
            "availability": {"calls": "no"},
            "provenance": {"source": "user_shared"},
        }
        state = resolve(_bundle(activities=[expired_act]), now)
        # Expired activity should be ignored; should fall to layer 7 (routine free)
        assert state.activity is not None
        assert state.activity.type == ActivityType.FREE
        assert state.activity.layer == 7

    def test_sharing_paused_propagated(self):
        """Sharing paused flag is surfaced in ResolvedState."""
        now = _now_ist(15)
        state = resolve(_bundle(sharing_paused={"active": True, "until": None}), now)
        assert state.sharing_paused is True

    def test_expired_sharing_pause_is_ignored(self):
        now = _now_ist(15)
        state = resolve(_bundle(sharing_paused={
            "active": True,
            "until": (now - timedelta(minutes=1)).isoformat(),
        }), now)

        assert state.sharing_paused is False

    def test_active_sharing_pause_expiry_is_next_boundary(self):
        now = _now_ist(15)
        until = now + timedelta(minutes=20)
        state = resolve(_bundle(sharing_paused={
            "active": True,
            "until": until.isoformat(),
        }), now)

        assert state.sharing_paused is True
        assert state.next_boundary_at == until

    def test_demo_clock_advance(self):
        """DemoClock: advancing time transitions across a schedule boundary."""
        from app.clock import DemoClock
        tmpl = {
            "_id": "t1", "title": "Class", "activity_type": "CLASS",
            "days": [5], "start_local": "10:00", "end_local": "11:00",
            "week_pattern": "every", "availability": {"calls": "no"},
        }
        # At 09:50: free (class hasn't started)
        now_before = _now_ist(9, 50)
        state_before = resolve(_bundle(templates=[tmpl]), now_before)
        assert state_before.activity is None or state_before.activity.type != ActivityType.CLASS

        # At 10:30: in class
        now_during = _now_ist(10, 30)
        state_during = resolve(_bundle(templates=[tmpl]), now_during)
        assert state_during.activity is not None
        assert state_during.activity.type == ActivityType.CLASS

    def test_last_shared_context_and_stale_boundary(self):
        now = _now_ist(15)
        shared_at = now - timedelta(minutes=30)
        phone = {
            "updated_at": now.isoformat(),
            "last_shared_context": {
                "snapshot": {"activity": "Heading home"},
                "shared_at": shared_at.isoformat(),
            },
        }

        state = resolve(_bundle(phone_state=phone), now)

        assert state.last_shared_context.snapshot == {"activity": "Heading home"}
        assert state.last_shared_context.shared_at == shared_at
        assert state.next_boundary_at == shared_at + timedelta(hours=3)


def test_expand_applies_moved_exception():
    target_date = date(2026, 10, 3)
    segments = expand(
        templates=[{
            "_id": "slot-1", "title": "Physics", "activity_type": "CLASS",
            "days": [5], "start_local": "09:00", "end_local": "10:00",
        }],
        exceptions=[{
            "template_id": "slot-1", "date": target_date.isoformat(),
            "kind": "moved", "new_start": "10:30", "new_end": "11:30",
        }],
        exam_sets=[],
        target_date=target_date,
        tz="Asia/Kolkata",
    )

    assert len(segments) == 1
    assert segments[0].start == _now_ist(10, 30)
    assert segments[0].end == _now_ist(11, 30)


def test_expand_cross_midnight_segment():
    segments = expand(
        templates=[{
            "_id": "sleep", "title": "Sleep", "activity_type": "SLEEP",
            "days": [5], "start_local": "23:00", "end_local": "01:00",
        }],
        exceptions=[],
        exam_sets=[],
        target_date=date(2026, 10, 3),
        tz="Asia/Kolkata",
    )

    assert len(segments) == 1
    assert segments[0].end - segments[0].start == timedelta(hours=2)


@pytest.mark.parametrize(
    ("week_pattern", "active_from", "expected_count"),
    [
        ("A", None, 0),
        ("B", None, 1),
        ("every", "2026-10-04T00:00:00+05:30", 0),
    ],
)
def test_expand_week_pattern_and_active_from(week_pattern, active_from, expected_count):
    template = {
        "_id": "slot", "title": "Class", "activity_type": "CLASS",
        "days": [5], "start_local": "09:00", "end_local": "10:00",
        "week_pattern": week_pattern,
    }
    if active_from:
        template["active_from"] = active_from

    segments = expand(
        [template], [], [], date(2026, 10, 3), "Asia/Kolkata"
    )

    assert len(segments) == expected_count


@pytest.mark.parametrize(
    ("kind", "new_end", "expected_end"),
    [
        ("cancelled", None, None),
        ("extended", "11:00", "11:00"),
        ("early_end", "09:30", "09:30"),
    ],
)
def test_expand_schedule_exceptions(kind, new_end, expected_end):
    target_date = date(2026, 10, 3)
    exception = {
        "template_id": "slot", "date": target_date.isoformat(), "kind": kind,
        "new_end": new_end,
    }

    segments = expand(
        [{"_id": "slot", "title": "Class", "activity_type": "CLASS",
          "days": [5], "start_local": "09:00", "end_local": "10:00"}],
        [exception], [], target_date, "Asia/Kolkata",
    )

    if expected_end is None:
        assert segments == []
    else:
        assert segments[0].end == _now_ist(int(expected_end[:2]), int(expected_end[3:]))


def test_exam_set_overrides_schedule_for_date():
    target_date = date(2026, 10, 3)
    segments = expand(
        [{"_id": "slot", "title": "Class", "activity_type": "CLASS",
          "days": [5], "start_local": "09:00", "end_local": "10:00"}],
        [],
        [{"date": target_date.isoformat(), "items": [{
            "type": "exam", "subject": "Math", "start_local": "11:00",
            "end_local": "12:00",
        }]}],
        target_date,
        "Asia/Kolkata",
    )

    assert segments
    assert all(segment.activity_type == "EXAM" for segment in segments)


def test_resolver_keeps_cross_midnight_segment_active_next_day():
    now = datetime(2026, 10, 4, 0, 30, tzinfo=IST).astimezone(timezone.utc)
    template = {
        "_id": "sleep", "title": "Sleep", "activity_type": "SLEEP",
        "days": [5], "start_local": "23:00", "end_local": "01:00",
    }

    state = resolve(_bundle(templates=[template]), now)

    assert state.activity is not None
    assert state.activity.type == ActivityType.SLEEP


def test_exam_state_is_upcoming_before_buffer():
    now = _now_ist(9)
    exam_set = {
        "date": "2026-10-03",
        "items": [{"type": "exam", "subject": "Math", "start_local": "11:00", "end_local": "12:00"}],
    }

    state = resolve(_bundle(exam_sets=[exam_set]), now)

    assert state.exam["state"] == "upcoming"
    assert state.exam["subject"] == "Math"
    assert state.next_boundary_at == _now_ist(10, 30)


def test_exam_state_is_finished_after_post_buffer():
    now = _now_ist(13)
    exam_set = {
        "date": "2026-10-03",
        "items": [{"type": "exam", "subject": "Math", "start_local": "11:00", "end_local": "12:00"}],
    }

    state = resolve(_bundle(exam_sets=[exam_set]), now)

    assert state.exam["state"] == "finished"
    assert state.exam["exams_today"] == 1


def test_manual_study_overrides_exam_set():
    now = _now_ist(11, 15)
    activity = {
        "_id": "study", "type": "STUDY", "title": "Revision",
        "status": Status.ACTIVE.value, "start_at": _now_ist(10).isoformat(),
        "expected_end_at": _now_ist(12).isoformat(),
        "provenance": {"source": "user_shared"},
    }
    exam_set = {
        "date": "2026-10-03",
        "items": [{"type": "exam", "subject": "Math", "start_local": "11:00", "end_local": "12:00"}],
    }

    state = resolve(_bundle(activities=[activity], exam_sets=[exam_set]), now)

    assert state.activity.type == ActivityType.STUDY
    assert state.activity.layer == 2


def test_free_windows_apply_buffer_and_minimum():
    day_start = datetime(2026, 10, 3, 7, tzinfo=timezone.utc)
    day_end = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    segments = [
        Segment(
            start=day_start + timedelta(hours=1),
            end=day_start + timedelta(hours=2),
            activity_type="CLASS",
            label="Class",
            calls_ok=False,
        ),
        Segment(
            start=day_start + timedelta(hours=2, minutes=14),
            end=day_start + timedelta(hours=3),
            activity_type="LAB",
            label="Lab",
            calls_ok=False,
        ),
    ]

    windows = free_windows(segments, day_start, day_end, min_window_min=10, buffer_min=5)

    assert [(window.net_minutes, window.start) for window in windows] == [
        (55, day_start),
        (115, day_start + timedelta(hours=3)),
    ]
    assert free_in_minutes(windows, day_start + timedelta(minutes=30)) == 0
    assert free_in_minutes(windows, day_start + timedelta(hours=2, minutes=5)) == 55


# ── Demo Workflow Tests ─────────────────────────────────────────────────────────

class TestDemoWorkflows:
    """Tests matching the 5 global acceptance workflows in MASTER_PROMPT.md."""

    def test_wf1_son_in_break_mom_sees_free(self):
        """WF1: Son's timetable has a 25min break → resolver says FREE."""
        now = _now_ist(11)  # 11:00 AM IST
        # Class 09:30-11:00, Break 11:00-11:30, Class 11:30-13:00
        templates = [
            {"_id": "t1", "title": "Maths", "activity_type": "CLASS",
             "days": [5], "start_local": "09:30", "end_local": "11:00",
             "week_pattern": "every", "availability": {"calls": "no"}},
            {"_id": "t2", "title": "Break", "activity_type": "BREAK",
             "days": [5], "start_local": "11:00", "end_local": "11:30",
             "week_pattern": "every", "availability": {"calls": "ok"}},
            {"_id": "t3", "title": "Physics", "activity_type": "CLASS",
             "days": [5], "start_local": "11:30", "end_local": "13:00",
             "week_pattern": "every", "availability": {"calls": "no"}},
        ]
        state = resolve(_bundle(templates=templates), now)
        assert state.activity is not None
        assert state.activity.type == ActivityType.BREAK
        assert state.reachability.calls == Calls.OK

    def test_wf2_friend_studying_no_calls(self):
        """WF2: Friend typed 'studying till 8, no calls' → live activity with calls=NO."""
        now = _now_ist(16)
        act = {
            "_id": "a1", "owner": "user1", "type": "STUDY",
            "title": "Studying until 8 PM",
            "status": Status.ACTIVE.value,
            "start_at": _now_ist(14).isoformat(),
            "expected_end_at": _now_ist(20).isoformat(),
            "availability": {"calls": "no", "messages": "ok"},
            "provenance": {"source": "ai_parsed_user_confirmed"},
        }
        state = resolve(_bundle(activities=[act]), now)
        assert state.activity.type == ActivityType.STUDY
        assert state.reachability.calls == Calls.NO
        assert state.reachability.messages == Messages.OK

    def test_wf3_travel_with_companion_and_eta(self):
        """WF3: Going home with Rahul, battery 5%, reach in 40 min → travel state."""
        now = _now_ist(18)
        eta = _now_ist(18, 40)
        act = {
            "_id": "a2", "owner": "user1", "type": "TRAVEL",
            "title": "Going home with Rahul",
            "status": Status.ACTIVE.value,
            "phase": TravelPhase.TRAVELLING.value,
            "start_at": now.isoformat(),
            "expected_end_at": eta.isoformat(),
            "metadata": {
                "destination": "Home", "destination_kind": "home",
                "eta": eta.isoformat(), "companions": ["Rahul"], "mode": "cab",
            },
            "provenance": {"source": "ai_parsed_user_confirmed"},
        }
        phone = {
            "_id": "user1",
            "battery_pct": 5,
            "battery_bucket": "critical",
            "may_go_offline": True,
            "declared_offline": False,
            "mode": "normal",
            "updated_at": now.isoformat(),
        }
        state = resolve(_bundle(activities=[act], phone_state=phone), now)
        assert state.activity.type == ActivityType.TRAVEL
        assert state.travel["overdue"] is False
        assert "Rahul" in state.travel["companions"]
        assert state.phone["battery_bucket"] == "critical"
        assert state.phone["may_go_offline"] is True

    def test_wf4_user_becomes_free(self):
        """WF4: Activity ends → user becomes free during routine hours."""
        now = _now_ist(14)  # no active activity; within routine hours
        state = resolve(_bundle(), now)
        assert state.activity is not None
        assert state.activity.type == ActivityType.FREE
        assert state.reachability.calls == Calls.OK

    def test_wf5_friday_cricket_scenario(self):
        """WF5: Scenario produces BUSY activity → overrides schedule free window."""
        now = _now_ist(19)  # 7 PM Fri (treating Sat as Fri for demo)
        scenario_act = {
            "_id": "a5", "owner": "user1", "type": "CUSTOM",
            "title": "Cricket",
            "status": Status.ACTIVE.value,
            "start_at": _now_ist(19).isoformat(),
            "expected_end_at": _now_ist(22).isoformat(),
            "availability": {"calls": "no", "messages": "later"},
            "provenance": {"source": "system_inferred"},   # scenario-produced
        }
        state = resolve(_bundle(activities=[scenario_act]), now)
        assert state.activity.layer == 5
        assert state.activity.type == ActivityType.CUSTOM
        assert state.reachability.calls == Calls.NO

    def test_time_scenario_resolves_without_activity_record(self):
        now = _now_ist(20)
        scenario = {
            "_id": "friday-cricket",
            "owner": "user1",
            "name": "Friday cricket",
            "enabled": True,
            "priority": 50,
            "trigger": {
                "kind": "time",
                "days": [5],
                "start_local": "19:00",
                "end_local": "22:00",
                "week_pattern": "every",
            },
            "effects": [{
                "kind": "set_activity",
                "activity_type": "CUSTOM",
                "title": "Cricket",
                "availability": {"calls": "no", "messages": "later"},
            }],
        }

        state = resolve(_bundle(scenarios=[scenario]), now)

        assert state.activity.type == ActivityType.CUSTOM
        assert state.activity.label == "Cricket"
        assert state.activity.layer == 5
        assert state.reachability.calls == Calls.NO
