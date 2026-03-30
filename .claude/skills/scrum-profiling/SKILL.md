---
name: scrum-profiling
description: "Generate a scrum status report for profiling-related epics, issues, and PRs. Outputs a PDF with charts and a markdown file (.md)."
---

# Profiling Scrum Status Report

You are generating a scrum status report for the Spyre profiling workstream.
This report will be used during scrum calls to give the team a quick snapshot
of progress, blockers, and what needs attention.

## Data Collection

Run the following `gh` commands to gather data. Adapt date ranges based on
the reporting period (default: last 7 days).

### 1. Open profiling issues

```bash
gh issue list --repo torch-spyre/torch-spyre --label torch-profiler --state open --json number,title,assignees,labels,updatedAt,createdAt --limit 100
```

### 2. Recently closed profiling issues (last 7 days)

```bash
gh issue list --repo torch-spyre/torch-spyre --label torch-profiler --state closed --json number,title,assignees,closedAt --limit 50
```

Filter results to only include issues closed within the reporting period.

### 3. Profiling epics

```bash
gh issue list --repo torch-spyre/torch-spyre --label torch-profiler --label epic --state open --json number,title,assignees,body --limit 20
```

For each epic, parse the checkbox sub-tasks from the issue body to calculate
completion percentage: count `- [x]` vs total `- [ ]` and `- [x]` lines.

### 4. Open PRs related to profiling

```bash
gh pr list --repo torch-spyre/torch-spyre --label torch-profiler --state open --json number,title,author,reviewRequests,reviews,createdAt,updatedAt,isDraft --limit 30
```

If the `torch-profiler` label is not consistently applied to PRs, also search:

```bash
gh pr list --repo torch-spyre/torch-spyre --state open --search "profil OR memory OR aiu-smi OR libaiupti" --json number,title,author,reviewRequests,reviews,createdAt,isDraft --limit 30
```

### 5. Recently merged PRs (last 7 days)

```bash
gh pr list --repo torch-spyre/torch-spyre --state merged --search "profil OR memory OR aiu-smi OR libaiupti" --json number,title,author,mergedAt --limit 20
```

Filter results to only include PRs merged within the reporting period.

### 6. Issues that moved to in-progress

Look for issues that were recently assigned or had activity. Use the
`updatedAt` field from step 1 and cross-reference with assignee changes.
Issues with assignees that were updated within the reporting period likely
moved to in-progress.

## Report Generation

After collecting all data, generate the report in **two formats**:

1. **Markdown file** — `reports/scrum-profiling-{YYYY-MM-DD}.md`
2. **PDF document** — `reports/scrum-profiling-{YYYY-MM-DD}.pdf`

Create the `reports/` directory if it does not exist (at the repo root).

Use the current date and compute the reporting period (last 7 days by default).
Convert all dates to `YYYY-MM-DD` format.

### Step 1: Generate chart images with matplotlib

Write a Python script and run it with `python3` to generate charts as PNG
files in a temporary directory. The script should use `matplotlib` to create
the following charts. Use a clean, professional style (`plt.style.use('seaborn-v0_8-whitegrid')` or similar). Use
the Spyre brand color palette: `#e68244` (orange), `#4d5c5e` (dark gray),
`#734761` (mauve), `#0075ca` (blue), `#f7b749` (gold), `#d9306a` (pink),
`#2ea44f` (green).

#### Chart 1: Epic Progress Bar Chart (horizontal)

- One horizontal bar per epic, showing completion percentage (0-100%).
- Color bars by status: green (>60%), gold (20-60%), red (<20%).
- Label each bar with the epic title (truncated to 40 chars) and the
  `done/total` count.
- Title: "Epic Progress"

#### Chart 2: Issue Flow Summary (grouped bar chart)

- Three groups: "Opened", "Closed", "In Progress"
- One bar per group showing the count for this period.
- Title: "Issue Flow — {start_date} to {end_date}"

#### Chart 3: PR Pipeline Funnel (horizontal bar chart)

- Bars for: "Draft", "Needs Review", "Approved", "Merged (this period)"
- Color-coded by stage.
- Title: "PR Pipeline"

#### Chart 4: Workload Distribution (bar chart)

- One bar per assignee, showing how many open profiling issues they own.
- Sort descending by count. Only include assignees with >= 1 issue.
- Title: "Open Issues by Assignee"

#### Chart 5: Stale Issues Age (horizontal bar chart)

- One bar per stale issue (assigned, no update in >14 days).
- Bar length = days since last update.
- Label with issue title (truncated) and assignee.
- Color gradient: yellow (14d) to red (30d+).
- Title: "Stale Issues — Days Since Last Update"

Save all charts as PNG files with `dpi=150`, `bbox_inches='tight'`.

