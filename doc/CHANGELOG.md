# Changelog

Notable changes to UNITY-Dashboard. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — email-notification branch — 2026-07-30

### Added
- **PSNR range-alert email** (`psnr_alert/`): after each Flywheel pull, every
  site's most recent PSNR value (per T1/T2 segment) is classified as
  `Nominal`, `Flagged`, or `Insufficient history` against that site's own
  leave-one-out historical baseline, and a per-site HTML status table is
  emailed to the QA recipient list. Every site in
  `site_phantom_key.json` is reported every run, not just sites with new
  data since the last run.
  - `baseline.py` — loads/sorts PSNR history, computes leave-one-out
    mean/std per `(site, segment)`, persists last-seen-session state
    (`src/data/psnr_baseline.json`).
  - `range_check.py` — classification logic; `k=2.5`, `MIN_HISTORY=5`.
  - `derive_k.py` — reusable leave-one-out z-score method for re-deriving
    `k` from real data (`python -m psnr_alert.derive_k`).
  - `email_report.py` — HTML table renderer + SMTP send.
  - `run.py` — orchestration entry point (`python -m psnr_alert.run`).
  - `.env.example` — SMTP config template.
- `test/test_psnr_alert.py` — 16 unit tests covering classification
  boundaries, full-roster evaluation (including sites with no new data and
  sites with no data at all), baseline exclusion of the latest point, and
  session-timestamp parsing.
- `PSNR_ALERT_CONTEXT.md` — background/rationale for the feature, including
  the data-driven derivation of `k`.
- `doc/` directory (this changelog).

### Changed
- `main.py`:
  - Rows now record which segment (`T1`/`T2`) each PSNR value belongs to
    (previously dropped, making T1 and T2 indistinguishable in
    `RWE_PSNR.csv`).
  - `SoftwareVersion`/`Temperature` are reset per session instead of
    silently carrying over a previous session's value when a session has
    no JSON/temperature data.
  - `src/data/tmp/` is cleared of leftover `PSNR_*.csv` at the start of
    each run, so a previous failed run can't get double-counted.
- `.github/workflows/update_phantoms.yml` — added steps to run
  `psnr_alert.run` and commit the updated `psnr_baseline.json` after the
  existing `RWE_PSNR.csv` commit.
- `.gitignore` — ignore `.env` / `psnr_alert/.env`, `__pycache__/`, and
  stray macOS/Google-Drive `Icon` marker files that were previously
  showing up as untracked noise (and, inside `.git/refs`, briefly broke
  `git fetch`).

### Fixed
- Inconsistent `Session` timestamp formats from Flywheel (`"2023-11-07
  09_59_15"` vs `"2026-07-28_08_12_26"`) broke a blind
  `str.replace('_', ':')` used to parse session timestamps — the second
  style has its date/time separator corrupted into a colon, which crashed
  the first live `update_phantoms.yml` run of `psnr_alert.run`. Replaced
  with a format-tolerant parser in `psnr_alert/baseline.py` (raises clearly
  on truly malformed input) and `src/pages/qa.py` (degrades to `NaT`
  instead of crashing the dashboard on import).

### Removed
- `fw-email-report/` — superseded by `psnr_alert/`. It was reference
  scaffolding (SMTP-send pattern, `.env`-driven config) for an unrelated
  Flywheel usage-report tool, never a dependency of the dashboard itself.
