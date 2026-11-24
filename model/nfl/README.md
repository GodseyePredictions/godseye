# NFL player-prop and anytime-TD algorithm (`attd`)

This folder is a snapshot of the NFL props / anytime-touchdown project as it stood on
24 November 2026 (through 2026 Week 11). It was built and run by hand in a single cloud
session and had never been in git before this commit. Nothing here changes how the model
works; it is a copy for safekeeping and review.

How to run it is in `USAGE.md`. The rules, backtests and verdicts are in `FACTORS.md`.
Working notes from the session are in `SESSION_NOTES.md`.

## Inventory (answers to the six questions asked on 24 November 2026)

### 1. Where the code lives

- Original location: `/home/user/attd` in a cloud container. It was **not a git repository**,
  had no remotes and had never been pushed to GitHub. This branch is the first copy outside
  that container.
- Size: 43 Python files, 7,067 lines. `data/` 144 MB, `outputs/` 19 MB, `models/` 32 KB,
  166 MB in total.
- Layout:

      run.py              command line: download, backtest, project, card, slip, site, refresh, grade, grade-card
      attd/               the package (pipeline, models, props, slips, site, PDFs, ESPN helpers)
      data/               nflverse caches, schedules, injuries, personnel log, forecasts
      models/             fitted leg correlations (JSON)
      outputs/            projections, cards, PDFs, shipped snapshots, graded results
      outputs/internal/   report cards and graded JSON
      outputs/official/   locked official releases (PDF + JSON)
      outputs/shipped/    a snapshot of every published slip set, used for grading as shipped
      ledger/             the Weeks 1-9 ledger of past slips
      deploy/             notes on hosting the site
      adhoc/              one-off grading and test scripts that lived outside the project

### 2. Tests

There are none. No unit or integration tests exist for this module. Checks so far have
been out-of-sample backtests (`run.py backtest`, results in `outputs/backtest_report.md`),
walk-forward files in `outputs/`, and grading shipped slips against box scores.

### 3. Does it learn on its own?

No. Nothing runs without a person asking for it.

- **What retrains:** `run.py project` refits the LightGBM expected-touchdown and
  anytime-TD models from scratch on every run, using all seasons from 2021 up to the last
  completed week. `run.py card` refits the player-prop models the same way. No fitted model
  is saved between runs.
- **What it learns from:** new games enter only when `run.py download` refreshes the
  nflverse data. More data means the next refit sees more games; that is the only sense in
  which it improves by itself.
- **What triggers it:** the assistant running those commands by hand when the owner asks
  for a build. There is no scheduled task.
- **Calibration:** probability calibration is fitted inside each refit. The leg
  correlations in `models/` were fitted on 7-8 November 2026 by `run.py backtest` and have
  not been refreshed since.
- **Grading feedback:** graded slips do **not** feed back into the model automatically.
  After each report card, rule changes were backtested and written into the code by hand,
  and logged in `FACTORS.md` (accepted and rejected). The owner's own reads go in
  `data/personnel.csv` and are applied as inputs, not learned.

### 4. How the site export is produced

`python run.py site --season S --week W` runs `attd/site.py`. It builds one JSON object
in Python and writes it into `attd/site_template.html` at the `const D = /*__DATA__*/null`
placeholder, giving a single self-contained HTML file. It also saves a snapshot of the
published slips to `outputs/shipped/`.

- **Computed in Python:** every player probability, prop ladder, preset slip and its joint
  probability, fair prices, play-at prices, game scripts, matchup reads, held-player flags
  and the correlation tables.
- **Computed in the page's JavaScript:** the joint probability of slips the viewer builds or
  edits (a Gaussian-copula simulation using the correlation tables shipped in the data),
  the fair price for those slips, edge against odds the viewer types in, and saved slips.

### 5. What existed only in the container

Everything, before this commit. Now on this branch: code, config, rules, the correlation
files, the personnel log, the ledger, shipped snapshots, graded results and PDFs.

Still only in the container (not committed):

- `data/pbp_*.parquet`, `data/part_*.parquet`, `data/ftn_*.parquet`: about 131 MB of
  play-by-play, participation and charting caches. `python run.py download` restores them
  from nflverse.
- `outputs/site/` and `deploy/index.html`: generated site pages, rebuilt by `run.py site`.
- Build logs.

One hand edit would be lost by a re-download: Jacory Croskey-Merritt was set active in
`data/roster_2026.parquet` on 23 November 2026 (noted in `SESSION_NOTES.md`).

There are no saved model binaries to lose, because models are refitted on each run.

### 6. Python version and dependencies

Python 3.13.18. `requirements.txt` lists the modelling dependencies; the PDF and site
checks need three more. Versions installed when this snapshot was taken:

    pandas==3.0.5
    numpy==2.5.3
    pyarrow==26.0.1
    scikit-learn==1.9.1
    lightgbm==4.7.0
    scipy==1.18.1
    tabulate==0.10.0
    reportlab==5.0.1      (PDF slips)
    pdfplumber==0.11.10   (reading PDFs back when grading)
    requests==2.34.2

## Changes made for this copy

- The ledger file was renamed to `ledger/NFL-Algo-Complete-Ledger.md` and the default
  path in `run.py` updated to match.
- The private site link was removed from the notes.
- The original `README.md` is now `USAGE.md` and the session's `CLAUDE.md` is
  `SESSION_NOTES.md`, so neither is mistaken for this repository's own files.
- No model code was changed.