### Step 2: Generate the Markdown report

Write the markdown report to `reports/scrum-profiling-{YYYY-MM-DD}.md` using
the template below. Embed chart image references using relative paths
(e.g., `![Epic Progress](charts/epic_progress.png)`).

### Step 3: Generate the PDF document

Write a Python script and run it with `python3` to generate the PDF document
using the `fpdf2` library (`from fpdf import FPDF`). The script should:

1. Create an FPDF instance (A4, portrait).
2. Add a title page with: report title, date, reporting period, key numbers box.
3. For each section (Epics, Closed Issues, Opened Issues, etc.):
   - Add a section heading with an orange underline accent.
   - Insert the corresponding chart image (width=190mm) right after the
     heading where a chart is relevant.
   - Add a table with the data using alternating row colors and an orange
     header row. Handle page breaks with header reprinting.
4. Add the Blockers & Risks section as bullet points.
5. Add a Visualizations appendix with the remaining charts.
6. Save to `reports/scrum-profiling-{YYYY-MM-DD}.pdf`.

Import pattern for fpdf2:
```python
from fpdf import FPDF
```

### Chart placement in the PDF document

| Section | Chart to embed |
|---------|----------------|
| Epic Progress | Chart 1 (epic progress bars) |
| Issue summary (after Key Numbers) | Chart 2 (issue flow) |
| PRs summary (after Key Numbers) | Chart 3 (PR pipeline) |
| After Key Numbers | Chart 4 (workload distribution) |
| Blockers & Risks | Chart 5 (stale issues age) |

## Markdown Output Template

````markdown
# Profiling Scrum Status — {date}

**Reporting period:** {start_date} → {end_date}

---

## Epic Progress

![Epic Progress](charts/epic_progress.png)

| Epic | Owner | Progress | Status |
|------|-------|----------|--------|
| #{number} {title} | @{assignee} | {done}/{total} ({pct}%) | {status_emoji} |

Status emoji key: 🟢 on track (>60%), 🟡 in progress (20-60%), 🔴 blocked or behind (<20%)

---

## Issues Closed

| Issue | Title | Closed by | Date |
|-------|-------|-----------|------|
| #{number} | {title} | @{assignee} | {closed_date} |

---

## Issues Opened

| Issue | Title | Opened by | Date |
|-------|-------|-----------|------|
| #{number} | {title} | @{author} | {created_date} |

---

## Issues In Progress

| Issue | Title | Assignee | Last updated |
|-------|-------|----------|--------------|
| #{number} | {title} | @{assignee} | {updated_date} |

---

## PRs Needing Review

| PR | Title | Author | Waiting since | Reviewers requested |
|----|-------|--------|---------------|---------------------|
| #{number} | {title} | @{author} | {created_date} | @{reviewers} |

Flag any PR that has been waiting for review for more than 3 business days.

---

## PRs Merged

| PR | Title | Author | Merged |
|----|-------|--------|--------|
| #{number} | {title} | @{author} | {merged_date} |

---

## Draft PRs

| PR | Title | Author | Created |
|----|-------|--------|---------|
| #{number} | {title} | @{author} | {created_date} |

---

## Blockers & Risks

List any issues or PRs that are:
- Blocked on external dependencies (runtime, flex, hardware)
- Stale (no activity for >14 days with an assignee)
- Missing assignees but in the current sprint

---

## Key Numbers

- **Open issues:** {count}
- **Closed this period:** {count}
- **Open PRs:** {count}
- **PRs needing review:** {count}
- **PRs merged this period:** {count}

---

## Visualizations

### Issue Flow
![Issue Flow](charts/issue_flow.png)

### PR Pipeline
![PR Pipeline](charts/pr_pipeline.png)

### Workload Distribution
![Workload Distribution](charts/workload_distribution.png)

### Stale Issues
![Stale Issues](charts/stale_issues.png)
````

## Formatting Rules

- Keep the report concise — this is for a scrum call, not a detailed review.
- Sort issues and PRs by most recent activity first.
- If an issue has multiple labels (e.g., `torch-profiler` + `epic`), show it
  in the Epics section, not in the regular issues sections.
- For PRs needing review, highlight any that have been open >3 business days
  with no review activity by adding a note next to them.
- For stale issues (assigned but no update in 14+ days), flag them in the
  In Progress section.
- Do not include issues or PRs that are unrelated to profiling even if they
  appear in search results — use your judgement to filter noise.

## Output Checklist

After generating both files, confirm to the user:

1. The markdown file path: `reports/scrum-profiling-{date}.md`
2. The PDF document path: `reports/scrum-profiling-{date}.pdf`
3. The charts directory: `reports/charts/`
4. A summary of key numbers from the report.
