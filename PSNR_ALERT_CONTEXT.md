# PSNR Range-Alert Email — Implementation Context

Guide for implementing the "flag sites whose PSNR falls outside its expected range and
email a per-site nominal/flagged summary" feature. Written so an implementer (human or
agent) with no memory of prior discussion can pick this up cold.

**Status: implemented.** See `psnr_alert/` for the module, `test/test_psnr_alert.py`
for tests, and `.github/workflows/update_phantoms.yml` for the wiring. This document
is kept as background/rationale (the `k` derivation in particular).

## 1. Goal

After the daily Flywheel pull refreshes `src/data/RWE_PSNR.csv`, evaluate each site's
most recent PSNR value against that site's own historical range, and email a summary
table (one row per site: nominal or flagged) to a QA recipient list.

## 2. Current pipeline (as of this writing)

- [main.py](main.py) connects to Flywheel, walks every subject/session in the
  `UNITY-QA` project, downloads `ghoststats` PSNR/MSE/NMI/SSIM CSVs for the `T1` and
  `T2` segments, and writes the full, **regenerated-from-scratch** result to
  [src/data/RWE_PSNR.csv](src/data/RWE_PSNR.csv). It does not append — every run
  rebuilds the whole file.
- [.github/workflows/update_phantoms.yml](.github/workflows/update_phantoms.yml) runs
  `main.py` daily at 03:00 UTC, then commits the refreshed CSV.
- Columns in `RWE_PSNR.csv` today: `Site, Location, Session, MSE, PSNR, NMI, SSIM,
  SoftwareVersion, Temperature`. `Site` is the Flywheel subject label (e.g.
  `137-0009`), `Location` is the human site name from
  [src/assets/site_phantom_key.json](src/assets/site_phantom_key.json).
- There is **no SNR column** — `PSNR` (from ghoststats) is the metric this feature
  acts on.
- [fw-email-report/](fw-email-report/) is an unrelated, existing tool (Flywheel usage
  report, not QA data) but has the SMTP-sending plumbing we want to reuse — see
  §6.

## 3. Pre-existing gaps that must be fixed first

These are real bugs in the current pipeline, independent of this feature, but this
feature cannot be built correctly until they're fixed:

