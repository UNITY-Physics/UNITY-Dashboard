"""Re-derive the global `k` (SD multiplier) from real PSNR history.

Leave-one-out, expanding-window z-scores: for each site, sort by session
timestamp, and for every point after a minimum warm-up compute
z = (value - mean(prior values)) / std(prior values). Pooling these z-scores
across all sites simulates "how surprising would this value have looked,
given only what was known before it" — the same situation live alerting
faces. See PSNR_ALERT_CONTEXT.md §4.

Run standalone:
    python -m psnr_alert.derive_k [path/to/RWE_PSNR.csv]
"""

import sys

import numpy as np
import pandas as pd

DEFAULT_CANDIDATES = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]


def leave_one_out_zscores(df, min_history=5):
    """Return the pooled array of leave-one-out z-scores across all site groups.

    `df` must already have a `timestamp` column (see baseline.load_history).
    """
    zs = []
    for _, group in df.groupby("Location"):
        vals = group.sort_values("timestamp")["PSNR"].values
        for i in range(min_history, len(vals)):
            prior = vals[:i]
            mu, sd = prior.mean(), prior.std(ddof=1)
            if sd == 0 or np.isnan(sd):
                continue
            zs.append((vals[i] - mu) / sd)
    return np.array(zs)


def flag_rates(zscores, candidates=DEFAULT_CANDIDATES):
    """% of historical points that would have been flagged at each candidate k."""
    return {k: float((np.abs(zscores) > k).mean() * 100) for k in candidates}


def recommend_k(zscores, candidates=DEFAULT_CANDIDATES, target_rate=5.0):
    """Pick the candidate k whose historical flag rate is closest to target_rate%."""
    rates = flag_rates(zscores, candidates)
    return min(rates, key=lambda k: abs(rates[k] - target_rate)), rates


if __name__ == "__main__":
    from psnr_alert.baseline import load_history

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "src/data/RWE_PSNR.csv"
    history = load_history(csv_path)

    zscores = leave_one_out_zscores(history)
    print(f"n z-scores: {len(zscores)}")

    k, rates = recommend_k(zscores)
    for candidate, rate in rates.items():
        marker = "  <-- recommended" if candidate == k else ""
        print(f"  k={candidate}: {rate:.2f}% flagged{marker}")
