#!/usr/bin/env python3
# Copyright 2026 The torch-spyre Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generate a profiling scrum status report with charts, markdown, and PDF output.

Usage:
    # Collect data from GitHub first, then generate:
    python generate_report.py

    # Or specify a custom reporting period (days):
    python generate_report.py --days 14

    # Specify a custom output directory:
    python generate_report.py --output-dir /path/to/output

The script expects JSON data files in a temp directory. If they don't exist,
it will fetch them from GitHub using the `gh` CLI.
"""

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from fpdf import FPDF  # noqa: E402

# --- Spyre brand colors ---
C_ORANGE = "#e68244"
C_GRAY = "#4d5c5e"
C_MAUVE = "#734761"
C_BLUE = "#0075ca"
C_GOLD = "#f7b749"
C_PINK = "#d9306a"
C_GREEN = "#2ea44f"

REPO = "torch-spyre/torch-spyre"


def parse_args():
    parser = argparse.ArgumentParser(description="Generate profiling scrum report")
    parser.add_argument(
        "--days", type=int, default=7, help="Reporting period in days (default: 7)"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: directory containing this script)",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory with cached JSON data files (default: /tmp)",
    )
    return parser.parse_args()


# --- GitHub data fetching ---
def gh_fetch(args_list, output_path):
    """Run a gh CLI command and save JSON output to a file."""
    cmd = ["gh"] + args_list
    print(f"  Fetching: {' '.join(cmd[:8])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARNING: gh command failed: {result.stderr.strip()}")
        with open(output_path, "w") as f:
            json.dump([], f)
        return
    with open(output_path, "w") as f:
        f.write(result.stdout)


def fetch_all_data(data_dir):
    """Fetch all profiling data from GitHub."""
    print("Fetching data from GitHub...")

    gh_fetch(
        [
            "issue", "list", "--repo", REPO, "--label", "torch-profiler",
            "--state", "open",
            "--json", "number,title,assignees,labels,updatedAt,createdAt",
            "--limit", "100",
        ],
        os.path.join(data_dir, "profiling_open_issues.json"),
    )
    gh_fetch(
        [
            "issue", "list", "--repo", REPO, "--label", "torch-profiler",
            "--state", "closed",
            "--json", "number,title,assignees,closedAt",
            "--limit", "50",
        ],
        os.path.join(data_dir, "profiling_closed_issues.json"),
    )
    gh_fetch(
        [
            "issue", "list", "--repo", REPO, "--label", "torch-profiler",
            "--label", "epic", "--state", "open",
            "--json", "number,title,assignees,body",
            "--limit", "20",
        ],
        os.path.join(data_dir, "profiling_epics.json"),
    )
    gh_fetch(
        [
            "pr", "list", "--repo", REPO, "--label", "torch-profiler",
            "--state", "open",
            "--json",
            "number,title,author,reviewRequests,reviews,createdAt,updatedAt,isDraft",
            "--limit", "30",
        ],
        os.path.join(data_dir, "profiling_prs_label.json"),
    )
    gh_fetch(
        [
            "pr", "list", "--repo", REPO, "--state", "open",
            "--search", "profil OR memory OR aiu-smi OR libaiupti",
            "--json",
            "number,title,author,reviewRequests,reviews,createdAt,isDraft,updatedAt,labels",
            "--limit", "30",
        ],
        os.path.join(data_dir, "profiling_prs_search.json"),
    )
    gh_fetch(
        [
            "pr", "list", "--repo", REPO, "--state", "merged",
            "--search", "profil OR memory OR aiu-smi OR libaiupti",
            "--json", "number,title,author,mergedAt,labels",
            "--limit", "20",
        ],
        os.path.join(data_dir, "profiling_prs_merged.json"),
    )
    print("Data fetching complete.")


# --- Helpers ---
def load_json(path):
    with open(path) as f:
        return json.load(f)


def parse_dt(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_date(s):
    dt = parse_dt(s)
    return dt.strftime("%Y-%m-%d") if dt else ""


def assignee_names(assignees):
    return (
        ", ".join(f"@{a['login']}" for a in assignees) if assignees else "unassigned"
    )


def truncate(s, n=40):
    return s[: n - 3] + "..." if len(s) > n else s


def status_emoji(pct):
    if pct > 60:
        return "\U0001f7e2"  # green circle
    elif pct >= 20:
        return "\U0001f7e1"  # yellow circle
    return "\U0001f534"  # red circle


PROFILING_KEYWORDS = {
    "profil", "memory", "aiu-smi", "libaiupti", "profiler", "torch-profiler",
}


def is_profiling_pr(pr):
    labels = [lbl["name"].lower() for lbl in pr.get("labels", [])]
    if "torch-profiler" in labels:
        return True
    title_lower = pr["title"].lower()
    return any(kw in title_lower for kw in PROFILING_KEYWORDS)


# --- Chart generation ---
def generate_charts(
    charts_dir, epics, opened_in_period, closed_in_period, in_progress,
    draft_prs, needs_review, approved_prs, merged_in_period,
    assignee_counts, stale_issues, start_date, today, end_date,
):
    """Generate all 5 charts as PNG files."""
    plt.style.use("seaborn-v0_8-whitegrid")

    # Chart 1: Epic Progress
    fig, ax = plt.subplots(figsize=(10, max(4, len(epics) * 0.5)))
    if epics:
        epic_labels = [truncate(f"#{e['number']} {e['title']}") for e in epics]
        epic_pcts = [e["pct"] for e in epics]
        epic_colors = [
            C_GREEN if p > 60 else C_GOLD if p >= 20 else C_PINK for p in epic_pcts
        ]
        y_pos = range(len(epics))
        ax.barh(y_pos, epic_pcts, color=epic_colors, edgecolor="white", height=0.6)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(epic_labels, fontsize=8)
        for idx, e in enumerate(epics):
            label = f"{e['done']}/{e['total']}" if e["total"] > 0 else "no tasks"
            ax.text(max(epic_pcts[idx] + 1, 3), idx, label, va="center", fontsize=8)
        ax.set_xlim(0, 105)
        ax.set_xlabel("Completion %")
    else:
        ax.text(
            0.5, 0.5, "No epics found", ha="center", va="center",
            transform=ax.transAxes,
        )
    ax.set_title("Epic Progress", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(charts_dir, "epic_progress.png"), dpi=150, bbox_inches="tight",
    )
    plt.close(fig)

    # Chart 2: Issue Flow
    fig, ax = plt.subplots(figsize=(6, 4))
    categories = ["Opened", "Closed", "In Progress"]
    counts = [len(opened_in_period), len(closed_in_period), len(in_progress)]
    colors = [C_BLUE, C_GREEN, C_ORANGE]
    bars = ax.bar(categories, counts, color=colors, edgecolor="white", width=0.5)
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
            str(count), ha="center", va="bottom", fontweight="bold", fontsize=12,
        )
    ax.set_ylabel("Count")
    ax.set_title(
        f"Issue Flow \u2014 {start_date.strftime('%Y-%m-%d')} to {today}",
        fontsize=13, fontweight="bold",
    )
    ax.set_ylim(0, max(counts + [1]) * 1.3)
    plt.tight_layout()
    fig.savefig(
        os.path.join(charts_dir, "issue_flow.png"), dpi=150, bbox_inches="tight",
    )
    plt.close(fig)

    # Chart 3: PR Pipeline
    fig, ax = plt.subplots(figsize=(7, 3.5))
    stages = ["Draft", "Needs Review", "Approved", "Merged (this period)"]
    stage_counts = [
        len(draft_prs), len(needs_review), len(approved_prs), len(merged_in_period),
    ]
    stage_colors = [C_GRAY, C_GOLD, C_BLUE, C_GREEN]
    y_pos = range(len(stages))
    ax.barh(y_pos, stage_counts, color=stage_colors, edgecolor="white", height=0.5)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(stages, fontsize=10)
    for idx, c in enumerate(stage_counts):
        ax.text(c + 0.1, idx, str(c), va="center", fontweight="bold", fontsize=11)
    ax.set_xlim(0, max(stage_counts + [1]) * 1.4)
    ax.set_xlabel("Count")
    ax.set_title("PR Pipeline", fontsize=13, fontweight="bold")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(charts_dir, "pr_pipeline.png"), dpi=150, bbox_inches="tight",
    )
    plt.close(fig)

    # Chart 4: Workload Distribution
    fig, ax = plt.subplots(figsize=(8, max(3, len(assignee_counts) * 0.4)))
    if assignee_counts:
        logins = list(assignee_counts.keys())
        issue_counts = list(assignee_counts.values())
        palette = [C_ORANGE, C_BLUE, C_MAUVE, C_GOLD, C_PINK, C_GREEN, C_GRAY]
        bar_colors = [palette[i % len(palette)] for i in range(len(logins))]
        ax.barh(logins, issue_counts, color=bar_colors, edgecolor="white", height=0.5)
        for idx, c in enumerate(issue_counts):
            ax.text(c + 0.1, idx, str(c), va="center", fontweight="bold", fontsize=10)
        ax.set_xlabel("Open Issues")
        ax.invert_yaxis()
    else:
        ax.text(
            0.5, 0.5, "No assignees", ha="center", va="center",
            transform=ax.transAxes,
        )
    ax.set_title("Open Issues by Assignee", fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(
        os.path.join(charts_dir, "workload_distribution.png"),
        dpi=150, bbox_inches="tight",
    )
    plt.close(fig)

    # Chart 5: Stale Issues Age
    fig, ax = plt.subplots(figsize=(10, max(3, len(stale_issues) * 0.45)))
    if stale_issues:
        stale_sorted = sorted(stale_issues, key=lambda i: parse_dt(i["updatedAt"]))
        stale_labels = [
            truncate(f"#{i['number']} {i['title']}", 45)
            + f" ({assignee_names(i['assignees'])})"
            for i in stale_sorted
        ]
        stale_days = [
            (end_date - parse_dt(i["updatedAt"])).days for i in stale_sorted
        ]
        norm = plt.Normalize(14, max(stale_days + [30]))
        cmap = mcolors.LinearSegmentedColormap.from_list("stale", [C_GOLD, C_PINK])
        stale_colors = [cmap(norm(d)) for d in stale_days]
        y_pos = range(len(stale_sorted))
        ax.barh(
            list(y_pos), stale_days, color=stale_colors, edgecolor="white", height=0.6,
        )
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(stale_labels, fontsize=7)
        for idx, d in enumerate(stale_days):
            ax.text(d + 0.3, idx, f"{d}d", va="center", fontsize=8)
        ax.set_xlabel("Days Since Last Update")
        ax.invert_yaxis()
    else:
        ax.text(
            0.5, 0.5, "No stale issues", ha="center", va="center",
            transform=ax.transAxes,
        )
    ax.set_title(
        "Stale Issues \u2014 Days Since Last Update", fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(
        os.path.join(charts_dir, "stale_issues.png"), dpi=150, bbox_inches="tight",
    )
    plt.close(fig)

    print("Charts generated successfully.")


# --- Markdown report ---
def generate_markdown(
    output_dir, charts_dir, today, start_date, epics, closed_in_period,
    opened_in_period, in_progress, needs_review, merged_in_period, draft_prs,
    stale_issues, non_epic_open, all_open_prs, end_date, blockers,
):
    lines = []
    lines.append(f"# Profiling Scrum Status \u2014 {today}")
    lines.append("")
    lines.append(
        f"**Reporting period:** {start_date.strftime('%Y-%m-%d')} \u2192 {today}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Epic Progress
    lines.append("## Epic Progress")
    lines.append("")
    lines.append("![Epic Progress](charts/epic_progress.png)")
    lines.append("")
    lines.append("| Epic | Owner | Progress | Status |")
    lines.append("|------|-------|----------|--------|")
    for e in epics:
        prog = (
            f"{e['done']}/{e['total']} ({e['pct']}%)" if e["total"] > 0 else "no tasks"
        )
        lines.append(
            f"| #{e['number']} {e['title']} | {e['assignees']}"
            f" | {prog} | {status_emoji(e['pct'])} |"
        )
    lines.append("")
    lines.append(
        "Status emoji key: \U0001f7e2 on track (>60%),"
        " \U0001f7e1 in progress (20-60%),"
        " \U0001f534 blocked or behind (<20%)"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Issues Closed
    lines.append("## Issues Closed")
    lines.append("")
    if closed_in_period:
        lines.append("| Issue | Title | Closed by | Date |")
        lines.append("|-------|-------|-----------|------|")
        for i in sorted(
            closed_in_period, key=lambda x: x.get("closedAt", ""), reverse=True,
        ):
            lines.append(
                f"| #{i['number']} | {i['title']}"
                f" | {assignee_names(i.get('assignees', []))}"
                f" | {fmt_date(i.get('closedAt'))} |"
            )
    else:
        lines.append("None this period.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Issues Opened
    lines.append("## Issues Opened")
    lines.append("")
    if opened_in_period:
        lines.append("| Issue | Title | Assignee | Date |")
        lines.append("|-------|-------|----------|------|")
        for i in sorted(
            opened_in_period, key=lambda x: x.get("createdAt", ""), reverse=True,
        ):
            lines.append(
                f"| #{i['number']} | {i['title']}"
                f" | {assignee_names(i.get('assignees', []))}"
                f" | {fmt_date(i.get('createdAt'))} |"
            )
    else:
        lines.append("None this period.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Issues In Progress
    lines.append("## Issues In Progress")
    lines.append("")
    if in_progress:
        lines.append("| Issue | Title | Assignee | Last updated |")
        lines.append("|-------|-------|----------|--------------|")
        for i in sorted(
            in_progress, key=lambda x: x.get("updatedAt", ""), reverse=True,
        ):
            lines.append(
                f"| #{i['number']} | {i['title']}"
                f" | {assignee_names(i.get('assignees', []))}"
                f" | {fmt_date(i.get('updatedAt'))} |"
            )
    else:
        lines.append("None this period.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # PRs Needing Review
    lines.append("## PRs Needing Review")
    lines.append("")
    if needs_review:
        lines.append("| PR | Title | Author | Waiting since | Reviewers |")
        lines.append("|----|-------|--------|---------------|-----------|")
        for pr in sorted(needs_review, key=lambda x: x.get("createdAt", "")):
            author = pr["author"]["login"]
            rr = ", ".join(
                f"@{r.get('login', '')}" for r in pr.get("reviewRequests", [])
            )
            days_waiting = (end_date - parse_dt(pr["createdAt"])).days
            flag = " (stale)" if days_waiting > 3 else ""
            lines.append(
                f"| #{pr['number']} | {pr['title']} | @{author}"
                f" | {fmt_date(pr['createdAt'])}{flag} | {rr} |"
            )
    else:
        lines.append("None this period.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # PRs Merged
    lines.append("## PRs Merged")
    lines.append("")
    if merged_in_period:
        lines.append("| PR | Title | Author | Merged |")
        lines.append("|----|-------|--------|--------|")
        for pr in sorted(
            merged_in_period, key=lambda x: x.get("mergedAt", ""), reverse=True,
        ):
            lines.append(
                f"| #{pr['number']} | {pr['title']}"
                f" | @{pr['author']['login']} | {fmt_date(pr.get('mergedAt'))} |"
            )
    else:
        lines.append("None this period.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Draft PRs
    lines.append("## Draft PRs")
    lines.append("")
    if draft_prs:
        lines.append("| PR | Title | Author | Created |")
        lines.append("|----|-------|--------|---------|")
        for pr in draft_prs:
            lines.append(
                f"| #{pr['number']} | {pr['title']}"
                f" | @{pr['author']['login']} | {fmt_date(pr['createdAt'])} |"
            )
    else:
        lines.append("None this period.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Blockers & Risks
    lines.append("## Blockers & Risks")
    lines.append("")
    for b in blockers:
        lines.append(b)
    lines.append("")
    lines.append("---")
    lines.append("")

    # Key Numbers
    lines.append("## Key Numbers")
    lines.append("")
    lines.append(f"- **Open issues:** {len(non_epic_open)} (+ {len(epics)} epics)")
    lines.append(f"- **Closed this period:** {len(closed_in_period)}")
    lines.append(f"- **Open PRs (profiling):** {len(all_open_prs)}")
    lines.append(f"- **PRs needing review:** {len(needs_review)}")
    lines.append(f"- **PRs merged this period:** {len(merged_in_period)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Visualizations
    lines.append("## Visualizations")
    lines.append("")
    for name, fname in [
        ("Issue Flow", "issue_flow.png"),
        ("PR Pipeline", "pr_pipeline.png"),
        ("Workload Distribution", "workload_distribution.png"),
        ("Stale Issues", "stale_issues.png"),
    ]:
        lines.append(f"### {name}")
        lines.append(f"![{name}](charts/{fname})")
        lines.append("")

    md_path = os.path.join(output_dir, f"scrum-profiling-{today}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Markdown report saved: {md_path}")
    return md_path


# --- PDF document ---
class ScrumPDF(FPDF):
    """Custom PDF with header/footer for scrum reports."""

    # Preferred TTF font paths — searched in order.
    _FONT_PATHS = {
        "darwin": {
            "": "/System/Library/Fonts/Supplemental/Arial.ttf",
            "B": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "I": "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
            "BI": "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
        },
        "linux": {
            "": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "B": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "I": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "BI": "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        },
    }

    def __init__(self, title_text, subtitle_text):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._title_text = title_text
        self._subtitle_text = subtitle_text
        self.set_auto_page_break(auto=True, margin=15)
        self._register_fonts()

    def _register_fonts(self):
        """Register a Unicode TTF font family, with fallback to built-in."""
        import platform
        plat = platform.system().lower()
        paths = self._FONT_PATHS.get(plat, {})
        self._font_family = "Helvetica"  # fallback
        if paths and os.path.exists(paths.get("", "")):
            family = "ScrumFont"
            for style, path in paths.items():
                if os.path.exists(path):
                    self.add_font(family, style, path)
            self._font_family = family

    def _set_font(self, style="", size=10):
        self.set_font(self._font_family, style, size)

    def header(self):
        self._set_font("B", 9)
        self.set_text_color(77, 92, 94)  # C_GRAY
        self.cell(0, 6, self._title_text, align="L")
        self.cell(0, 6, self._subtitle_text, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self._set_font("I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_heading(self, text):
        self._set_font("B", 14)
        self.set_text_color(77, 92, 94)
        self.ln(4)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(230, 130, 68)  # C_ORANGE
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 80, self.get_y())
        self.set_line_width(0.2)
        self.ln(3)

    def sub_heading(self, text):
        self._set_font("B", 11)
        self.set_text_color(115, 71, 97)  # C_MAUVE
        self.ln(2)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self._set_font("", 9)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5, text)

    def bullet(self, text):
        self._set_font("", 9)
        self.set_text_color(50, 50, 50)
        self.cell(5, 5, "\u2022 ")
        self.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")

    def add_chart_image(self, charts_dir, name):
        path = os.path.join(charts_dir, name)
        if os.path.exists(path):
            avail = 297 - 15 - self.get_y()  # A4 height minus margin
            if avail < 50:
                self.add_page()
            self.image(path, x=10, w=190)
            self.ln(3)

    def add_data_table(self, headers, rows, col_widths=None):
        if not col_widths:
            total = 190
            col_widths = [total / len(headers)] * len(headers)

        # Check if table fits; if not, add a page
        row_h = 6
        needed = (1 + len(rows)) * row_h + 5
        avail = 297 - 15 - self.get_y()
        if needed > avail:
            self.add_page()

        # Header row
        self._set_font("B", 8)
        self.set_fill_color(230, 130, 68)  # C_ORANGE
        self.set_text_color(255, 255, 255)
        for j, h in enumerate(headers):
            self.cell(col_widths[j], row_h, h, border=1, fill=True)
        self.ln()

        # Data rows
        self._set_font("", 7)
        self.set_text_color(50, 50, 50)
        for i, row in enumerate(rows):
            if i % 2 == 0:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            max_lines = 1
            for j, val in enumerate(row):
                txt = str(val)
                # Estimate lines needed
                char_w = col_widths[j] / 2.2  # approx chars per line at font 7
                lines_needed = max(1, int(len(txt) / max(char_w, 1)) + 1)
                max_lines = max(max_lines, lines_needed)
            cell_h = row_h * max_lines

            # Check page break
            if self.get_y() + cell_h > 297 - 15:
                self.add_page()
                # Re-print header
                self._set_font("B", 8)
                self.set_fill_color(230, 130, 68)
                self.set_text_color(255, 255, 255)
                for j, h in enumerate(headers):
                    self.cell(col_widths[j], row_h, h, border=1, fill=True)
                self.ln()
                self._set_font("", 7)
                self.set_text_color(50, 50, 50)
                if i % 2 == 0:
                    self.set_fill_color(245, 245, 245)
                else:
                    self.set_fill_color(255, 255, 255)

            for j, val in enumerate(row):
                self.cell(col_widths[j], cell_h, str(val)[:60], border=1, fill=True)
            self.ln()
        self.ln(2)


def generate_pdf(
    output_dir, charts_dir, today, start_date, epics, closed_in_period,
    opened_in_period, in_progress, needs_review, merged_in_period, draft_prs,
    blockers, non_epic_open, all_open_prs, end_date,
):
    title_text = f"Profiling Scrum Status \u2014 {today}"
    subtitle_text = f"Reporting period: {start_date.strftime('%Y-%m-%d')} to {today}"

    pdf = ScrumPDF(title_text, subtitle_text)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title page
    pdf._set_font("B", 22)
    pdf.set_text_color(77, 92, 94)
    pdf.ln(30)
    pdf.cell(0, 12, "Profiling Scrum Status", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf._set_font("", 14)
    pdf.set_text_color(230, 130, 68)
    pdf.cell(0, 10, today, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf._set_font("", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(
        0, 8, f"{start_date.strftime('%Y-%m-%d')}  to  {today}",
        align="C", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(10)

    # Key Numbers box
    pdf.set_fill_color(245, 245, 245)
    pdf.set_draw_color(200, 200, 200)
    box_x, box_y = 40, pdf.get_y()
    pdf.rect(box_x, box_y, 130, 40, style="DF")
    pdf.set_xy(box_x + 5, box_y + 3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(77, 92, 94)
    pdf.cell(120, 6, "Key Numbers", new_x="LMARGIN", new_y="NEXT")
    pdf._set_font("", 10)
    pdf.set_text_color(50, 50, 50)
    key_nums = [
        f"Open issues: {len(non_epic_open)} (+ {len(epics)} epics)",
        f"Closed this period: {len(closed_in_period)}",
        f"Open PRs (profiling): {len(all_open_prs)}",
        f"PRs needing review: {len(needs_review)}",
        f"PRs merged this period: {len(merged_in_period)}",
    ]
    for kn in key_nums:
        pdf.set_x(box_x + 8)
        pdf.cell(115, 5.5, f"\u2022  {kn}", new_x="LMARGIN", new_y="NEXT")

    # Epic Progress
    pdf.add_page()
    pdf.section_heading("Epic Progress")
    pdf.add_chart_image(charts_dir, "epic_progress.png")
    epic_rows = []
    for e in epics:
        prog = (
            f"{e['done']}/{e['total']} ({e['pct']}%)" if e["total"] > 0 else "no tasks"
        )
        st = (
            "on track" if e["pct"] > 60
            else "in progress" if e["pct"] >= 20
            else "behind"
        )
        epic_rows.append([f"#{e['number']} {e['title']}", e["assignees"], prog, st])
    pdf.add_data_table(
        ["Epic", "Owner", "Progress", "Status"],
        epic_rows,
        col_widths=[80, 45, 35, 30],
    )

    # Issues Closed
    pdf.section_heading("Issues Closed")
    if closed_in_period:
        rows = [
            [
                f"#{i['number']}", i["title"],
                assignee_names(i.get("assignees", [])), fmt_date(i.get("closedAt")),
            ]
            for i in sorted(
                closed_in_period, key=lambda x: x.get("closedAt", ""), reverse=True,
            )
        ]
        pdf.add_data_table(
            ["Issue", "Title", "Closed by", "Date"],
            rows,
            col_widths=[20, 80, 55, 35],
        )
    else:
        pdf.body_text("None this period.")

    # Issues Opened
    pdf.section_heading("Issues Opened")
    if opened_in_period:
        rows = [
            [
                f"#{i['number']}", i["title"],
                assignee_names(i.get("assignees", [])), fmt_date(i.get("createdAt")),
            ]
            for i in sorted(
                opened_in_period, key=lambda x: x.get("createdAt", ""), reverse=True,
            )
        ]
        pdf.add_data_table(
            ["Issue", "Title", "Assignee", "Date"],
            rows,
            col_widths=[20, 80, 55, 35],
        )
    else:
        pdf.body_text("None this period.")

    # Issues In Progress
    pdf.section_heading("Issues In Progress")
    if in_progress:
        rows = [
            [
                f"#{i['number']}", i["title"],
                assignee_names(i.get("assignees", [])), fmt_date(i.get("updatedAt")),
            ]
            for i in sorted(
                in_progress, key=lambda x: x.get("updatedAt", ""), reverse=True,
            )
        ]
        pdf.add_data_table(
            ["Issue", "Title", "Assignee", "Last Updated"],
            rows,
            col_widths=[20, 80, 55, 35],
        )
    else:
        pdf.body_text("None this period.")

    # PRs Needing Review
    pdf.section_heading("PRs Needing Review")
    if needs_review:
        rows = []
        for pr in sorted(needs_review, key=lambda x: x.get("createdAt", "")):
            rr = ", ".join(
                f"@{r.get('login', '')}" for r in pr.get("reviewRequests", [])
            )
            rows.append([
                f"#{pr['number']}", pr["title"],
                f"@{pr['author']['login']}", rr or fmt_date(pr["createdAt"]),
            ])
        pdf.add_data_table(
            ["PR", "Title", "Author", "Reviewers"],
            rows,
            col_widths=[20, 85, 45, 40],
        )
    else:
        pdf.body_text("None this period.")

    # PRs Merged
    pdf.section_heading("PRs Merged")
    if merged_in_period:
        rows = [
            [
                f"#{pr['number']}", pr["title"],
                f"@{pr['author']['login']}", fmt_date(pr.get("mergedAt")),
            ]
            for pr in sorted(
                merged_in_period, key=lambda x: x.get("mergedAt", ""), reverse=True,
            )
        ]
        pdf.add_data_table(
            ["PR", "Title", "Author", "Merged"],
            rows,
            col_widths=[20, 85, 45, 40],
        )
    else:
        pdf.body_text("None this period.")

    # Draft PRs
    pdf.section_heading("Draft PRs")
    if draft_prs:
        rows = [
            [
                f"#{pr['number']}", pr["title"],
                f"@{pr['author']['login']}", fmt_date(pr["createdAt"]),
            ]
            for pr in draft_prs
        ]
        pdf.add_data_table(
            ["PR", "Title", "Author", "Created"],
            rows,
            col_widths=[20, 85, 45, 40],
        )
    else:
        pdf.body_text("None this period.")

    # Blockers & Risks
    pdf.add_page()
    pdf.section_heading("Blockers & Risks")
    pdf.add_chart_image(charts_dir, "stale_issues.png")
    for b in blockers:
        clean = b.lstrip("- ").lstrip(" ")
        pdf.bullet(clean)

    # Visualizations
    pdf.add_page()
    pdf.section_heading("Visualizations")
    for chart_name, chart_title in [
        ("issue_flow.png", "Issue Flow"),
        ("pr_pipeline.png", "PR Pipeline"),
        ("workload_distribution.png", "Workload Distribution"),
    ]:
        pdf.sub_heading(chart_title)
        pdf.add_chart_image(charts_dir, chart_name)

    pdf_path = os.path.join(output_dir, f"scrum-profiling-{today}.pdf")
    pdf.output(pdf_path)
    print(f"PDF report saved: {pdf_path}")
    return pdf_path


# --- Main ---
def main():
    args = parse_args()

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    today = end_date.strftime("%Y-%m-%d")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = args.output_dir or script_dir
    data_dir = args.data_dir or "/tmp"
    charts_dir = os.path.join(output_dir, "charts")

    os.makedirs(charts_dir, exist_ok=True)

    def in_period(dt_str):
        dt = parse_dt(dt_str)
        return dt and dt >= start_date

    # Fetch data if not cached
    data_file = os.path.join(data_dir, "profiling_open_issues.json")
    if not os.path.exists(data_file):
        fetch_all_data(data_dir)
    else:
        print(f"Using cached data from {data_dir}")

    # Load data
    open_issues = load_json(os.path.join(data_dir, "profiling_open_issues.json"))
    closed_issues = load_json(os.path.join(data_dir, "profiling_closed_issues.json"))
    epics_raw = load_json(os.path.join(data_dir, "profiling_epics.json"))
    prs_label = load_json(os.path.join(data_dir, "profiling_prs_label.json"))
    prs_search = load_json(os.path.join(data_dir, "profiling_prs_search.json"))
    prs_merged_raw = load_json(os.path.join(data_dir, "profiling_prs_merged.json"))

    # Classify
    epic_numbers = {e["number"] for e in epics_raw}
    non_epic_open = [i for i in open_issues if i["number"] not in epic_numbers]

    closed_in_period = [i for i in closed_issues if in_period(i.get("closedAt"))]
    opened_in_period = [
        i for i in non_epic_open if in_period(i.get("createdAt"))
    ]
    opened_numbers = {i["number"] for i in opened_in_period}
    in_progress = [
        i for i in non_epic_open
        if i.get("assignees") and in_period(i.get("updatedAt"))
        and i["number"] not in opened_numbers
    ]

    stale_issues = [
        i for i in non_epic_open
        if i.get("assignees")
        and parse_dt(i.get("updatedAt"))
        and (end_date - parse_dt(i["updatedAt"])).days >= 14
    ]

    # Epics
    epics = []
    for e in epics_raw:
        body = e.get("body", "") or ""
        done = body.count("- [x]") + body.count("- [X]")
        total = done + body.count("- [ ]")
        pct = int(done / total * 100) if total > 0 else 0
        epics.append({
            "number": e["number"],
            "title": e["title"],
            "assignees": assignee_names(e.get("assignees", [])),
            "done": done,
            "total": total,
            "pct": pct,
        })

    # PRs
    seen_pr = set()
    all_open_prs = []
    for pr in prs_label + prs_search:
        if pr["number"] not in seen_pr:
            seen_pr.add(pr["number"])
            all_open_prs.append(pr)
    all_open_prs = [pr for pr in all_open_prs if is_profiling_pr(pr)]

    draft_prs = [pr for pr in all_open_prs if pr.get("isDraft")]
    non_draft_prs = [pr for pr in all_open_prs if not pr.get("isDraft")]

    needs_review = []
    approved_prs = []
    for pr in non_draft_prs:
        reviews = pr.get("reviews", [])
        states = [r["state"] for r in reviews]
        if "APPROVED" in states and states[-1] == "APPROVED":
            approved_prs.append(pr)
        else:
            needs_review.append(pr)

    merged_in_period = [
        pr for pr in prs_merged_raw
        if in_period(pr.get("mergedAt")) and is_profiling_pr(pr)
    ]

    # Workload
    assignee_counts = {}
    for i in non_epic_open:
        for a in i.get("assignees", []):
            login = a["login"]
            assignee_counts[login] = assignee_counts.get(login, 0) + 1
    assignee_counts = dict(sorted(assignee_counts.items(), key=lambda x: -x[1]))

    # Blockers
    blockers = []
    if stale_issues:
        blockers.append(
            f"- **{len(stale_issues)} stale issues**"
            " (assigned, no update in 14+ days):"
        )
        for i in stale_issues[:5]:
            days = (end_date - parse_dt(i["updatedAt"])).days
            blockers.append(
                f"  - #{i['number']} {truncate(i['title'], 50)}"
                f" ({assignee_names(i.get('assignees', []))}) \u2014 {days}d stale"
            )
        if len(stale_issues) > 5:
            blockers.append(f"  - ...and {len(stale_issues) - 5} more")

    unassigned_epics = [e for e in epics if e["assignees"] == "unassigned"]
    if unassigned_epics:
        blockers.append(
            f"- **{len(unassigned_epics)} unassigned epics** need owners: "
            + ", ".join(f"#{e['number']}" for e in unassigned_epics)
        )

    no_task_epics = [e for e in epics if e["total"] == 0]
    if no_task_epics:
        blockers.append(
            f"- **{len(no_task_epics)} epics have no sub-tasks**"
            " defined \u2014 hard to track progress"
        )

    if not merged_in_period:
        blockers.append(
            "- **No profiling PRs merged this period** \u2014 velocity concern"
        )

    if not blockers:
        blockers.append("None identified this period.")

    # Generate
    generate_charts(
        charts_dir, epics, opened_in_period, closed_in_period, in_progress,
        draft_prs, needs_review, approved_prs, merged_in_period,
        assignee_counts, stale_issues, start_date, today, end_date,
    )

    generate_markdown(
        output_dir, charts_dir, today, start_date, epics, closed_in_period,
        opened_in_period, in_progress, needs_review, merged_in_period, draft_prs,
        stale_issues, non_epic_open, all_open_prs, end_date, blockers,
    )

    generate_pdf(
        output_dir, charts_dir, today, start_date, epics, closed_in_period,
        opened_in_period, in_progress, needs_review, merged_in_period, draft_prs,
        blockers, non_epic_open, all_open_prs, end_date,
    )

    # Summary
    print(f"\n{'=' * 40}")
    print(f"Report generated for {today}")
    print(f"{'=' * 40}")
    print(f"Open issues: {len(non_epic_open)} (+ {len(epics)} epics)")
    print(f"Closed this period: {len(closed_in_period)}")
    print(f"Open PRs (profiling): {len(all_open_prs)}")
    print(f"PRs needing review: {len(needs_review)}")
    print(f"PRs merged this period: {len(merged_in_period)}")
    print(f"Stale issues: {len(stale_issues)}")


if __name__ == "__main__":
    main()
