"""Replay tests for the deterministic pre-signal state machine.

No live market data is used: every test drives the machine with a constructed
evidence sequence and a fake clock, so the hysteresis behaviour is exact.
"""

from __future__ import annotations

import pytest

from bitcoin_cycle_analyzer.short_term.presignal_state import (
    BUILD_UP_GROUPS,
    Evidence,
    PreSignalStateMachine,
    classify,
)


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def tick(self, seconds: float = 1.0) -> None:
        self.now += seconds


def machine() -> tuple[PreSignalStateMachine, FakeClock]:
    clock = FakeClock()
    return PreSignalStateMachine(clock=clock), clock


CALM = Evidence(setup_state="NEUTRAL", direction="NEUTRAL", pressure=0.0, flow_agreement="NEUTRAL")

WATCHING = Evidence(setup_state="WATCH", direction="SHORT", pressure=40.0, flow_agreement="NEUTRAL")

BUILDING = Evidence(
    setup_state="WATCH",
    direction="SHORT",
    pressure=60.0,
    flow_agreement="NEUTRAL",
    return_60s=-0.0009,
    range_expansion=1.9,
)

NEARLY = Evidence(
    setup_state="ARMED",
    direction="SHORT",
    pressure=70.0,
    flow_agreement="CONFIRMED",
    l2_aligned=None,  # the one missing condition
    return_60s=-0.0012,
    range_expansion=2.0,
)

TEST_SIGNAL = Evidence(
    setup_state="SIGNAL",
    direction="SHORT",
    pressure=80.0,
    flow_agreement="CONFIRMED",
    l2_aligned=True,
    return_60s=-0.0015,
    range_expansion=2.2,
    v5_3_candidate_age_s=4.0,
    v5_3_candidate_accepted=True,
)


def drive(sm: PreSignalStateMachine, clock: FakeClock, evidence: Evidence, count: int) -> dict:
    result: dict = {}
    for _ in range(count):
        result = sm.update(evidence)
        clock.tick(1.0)
    return result


# --------------------------------------------------------------- raw classifier


def test_classify_maps_evidence_to_the_expected_raw_states():
    assert classify(CALM)[0] == "RUHIG"
    assert classify(WATCHING)[0] == "BEOBACHTEN"
    assert classify(BUILDING)[0] == "SETUP_ENTSTEHT"
    assert classify(NEARLY)[0] == "SIGNAL_NAHE"
    assert classify(TEST_SIGNAL)[0] == "TESTSIGNAL"


def test_data_quality_alone_never_lifts_the_ui_off_ruhig():
    state, conditions = classify(CALM)
    assert conditions["datenqualitaet"] is True
    assert not any(conditions[key] for key in BUILD_UP_GROUPS)
    assert state == "RUHIG"


def test_forecast_neutral_does_not_duplicate_block_signal_near():
    evidence = Evidence(
        setup_state="NEUTRAL",
        direction="SHORT",
        pressure=70.0,
        flow_agreement="CONFIRMED",
        l2_aligned=True,
        return_60s=-0.0012,
    )
    state, conditions = classify(evidence)
    assert state == "SIGNAL_NAHE"
    assert "zustand" not in conditions
    assert "scharf" not in conditions


def test_explicit_contradiction_is_a_gate_but_neutral_l2_is_soft():
    assert classify(NEARLY)[0] == "SIGNAL_NAHE"
    contradicted = Evidence(
        setup_state="NEUTRAL",
        direction="SHORT",
        pressure=70.0,
        flow_agreement="CONFIRMED",
        l2_aligned=None,
        return_60s=-0.0012,
        contradictions=("cross-group directional conflict",),
    )
    assert classify(contradicted)[0] == "SETUP_ENTSTEHT"


# ------------------------------------------------------------------ hysteresis


def test_ruhig_is_stable_under_flickering_noise():
    sm, clock = machine()
    drive(sm, clock, CALM, 10)
    assert sm.state == "RUHIG"
    # single-tick blips, each immediately retracted -- must never confirm
    for _ in range(20):
        sm.update(BUILDING)
        clock.tick(1.0)
        sm.update(CALM)
        clock.tick(1.0)
        assert sm.state == "RUHIG"
    assert sm.alerts() == []
    assert sm.snapshot()["timeline"] == []


def test_two_consecutive_blips_are_still_below_the_upgrade_dwell():
    sm, clock = machine()
    drive(sm, clock, CALM, 5)
    drive(sm, clock, WATCHING, 2)
    assert sm.state == "RUHIG"
    drive(sm, clock, WATCHING, 1)
    assert sm.state == "BEOBACHTEN"


# ------------------------------------------------------------- full build path


def test_full_build_up_sequence_reaches_testsignal():
    sm, clock = machine()
    drive(sm, clock, CALM, 5)
    assert sm.state == "RUHIG"

    drive(sm, clock, WATCHING, 4)
    assert sm.state == "BEOBACHTEN"

    drive(sm, clock, BUILDING, 4)
    assert sm.state == "SETUP_ENTSTEHT"

    near = drive(sm, clock, NEARLY, 4)
    assert sm.state == "SIGNAL_NAHE"
    assert near["missing_trigger"] == "orderbuch"
    assert "Orderbuch" in near["missing_trigger_label"]
    assert "SHORT-Signal nahe" in near["headline"]
    assert near["show_checklist"] is True

    final = drive(sm, clock, TEST_SIGNAL, 4)
    assert sm.state == "TESTSIGNAL"
    assert final["severity"] == "CRITICAL"
    assert final["execution"] == "DISABLED"

    path = [event["to"] for event in reversed(final["timeline"])]
    assert path == ["BEOBACHTEN", "SETUP_ENTSTEHT", "SIGNAL_NAHE", "TESTSIGNAL"]