1. **No `Segment` column.** [main.py:99-127](main.py#L99-L127) loops `for seg in
   ['T1', 'T2']` and builds one row per segment, but never stores `seg` in the row
   dict (`d = {'Site':..., 'Session':..., 'PSNR':None}`). Today, T1 and T2 PSNR values
   for the same session are indistinguishable in the CSV — they just appear as two
   unlabeled rows. **Fix:** add `d['Segment'] = seg`, and add `'Segment'` to the
   column list in `combined_df_reordered` (main.py:167). The range check must key on
   `(Location, Segment)`, not just `Location` — T1 and T2 PSNR have different natural
   distributions and must not be pooled.
2. **Stale `sw`/`temp_d` values.** [main.py:58,80,88](main.py#L58) — if a session has
   multiple acquisitions and a later one fails to yield a JSON or temperature, the row
   silently keeps the *previous* acquisition's value instead of `None`. Worth a fix
   (reset both to `None` at the top of each acquisition loop iteration) so
   `SoftwareVersion`/`Temperature` in flagged-email context aren't misleading, but not
   strictly blocking for the PSNR check itself.
3. **`src/data/tmp/` not cleaned between runs.** [main.py:143-153](main.py#L143)
   reads every `PSNR*.csv` in `tmp/` indiscriminately; leftovers from a previous
   failed run would double-count. Clean or scope this before relying on the CSV for
   alerting.

## 4. Deriving `k` from real data (not a guessed constant)

Per your instruction, `k` (the SD multiplier that defines "expected range") must be
**calculated from real values and global across sites** — one `k`, shared by every
site, but applied to each site's own mean/SD.

### Method used

Leave-one-out, expanding-window z-scores: for each site, sort its historical PSNR
values by session timestamp; for each point after a minimum history warm-up, compute
`z = (value - mean(prior values)) / std(prior values)`; pool the `z` values across all
16 sites. This simulates "how surprising would this value have looked, given only what
was known before it" — which is exactly the situation the live alerting will face.

Run against the **current** (unsegmented, T1+T2 pooled) `RWE_PSNR.csv`, `MIN_HISTORY =
5`:

```
n z-scores: 443
flag rate by candidate k:
  k=1.5 -> 25.06% flagged
  k=2.0 -> 11.96% flagged
  k=2.5 ->  4.97% flagged   <-- recommended
  k=3.0 ->  3.61% flagged
  k=3.5 ->  2.26% flagged
  k=4.0 ->  1.35% flagged
```

**Recommendation: `k = 2.5`**, i.e. flag when `|value - site_mean| > 2.5 *
site_std`. This lands at a ~5% historical flag rate (a standard "outside the ~95%
band" operating point) — tight enough to be meaningful, loose enough not to flag on
routine noise.

### Important caveat — recompute after the Segment fix

This run pooled T1 and T2 together (per §3.1, they're not currently distinguishable),
which inflates the apparent variance and makes this `k` somewhat conservative. **Once
the `Segment` column exists**, rerun this same leave-one-out method split by
`(Location, Segment)` pooled globally for the z-score distribution, and confirm `k =
2.5` still lands near a 5% historical flag rate — adjust if the split changes the
picture materially. The reusable derivation script:

```python
import pandas as pd, numpy as np

df = pd.read_csv('src/data/RWE_PSNR.csv')
df['timestamp'] = pd.to_datetime(df['Session'].str.replace('_', ':'))
df = df.sort_values(['Location', 'Segment', 'timestamp']).reset_index(drop=True)

MIN_HISTORY = 5
zs = []
for (site, seg), g in df.groupby(['Location', 'Segment']):
    vals = g['PSNR'].values
    for i in range(MIN_HISTORY, len(vals)):
        prior = vals[:i]
        mu, sd = prior.mean(), prior.std(ddof=1)
        if sd == 0 or np.isnan(sd):
            continue
        zs.append((vals[i] - mu) / sd)

zs = np.array(zs)
for k in [1.5, 2, 2.5, 3, 3.5, 4]:
    print(k, (np.abs(zs) > k).mean() * 100)
```

This should live in the new module (§5) as a `derive_k.py` / `--recompute-k` utility,
not just a one-off — it should be easy to rerun as more data accumulates.

### Minimum history

Sites with fewer than `MIN_HISTORY = 5` prior sessions (for a given segment) don't
have a trustworthy baseline yet. Today that's **2 of 16 sites** (`cardiff`: 1 row,
`ubc`: 3 rows) at the unsegmented count — likely more once split by segment. Report
these as `Insufficient history`, a third status distinct from `Nominal`/`Flagged`, not
silently either one.

## 5. "Most recent, non-new data" requirement

Per your correction: **the email must report status for every site's current latest
value every run — not only sites that received a new session since the last run.**

Concretely, separate two concerns that were previously conflated:

- **New-session detection** (was the primary driver before this correction): compares
  today's `RWE_PSNR.csv` against a persisted "last seen session per `(Location,
  Segment)`" state, used to (a) decide whether the baseline needs updating with a new
  point, and (b) mark a row as "new since last report" for context in the email (e.g.
  "no new data since 2026-07-14" vs "new session 2026-07-28").
- **Status evaluation** (must now run unconditionally, every report, for every site):
  take each `(Location, Segment)`'s most recent row in `RWE_PSNR.csv` — regardless of
  whether it's new this run — and classify it against that site's baseline (mean/SD
  computed from its history *excluding* that latest point, i.e. still leave-one-out,
  so a site's own latest value never contaminates its own comparison band). This means
  a site with zero new activity still shows up as `Nominal`/`Flagged`/`Insufficient
  history` in every email, using its last known value.

So the email body is always a full site roster (all `Location` values present in
`site_phantom_key.json` or seen historically), not a delta of what changed today.

## 6. Reusing `fw-email-report/` — then deleting it

[fw-email-report/](fw-email-report/) is scaffolding for this feature, not a
dependency of it. Use it as a reference/starting point, then remove the whole
directory once the new feature is built and working:

- **Borrow the pattern, not the file as-is:**
  [fw-email-report/util/email.py](fw-email-report/util/email.py)'s
  `send_email_with_csv` (plain `smtplib` + `MIMEMultipart`, `.env`-driven SMTP config)
  is a good base for a new send function — but this feature needs an **HTML body**
  (the site status table), not just a CSV attachment with a plain-text body. Write a
  new `send_email_html` (or extend the copied function) rather than reusing the
  existing signature unchanged.
- **Borrow the orchestration shape** from
  [fw-email-report/run.py](fw-email-report/run.py): `load_dotenv()` +
  `os.environ[...]` for required SMTP settings, `os.environ.get(...)` with defaults
  for optional ones. Follow the same env var naming
  (`SMTP_SENDER_EMAIL`/`SMTP_SENDER_NAME`/`SMTP_SERVER`/`SMTP_PORT`/`SMTP_USERNAME`/
  `SMTP_PASSWORD`, plus a new `SMTP_RECIPIENT_EMAIL` list for QA alerts) so secrets
  management stays consistent with what's already documented in
  [fw-email-report/.env.example](fw-email-report/.env.example).
- **Do not carry over as-is:** the ~90 lines of commented-out dead code in
  [fw-email-report/app/main.py](fw-email-report/app/main.py) (lines 104-199), the
  committed `__pycache__/` directories, or the usage-report-specific `reporter()`
  logic (unrelated to PSNR).
- **Before this folder is ever `git add`-ed:** note `fw-email-report/.env` is
  currently untracked and **not gitignored** (only `env/` is ignored at the repo
  root). If any intermediate commit touches this folder, make sure `.env` and
  `__pycache__/` are excluded first — or simplest, since it's being deleted at the
  end anyway, just never `git add` the folder at all and build the new module
  alongside/independent of it.
- **Removal step (final task in this feature, not optional):** once the new PSNR
  alert module is in place, tested, and wired into the workflow, delete
  `fw-email-report/` entirely (`git rm -r` if it ever got tracked, otherwise it's just
  untracked and can be removed directly). Confirm nothing else in the repo imports
  from it first (nothing currently does — it's self-contained).

## 7. Proposed new module layout

Suggested — not binding, but keeps this self-contained and out of `fw-email-report`'s
now-deleted footprint:

```
psnr_alert/
  __init__.py
  baseline.py       # load/update psnr_baseline.json, leave-one-out mean/SD per (Location, Segment)
  derive_k.py        # the recompute-k utility from §4, runnable standalone
  range_check.py     # classify each site's latest row: Nominal / Flagged / Insufficient history
  email_report.py    # HTML table renderer + send (adapted from fw-email-report/util/email.py)
  run.py              # orchestration: load CSV -> update baseline -> classify -> send email
  .env.example         # SMTP_* vars, following fw-email-report's naming
src/data/psnr_baseline.json   # persisted per-(Location,Segment) history state, committed like RWE_PSNR.csv
```

### `psnr_baseline.json` shape (sketch)

```json
{
  "st thomas": {
    "T1": {"n": 74, "mean": 33.9, "std": 0.6, "last_session": "2023-06-21 09:56:57"},
    "T2": {"n": 74, "mean": 31.2, "std": 0.8, "last_session": "2023-06-21 09:56:57"}
  }
}
```

Store running `n`/`mean`/`std` (Welford's online algorithm, since the CSV is fully
regenerated each run rather than truly incremental — simplest correct approach is
actually to just recompute mean/std directly from all historical rows in
`RWE_PSNR.csv` for that `(Location, Segment)` each run, excluding the latest point,
rather than maintaining running stats — the CSV already has full history, so there's
no need for incremental statistics here). The JSON state file's real job is just
tracking `last_session` seen per `(Location, Segment)`, for the "new since last
report" annotation in §5 — the mean/SD themselves can be recomputed fresh from the CSV
every run since full history is always available.

## 8. Workflow integration

Extend [.github/workflows/update_phantoms.yml](.github/workflows/update_phantoms.yml)
(confirmed as the chosen integration point): add a step after the existing "Commit and
push updated CSV" step that runs `python -m psnr_alert.run`, then a second commit for
the updated `psnr_baseline.json` state (last-seen timestamps). Add required SMTP
secrets to the repo's GitHub Actions secrets, alongside the existing
`FW_CLI_API_KEY`.

## 9. Testing plan

- Unit-test `range_check.py` classification against synthetic `(mean, std, value)`
  triples spanning nominal/flagged/insufficient-history cases.
- Run `derive_k.py` against the real `RWE_PSNR.csv` (post-Segment-fix) and confirm the
  flag rate at `k=2.5` is still in a sane single-digit-percent range before wiring it
  into the live workflow.
- Dry-run `email_report.py` locally (via `fw-email-report/.env`-style local config, not
  committed) and visually check the rendered HTML table before enabling the scheduled
  send.

## 10. Open items still needing a decision

- Exact recipient list for the alert email = [niall.bourke@kcl.ac.uk, hajer.karoui@kcl.ac.uk]
- Whether "Insufficient history" sites should be included in every email
- Whether a flagged status should re-trigger an email every day it remains flagged

