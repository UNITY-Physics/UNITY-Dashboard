"""Classify each site's latest PSNR value as Nominal / Flagged / Insufficient
history / No data, against its own leave-one-out baseline.

k and MIN_HISTORY are derived from real historical PSNR data — see
`derive_k.py` and PSNR_ALERT_CONTEXT.md §4 for the method. They are global
constants applied to every site's own mean/std, not per-site tuned values.
"""

from psnr_alert.baseline import leave_one_out_baselines

# From leave-one-out z-score analysis of src/data/RWE_PSNR.csv (3020 points,
# 16 sites): k=2.5 lands at a ~3.8% historical flag rate. Recompute with
# derive_k.py as more data accumulates.
DEFAULT_K = 2.5
MIN_HISTORY = 5

NOMINAL = "Nominal"
FLAGGED = "Flagged"
INSUFFICIENT_HISTORY = "Insufficient history"
NO_DATA = "No data"


def classify(latest_value, baseline_mean, baseline_std, baseline_n, k=DEFAULT_K, min_history=MIN_HISTORY):
    """Pure classification function, usable directly against synthetic values."""
    if baseline_n < min_history or baseline_mean is None or baseline_std is None:
        return INSUFFICIENT_HISTORY
    deviation = abs(latest_value - baseline_mean)
    return FLAGGED if deviation > k * baseline_std else NOMINAL


def evaluate_sites(df, roster, previous_state=None, k=DEFAULT_K, min_history=MIN_HISTORY):
    """Evaluate every site in `roster` against its latest PSNR value.

    Every site in the roster is evaluated every run — including sites with no
    new session since the last report — using each site's own most recent
    known value. `previous_state` (from baseline.load_state) is only used to
    annotate whether that latest value is new since the last report; it does
    not gate whether a site is evaluated.
    """
    previous_state = previous_state or {}
    baselines = leave_one_out_baselines(df)

    results = []
    for location in roster:
        stats = baselines.get(location)

        if stats is None:
            results.append({
                "site": location,
                "status": NO_DATA,
                "latest_value": None,
                "baseline_mean": None,
                "baseline_std": None,
                "baseline_n": 0,
                "latest_session": None,
                "is_new": False,
            })
            continue

        status = classify(
            stats["latest_value"],
            stats["baseline_mean"],
            stats["baseline_std"],
            stats["baseline_n"],
            k=k,
            min_history=min_history,
        )

        prev = previous_state.get(location)
        is_new = prev is None or prev.get("last_session") != stats["latest_session"]

        results.append({
            "site": location,
            "status": status,
            "latest_value": stats["latest_value"],
            "baseline_mean": stats["baseline_mean"],
            "baseline_std": stats["baseline_std"],
            "baseline_n": stats["baseline_n"],
            "latest_session": stats["latest_session"],
            "is_new": is_new,
        })

    return results