def test_collapse_before_completion_reports_invalidiert():
    sm, clock = machine()
    drive(sm, clock, CALM, 3)
    drive(sm, clock, WATCHING, 4)
    assert sm.state == "BEOBACHTEN"
    drive(sm, clock, BUILDING, 4)
    assert sm.state == "SETUP_ENTSTEHT"

    # a short loss of evidence must NOT downgrade yet (downgrade dwell is 8)
    drive(sm, clock, CALM, 5)
    assert sm.state == "SETUP_ENTSTEHT"

    result = drive(sm, clock, CALM, 4)
    assert sm.state == "INVALIDIERT"
    assert "zerfallen" in result["headline"]
    path = [event["to"] for event in reversed(result["timeline"])]
    assert path == ["BEOBACHTEN", "SETUP_ENTSTEHT", "INVALIDIERT"]


def test_invalidiert_decays_back_to_ruhig_after_the_hold():
    sm, clock = machine()
    drive(sm, clock, WATCHING, 4)
    drive(sm, clock, BUILDING, 4)
    drive(sm, clock, CALM, 10)
    assert sm.state == "INVALIDIERT"
    drive(sm, clock, CALM, 35)
    assert sm.state == "RUHIG"


def test_engine_invalidation_short_circuits_the_build_up():
    sm, clock = machine()
    drive(sm, clock, WATCHING, 4)
    assert sm.state == "BEOBACHTEN"
    sm.update(Evidence(setup_state="SIGNAL_INVALIDATED", direction="SHORT", pressure=5.0))
    assert sm.state == "INVALIDIERT"


# ---------------------------------------------------------------------- alerts


def test_alerts_fire_once_per_transition_only():
    sm, clock = machine()
    drive(sm, clock, CALM, 5)
    assert sm.alerts() == []

    drive(sm, clock, WATCHING, 30)
    ids = [alert["id"] for alert in sm.alerts()]
    assert len(ids) == 1
    assert len(set(ids)) == 1
    assert sm.alerts()[0]["state"] == "BEOBACHTEN"
    assert sm.alerts()[0]["severity"] == "QUIET"
    assert sm.alerts()[0]["sound"] is False

    drive(sm, clock, BUILDING, 30)
    drive(sm, clock, NEARLY, 30)
    states = [alert["state"] for alert in sm.alerts()]
    assert states == ["SIGNAL_NAHE", "SETUP_ENTSTEHT", "BEOBACHTEN"]
    assert len({alert["id"] for alert in sm.alerts()}) == 3
    assert sm.alerts()[0]["sound"] is True


def test_transition_sink_is_append_only_and_transition_scoped():
    events = []
    clock = FakeClock()
    sm = PreSignalStateMachine(clock=clock, event_sink=events.append)
    drive(sm, clock, WATCHING, 20)
    assert [event["to"] for event in events] == ["BEOBACHTEN"]
    assert events[0]["execution"] == "DISABLED"
    drive(sm, clock, BUILDING, 20)
    assert [event["to"] for event in events] == ["BEOBACHTEN", "SETUP_ENTSTEHT"]


def test_ruhig_never_produces_an_alert():
    sm, clock = machine()
    drive(sm, clock, WATCHING, 4)
    drive(sm, clock, CALM, 60)
    assert sm.state == "RUHIG"
    assert all(alert["state"] != "RUHIG" for alert in sm.alerts())


def test_snapshot_is_stable_between_updates():
    sm, clock = machine()
    drive(sm, clock, BUILDING, 6)
    first = sm.snapshot()
    second = sm.snapshot()
    assert first["state"] == second["state"]
    assert first["entered_at"] == second["entered_at"]


# ------------------------------------------------------------------ API wiring


def test_api_exposes_presignal_and_keeps_proximity(tmp_path):
    from fastapi.testclient import TestClient

    from bitcoin_cycle_analyzer.short_term.web_api import create_app

    client = TestClient(create_app(tmp_path))
    payload = client.get("/api/state").json()
    assert payload["presignal"]["state"] in {"RUHIG", "BEOBACHTEN"}
    assert payload["presignal"]["execution"] == "DISABLED"
    assert isinstance(payload["alerts"], list)
    assert "proximity" in payload  # still available for the expert view

    dedicated = client.get("/api/presignal").json()
    assert dedicated["execution"] == "DISABLED"
    assert dedicated["presignal"]["state"] == payload["presignal"]["state"]
    event_path = tmp_path / "runtime/waverun/presignal_events.jsonl"
    # Calm snapshots do not manufacture transition records.
    assert not event_path.exists()


@pytest.mark.parametrize("state", ["RUHIG", "BEOBACHTEN", "SETUP_ENTSTEHT", "SIGNAL_NAHE", "TESTSIGNAL"])
def test_every_state_has_a_german_headline(state):
    from bitcoin_cycle_analyzer.short_term.presignal_state import headline

    evidence = {"RUHIG": CALM, "BEOBACHTEN": WATCHING, "SETUP_ENTSTEHT": BUILDING,
                "SIGNAL_NAHE": NEARLY, "TESTSIGNAL": TEST_SIGNAL}[state]
    text = headline(state, evidence, evidence.conditions())
    assert text and text[0].isupper() and text.endswith(".")
