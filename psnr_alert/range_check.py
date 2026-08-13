"""Classify each site's latest PSNR value as Nominal / Flagged / Insufficient
history / No data.

The classifier operates in two modes:
1. Range mode (default): Evaluates if the latest PSNR falls within an 
   expected absolute range (default 30-40).
2. Standard Deviation ('std') mode: Evaluates against the site's own 
   leave-one-out historical baseline.

For 'std' mode, k and MIN_HISTORY are derived from real historical PSNR data —
see `derive_k.py` and PSNR_ALERT_CONTEXT.md §4 for the method. They are global
constants applied to every site's own mean/std, not per-site tuned values.
"""

from psnr_alert.baseline import leave_one_out_baselines

# From leave-one-out z-score analysis of src/data/RWE_PSNR.csv (3020 points,
# 16 sites): k=2.5 lands at a ~3.8% historical flag rate. Recompute with
# derive_k.py as more data accumulates.
DEFAULT_K = 2
MIN_HISTORY = 5

# Range mode defaults
DEFAULT_MIN_PSNR = 30
DEFAULT_MAX_PSNR = 40

# Status constants
NOMINAL = "Nominal"
FLAGGED = "Flagged"
INSUFFICIENT_HISTORY = "Insufficient history"
NO_DATA = "No data"

# Mode constants
MODE_RANGE = "range"
MODE_STD = "std"

# ==========================================
# SCRIPT CONFIGURATION
# Set to MODE_RANGE or MODE_STD
# ==========================================
ACTIVE_MODE = MODE_RANGE


def classify(latest_value, baseline_mean, baseline_std, baseline_n, 
             k=DEFAULT_K, min_history=MIN_HISTORY, 
             mode=ACTIVE_MODE, min_val=DEFAULT_MIN_PSNR, max_val=DEFAULT_MAX_PSNR):
    """
    Classification function with two modes:
    - 'range': Checks if the latest_value is strictly between min_val and max_val.
    - 'std': Checks if the latest_value deviates from the mean by more than k standard deviations.
    """
    if mode == MODE_STD:
        if baseline_n < min_history or baseline_mean is None or baseline_std is None:
            return INSUFFICIENT_HISTORY
        deviation = abs(latest_value - baseline_mean)
        return FLAGGED if deviation > k * baseline_std else NOMINAL
        
    elif mode == MODE_RANGE:
        # In absolute range mode, historical data size doesn't matter, 
        # we just check the current value against the static thresholds.
        if latest_value is None:
            return INSUFFICIENT_HISTORY
            
        if min_val <= latest_value <= max_val:
            return NOMINAL
        return FLAGGED
        
    else:
        raise ValueError(f"Unknown classification mode: {mode}")


def evaluate_sites(df, roster, previous_state=None, k=DEFAULT_K, min_history=MIN_HISTORY, 
                   mode=ACTIVE_MODE, min_val=DEFAULT_MIN_PSNR, max_val=DEFAULT_MAX_PSNR):
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
            mode=mode,
            min_val=min_val,
            max_val=max_val
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
