# Profiling Scrum Reports

Automated scrum status reports for the Spyre profiling workstream.
Generates both a **PDF** (`.pdf`) and **Markdown file** (`.md`)
with embedded visualizations.

## What it does

Pulls profiling-related data from the
[torch-spyre/torch-spyre](https://github.com/torch-spyre/torch-spyre) GitHub
repo (issues, epics, and PRs with the `torch-profiler` label) and produces a
report covering the last 7 days (configurable).

### Report sections

| Section | Description |
|---------|-------------|
| **Epic Progress** | Completion % for each profiling epic (parsed from checkboxes) |
| **Issues Closed** | Issues closed during the reporting period |
| **Issues Opened** | New issues created during the period |
| **Issues In Progress** | Assigned issues with recent activity |
| **PRs Needing Review** | Open PRs awaiting review, flagged if stale |
| **PRs Merged** | PRs merged during the period |
| **Draft PRs** | Work-in-progress PRs |
| **Blockers & Risks** | Stale issues, unassigned epics, velocity concerns |
| **Key Numbers** | Summary counts |

### Charts (embedded in both formats)

| Chart | Description |
|-------|-------------|
| **Epic Progress** | Horizontal bars showing completion %, color-coded by status |
| **Issue Flow** | Grouped bars: opened vs closed vs in-progress |
| **PR Pipeline** | Funnel: draft → needs review → approved → merged |
| **Workload Distribution** | Open issues per assignee |
| **Stale Issues Age** | Days since last update, yellow-to-red gradient |

## Prerequisites

- **Python 3.10+**
- **GitHub CLI** (`gh`) — authenticated with access to `torch-spyre/torch-spyre`
- Python packages:

```bash
pip install -r reports/requirements.txt
```

Or individually:

```bash
pip install matplotlib fpdf2 pillow
```

## Usage

### Option 1: Via Claude Code (recommended)

Run the skill from the repo root:

```
/scrum-profiling
```

Claude Code will fetch the data, generate charts, and produce both report
files in the `reports/` directory.

### Option 2: Standalone script

```bash
# From the repo root — fetches data from GitHub and generates reports
python reports/generate_report.py

# Custom reporting period (14 days)
python reports/generate_report.py --days 14

# Custom output directory
python reports/generate_report.py --output-dir /path/to/output

# Use pre-fetched data from a specific directory
python reports/generate_report.py --data-dir /path/to/json-data
```

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--days` | `7` | Number of days in the reporting period |
| `--output-dir` | `reports/` | Where to write `.md`, `.pdf`, and `charts/` |
| `--data-dir` | `/tmp` | Directory for cached GitHub JSON data |

## Output

After running, you'll find:

```
reports/
├── charts/
│   ├── epic_progress.png
│   ├── issue_flow.png
│   ├── pr_pipeline.png
│   ├── stale_issues.png
│   └── workload_distribution.png
├── scrum-profiling-YYYY-MM-DD.md
└── scrum-profiling-YYYY-MM-DD.pdf
```

Generated reports and charts are **gitignored** — they are local artifacts,
not committed to the repo.

## How it works

1. **Data collection** — Uses `gh` CLI to query GitHub for issues and PRs
   with the `torch-profiler` label, plus keyword searches for
   profiling-related PRs.
2. **Classification** — Separates epics from regular issues, computes
   checkbox-based progress for epics, identifies stale/in-progress items.
3. **Chart generation** — Uses `matplotlib` with the Spyre brand color
   palette to produce 5 PNG charts.
4. **Report generation** — Writes a Markdown file with image references and
   a styled PDF with embedded charts, formatted tables, and a title page.
