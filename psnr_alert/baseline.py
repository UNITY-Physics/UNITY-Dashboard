"""Load PSNR history and compute per-(site, segment) baseline statistics.

The source CSV (`src/data/RWE_PSNR.csv`) is regenerated from scratch on every
Flywheel pull, so it always contains full history. There is no need to
maintain running/incremental statistics — baseline mean/std are recomputed
fresh from the CSV on every run, leaving out each site's own most recent
point so that point can be judged against what was known before it.
"""

import json
import os

import pandas as pd

REQUIRED_COLUMNS = {"Location", "Session", "Segment", "PSNR"}


def load_history(csv_path):
    """Load and sort the PSNR history CSV.

    Raises ValueError if the `Segment` column is missing — this means the
    CSV predates the main.py fix that records which segment (T1/T2) each
    row belongs to, and pooling them would silently corrupt the baseline.
    """
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"RWE_PSNR.csv is missing required column(s) {sorted(missing)}. "
            "If 'Segment' is missing, this CSV predates the main.py fix that "
            "records T1/T2 per row — rerun the Flywheel pull before running "
            "the PSNR alert."
        )

    df = df.dropna(subset=["Location", "PSNR"]).copy()
    df["timestamp"] = pd.to_datetime(df["Session"].str.replace("_", ":"))
    df = df.sort_values(["Location", "Segment", "timestamp"]).reset_index(drop=True)
    return df


def site_roster(site_phantom_key_path):
    """Canonical list of known site names, independent of who has data yet."""
    with open(site_phantom_key_path) as f:
        site_phantom_key = json.load(f)
    return sorted(site_phantom_key.keys())


def leave_one_out_baselines(df):
    """For each (Location, Segment), compute stats from all-but-the-latest row.

    Returns a dict keyed by (location, segment) with:
      baseline_n, baseline_mean, baseline_std,
      latest_value, latest_session, latest_timestamp
    Sites/segments with only one row get baseline_n = 0 (no prior history).
    """
    results = {}
    for (location, segment), group in df.groupby(["Location", "Segment"]):
        group = group.sort_values("timestamp")
        latest = group.iloc[-1]
        prior = group.iloc[:-1]

        baseline_n = len(prior)
        baseline_mean = prior["PSNR"].mean() if baseline_n > 0 else None
        baseline_std = prior["PSNR"].std(ddof=1) if baseline_n > 1 else None

        results[(location, segment)] = {
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
        raw = json.load(f)
    # JSON keys are "location||segment" strings; expand back to tuple keys.
    return {tuple(key.split("||")): value for key, value in raw.items()}


def save_state(state_path, baselines):
    """Persist last_session per (location, segment) for the next run."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    serializable = {
        f"{location}||{segment}": {
            "last_session": stats["latest_session"],
        }
        for (location, segment), stats in baselines.items()
    }
    with open(state_path, "w") as f:
        json.dump(serializable, f, indent=2, sort_keys=True)
