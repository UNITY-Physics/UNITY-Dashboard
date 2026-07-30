import pandas as pd
import pytest

from psnr_alert.baseline import leave_one_out_baselines, load_history
from psnr_alert.email_report import build_html_table, build_subject
from psnr_alert.range_check import (
    FLAGGED,
    INSUFFICIENT_HISTORY,
    NOMINAL,
    NO_DATA,
    classify,
    evaluate_sites,
)


# --- classify() -------------------------------------------------------

def test_classify_nominal_within_band():
    assert classify(latest_value=30.0, baseline_mean=30.0, baseline_std=1.0, baseline_n=10) == NOMINAL


def test_classify_flagged_outside_band():
    # deviation = 5, k*std = 2.5 -> flagged
    assert classify(latest_value=35.0, baseline_mean=30.0, baseline_std=1.0, baseline_n=10) == FLAGGED


def test_classify_boundary_is_nominal():
    # deviation exactly equals k*std -> not flagged (strict >)
    assert classify(latest_value=32.5, baseline_mean=30.0, baseline_std=1.0, baseline_n=10, k=2.5) == NOMINAL


def test_classify_insufficient_history_below_min():
    assert classify(latest_value=100.0, baseline_mean=30.0, baseline_std=1.0, baseline_n=3, min_history=5) == INSUFFICIENT_HISTORY


def test_classify_insufficient_history_no_std():
    assert classify(latest_value=30.0, baseline_mean=None, baseline_std=None, baseline_n=0) == INSUFFICIENT_HISTORY


def test_classify_zero_std_flags_any_deviation():
    assert classify(latest_value=31.0, baseline_mean=30.0, baseline_std=0.0, baseline_n=10) == FLAGGED
    assert classify(latest_value=30.0, baseline_mean=30.0, baseline_std=0.0, baseline_n=10) == NOMINAL


# --- evaluate_sites() ---------------------------------------------------

def _make_history():
    # site_a: 6 nominal-ish points then one flagged latest point
    # site_b: only 2 points -> insufficient history
    # site_c: not present at all -> no data
    rows = []
    base_sessions = [f"2024-01-{i:02d} 09_00_00" for i in range(1, 8)]
    for i, session in enumerate(base_sessions[:-1]):
        rows.append({"Location": "site_a", "Session": session, "PSNR": 30.0 + (i % 2) * 0.1})
    # latest point is a big outlier
    rows.append({"Location": "site_a", "Session": base_sessions[-1], "PSNR": 50.0})

    rows.append({"Location": "site_b", "Session": "2024-01-01 09_00_00", "PSNR": 20.0})
    rows.append({"Location": "site_b", "Session": "2024-01-02 09_00_00", "PSNR": 20.5})

    return pd.DataFrame(rows)


def test_evaluate_sites_full_roster():
    df = _make_history()
    df["timestamp"] = pd.to_datetime(df["Session"].str.replace("_", ":"))

    roster = ["site_a", "site_b", "site_c"]
    results = evaluate_sites(df, roster, previous_state={}, k=2.5, min_history=5)

    by_site = {r["site"]: r for r in results}

    assert by_site["site_a"]["status"] == FLAGGED
    assert by_site["site_b"]["status"] == INSUFFICIENT_HISTORY
    assert by_site["site_c"]["status"] == NO_DATA

    # every roster site must be present, even with no data
    assert len(results) == len(roster)


def test_evaluate_sites_reports_non_new_latest_value():
    """A site with no new session since the last report must still be evaluated
    and included using its existing latest value (not skipped)."""
    df = _make_history()
    df["timestamp"] = pd.to_datetime(df["Session"].str.replace("_", ":"))

    previous_state = {"site_a": {"last_session": "2024-01-07 09_00_00"}}
    results = evaluate_sites(df, ["site_a"], previous_state=previous_state, k=2.5, min_history=5)

    site_a = next(r for r in results if r["site"] == "site_a")
    assert site_a["is_new"] is False
    assert site_a["status"] == FLAGGED  # still evaluated even though not new


def test_evaluate_sites_marks_new_session():
    df = _make_history()
    df["timestamp"] = pd.to_datetime(df["Session"].str.replace("_", ":"))

    results = evaluate_sites(df, ["site_a"], previous_state={}, k=2.5, min_history=5)
    site_a = next(r for r in results if r["site"] == "site_a")
    assert site_a["is_new"] is True


# --- baseline.load_history --------------------------------------------

def test_load_history_requires_psnr_column(tmp_path):
    csv_path = tmp_path / "no_psnr.csv"
    pd.DataFrame([
        {"Location": "site_a", "Session": "2024-01-01 09_00_00"},
    ]).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="PSNR"):
        load_history(str(csv_path))


def test_load_history_handles_mixed_session_timestamp_formats(tmp_path):
    """Real Flywheel session labels aren't consistently formatted: older
    sessions look like "2023-11-07 09_59_15" (space, then underscores),
    newer ones like "2026-07-28_08_12_26" (underscore throughout). A blind
    str.replace('_', ':') corrupts the second style by also turning the
    date/time separator into a colon, which broke the live workflow."""
    csv_path = tmp_path / "mixed_formats.csv"
    pd.DataFrame([
        {"Location": "site_a", "Session": "2023-11-07 09_59_15", "PSNR": 30.0},
        {"Location": "site_a", "Session": "2026-07-28_08_12_26", "PSNR": 31.0},
    ]).to_csv(csv_path, index=False)

    history = load_history(str(csv_path))
    parsed = sorted(history["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S"))
    assert parsed == ["2023-11-07 09:59:15", "2026-07-28 08:12:26"]


def test_load_history_raises_on_unrecognized_timestamp_format(tmp_path):
    csv_path = tmp_path / "bad_format.csv"
    pd.DataFrame([
        {"Location": "site_a", "Session": "not-a-timestamp", "PSNR": 30.0},
    ]).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Unrecognized Session timestamp"):
        load_history(str(csv_path))


def test_leave_one_out_baselines_excludes_latest_point():
    df = _make_history()
    df["timestamp"] = pd.to_datetime(df["Session"].str.replace("_", ":"))
    baselines = leave_one_out_baselines(df)

    site_a = baselines["site_a"]
    assert site_a["baseline_n"] == 6
    assert site_a["latest_value"] == 50.0
    # baseline mean/std must not include the 50.0 outlier
    assert site_a["baseline_mean"] < 31.0


# --- email_report --------------------------------------------------------

def test_build_subject_flags_when_flagged_present():
    results = [{"status": FLAGGED}, {"status": NOMINAL}]
    assert "flagged" in build_subject(results).lower()


def test_build_subject_nominal_when_none_flagged():
    results = [{"status": NOMINAL}, {"status": NO_DATA}]
    assert build_subject(results) == "UNITY QA: all sites nominal"


def test_build_html_table_contains_each_site():
    results = [
        {"site": "site_a", "status": FLAGGED, "latest_value": 50.0,
         "baseline_mean": 30.0, "baseline_std": 0.1, "baseline_n": 6,
         "latest_session": "2024-01-07 09_00_00", "is_new": True},
        {"site": "site_b", "status": INSUFFICIENT_HISTORY, "latest_value": 20.5,
         "baseline_mean": None, "baseline_std": None, "baseline_n": 1,
         "latest_session": "2024-01-02 09_00_00", "is_new": False},
    ]
    html = build_html_table(results, k=2.5)
    assert "Site_A" in html or "site_a".title() in html
    assert FLAGGED in html
    assert INSUFFICIENT_HISTORY in html
