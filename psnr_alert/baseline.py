"""Load PSNR history and compute per-site baseline statistics.

The source CSV (`src/data/RWE_PSNR.csv`) is regenerated from scratch on every
Flywheel pull, so it always contains full history. There is no need to
maintain running/incremental statistics — baseline mean/std are recomputed
fresh from the CSV on every run, leaving out each site's own most recent
point so that point can be judged against what was known before it.

Note: the ghoststats PSNR output is a single per-session value — main.py's
`for seg in ['T1', 'T2']` loop was filename filtering, not a genuine T1/T2
split (every real row matches "T2"; "T1" never matches anything), so there
is no per-segment baseline here, just one per site.
"""

import json
import os
import re

import pandas as pd

REQUIRED_COLUMNS = {"Location", "Session", "PSNR"}

# Flywheel session labels aren't consistently formatted: older sessions use
# "YYYY-MM-DD HH_MM_SS" (space before the time, underscores within it), newer
# ones use "YYYY-MM-DD_HH_MM_SS" (underscore throughout). A blind
# str.replace("_", ":") turns the date/time separator into a colon in the
# second style, producing an unparseable string. Accept either separator in
# either position and normalize to a single canonical form.
_SESSION_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ _](\d{2})[_:](\d{2})[_:](\d{2})$")


def _normalize_session_timestamp(session_label):
    match = _SESSION_TS_RE.match(str(session_label).strip())
    if not match:
        raise ValueError(f"Unrecognized Session timestamp format: {session_label!r}")
    date, hh, mm, ss = match.groups()
    return f"{date} {hh}:{mm}:{ss}"


def load_history(csv_path):
    """Load and sort the PSNR history CSV."""
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"RWE_PSNR.csv is missing required column(s) {sorted(missing)}.")

    df = df.dropna(subset=["Location", "PSNR"]).copy()
    df["timestamp"] = pd.to_datetime(df["Session"].map(_normalize_session_timestamp))
    df = df.sort_values(["Location", "timestamp"]).reset_index(drop=True)
    return df


def site_roster(site_phantom_key_path):
    """Canonical list of known site names, independent of who has data yet."""
    with open(site_phantom_key_path) as f:
        site_phantom_key = json.load(f)
    return sorted(site_phantom_key.keys())


def leave_one_out_baselines(df):
    """For each Location, compute stats from all-but-the-latest row.

    Returns a dict keyed by location with:
      baseline_n, baseline_mean, baseline_std,
      latest_value, latest_session, latest_timestamp
    Sites with only one row get baseline_n = 0 (no prior history).
    """
    results = {}
    for location, group in df.groupby("Location"):
        group = group.sort_values("timestamp")
        latest = group.iloc[-1]
        prior = group.iloc[:-1]

        baseline_n = len(prior)
        baseline_mean = prior["PSNR"].mean() if baseline_n > 0 else None
        baseline_std = prior["PSNR"].std(ddof=1) if baseline_n > 1 else None

        results[location] = {
            "baseline_n": baseline_n,
            "baseline_mean": baseline_mean,
            "baseline_std": baseline_std,
            "latest_value": latest["PSNR"],
            "latest_session": latest["Session"],
            "latest_timestamp": latest["timestamp"],
        }
    return results


def load_state(state_path):
    """Last-seen-session state from the previous run, for 'new since last report'."""
    if not os.path.exists(state_path):
        return {}
    with open(state_path) as f:
        return json.load(f)


def save_state(state_path, baselines):
    """Persist last_session per site for the next run."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    serializable = {
        location: {"last_session": stats["latest_session"]}
        for location, stats in baselines.items()
    }
    with open(state_path, "w") as f:
        json.dump(serializable, f, indent=2, sort_keys=True)
