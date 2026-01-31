# IKD GaN CMOS Literature Intelligence

This repository tracks and curates literature relevant to **GaN CMOS / complementary GaN logic**. A Python agent periodically queries bibliographic sources (currently Crossref), deduplicates results against a master sheet, assigns taxonomy tags, and appends new candidates to a review queue.

## Repository Layout

- `00_taxonomy/`
  - `IKD_Taxonomy.yaml`: Controlled vocabulary, venue hints, and keyword-based tagging rules.
- `01_literature/`
  - `IKD_Literature_Master.xlsx`: Accepted/curated records.
  - `IKD_ReviewQueue.xlsx`: Newly discovered candidates awaiting human review.
  - `IKD_RunLog.csv`: Run history (counts, time window, notes).
- `02_reports/`
  - Outputs and summaries (for example `WeeklyDigest.md`, `GapMap.xlsx`).
- `03_queries/`
  - `queries.json`: Search buckets and phrases used by the agent.
- `literature_agent_v1/`
  - `run_incremental.py`: Main incremental sweep script.
  - `state/last_run_timestamp.txt`: Persists the last run date to avoid re-fetching old results.

## How the Agent Works

1. Loads taxonomy (`00_taxonomy/IKD_Taxonomy.yaml`) and queries (`03_queries/queries.json`).
2. Reads the last run date from `literature_agent_v1/state/last_run_timestamp.txt` (defaults to 2010-01-01 if missing).
3. Queries Crossref for each query bucket for new items since the last run date.
4. Deduplicates against the master sheet using DOI and title similarity.
5. Applies deterministic keyword rules to tag DeviceType / Method / EnablerCategory.
6. Appends new unique entries to `IKD_ReviewQueue.xlsx` and logs a row to `IKD_RunLog.csv`.

## Run Locally (Windows)

### Prerequisites

- Python 3.11+ (recommended)

### Install Dependencies

```powershell
cd c:\Users\kainl\OneDrive\GitHub\IKD_GaN_CMOS
python -m pip install --upgrade pip
pip install -r literature_agent_v1\requirements.txt
```

### Execute the Incremental Sweep

```powershell
python literature_agent_v1\run_incremental.py
```

## Automation (GitHub Actions)

The workflow [.github/workflows/ikd_gan_cmos_daily.yml](file:///c:/Users/kainl/OneDrive/GitHub/IKD_GaN_CMOS/.github/workflows/ikd_gan_cmos_daily.yml) runs daily on a schedule and on manual dispatch. It installs dependencies, runs the incremental agent, then commits and pushes any updated data files.

## Configuration

- Update search buckets/phrases: [queries.json](file:///c:/Users/kainl/OneDrive/GitHub/IKD_GaN_CMOS/03_queries/queries.json)
- Update taxonomy and tagging rules: [IKD_Taxonomy.yaml](file:///c:/Users/kainl/OneDrive/GitHub/IKD_GaN_CMOS/00_taxonomy/IKD_Taxonomy.yaml)
