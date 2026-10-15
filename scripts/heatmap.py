#!/usr/bin/env python3
"""Draw the Pugnola contribution calendar as an SVG (Mezzanotte palette).

Data comes from GitHub's own GraphQL contribution calendar for the public
profile (private contributions are included as anonymous counts because the
"Private contributions" profile setting is on). Works with the default
GITHUB_TOKEN in Actions; no personal token needed.

usage: GITHUB_TOKEN=... heatmap.py <theme> <palette> <out.svg>
  theme:   dark | light
  palette: red
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request

LOGIN = "Pugnola"

PALETTES = {
    ("dark", "red"): ["#1C1624", "#4A0E16", "#7E1019", "#B3121F", "#FF2A3A"],
    ("light", "red"): ["#ebedf0", "#FFC9C9", "#FF8A93", "#E0303F", "#8A0E18"],
}
TEXT = {"dark": "#8b949e", "light": "#57606a"}
MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(token: str) -> tuple[int, list[list[tuple[str, int]]]]:
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-heatmap",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [
        [(d["date"], d["contributionCount"]) for d in w["contributionDays"]]
        for w in cal["weeks"]
    ]
    return cal["totalContributions"], weeks


def levels(weeks):
    vals = sorted(c for w in weeks for _, c in w if c > 0)
    if not vals:
        return lambda c: 0
    q = lambda p: vals[min(len(vals) - 1, int(len(vals) * p))]
    t1, t2, t3 = q(0.25), q(0.5), q(0.75)

    def level(c: int) -> int:
        if c == 0:
            return 0
        if c <= t1:
            return 1
        if c <= t2:
            return 2
        if c <= t3:
            return 3
        return 4

    return level


def render(total: int, weeks, theme: str, palette: str) -> str:
    colors = PALETTES[(theme, palette)]
    text = TEXT[theme]
    cell, gap = 11, 3
    step = cell + gap
    left, top = 34, 22
    level = levels(weeks)
    width = left + len(weeks) * step + 4
    height = top + 7 * step + 30

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="son bir yılda {total} katkı">',
        "<style>"
        + "".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(colors))
        + f'text{{fill:{text};font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:10px}}'
        + "</style>",
    ]

    # month labels: first week whose first day falls in a new month
    seen = None
    for wi, week in enumerate(weeks):
        first = dt.date.fromisoformat(week[0][0])
        if first.month != seen:
            if seen is not None or first.day <= 7:
                out.append(f'<text x="{left + wi * step}" y="12">{MONTHS[first.month - 1]}</text>')
            seen = first.month

    for row, label in ((1, "Pzt"), (3, "Çar"), (5, "Cum")):
        out.append(f'<text x="0" y="{top + row * step + 9}">{label}</text>')

    for wi, week in enumerate(weeks):
        for di, (date, count) in enumerate(week):
            wd = (dt.date.fromisoformat(date).weekday() + 1) % 7  # Sunday = 0
            x = left + wi * step
            y = top + wd * step
            out.append(
                f'<rect class="l{level(count)}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2">'
                f"<title>{date}: {count} katkı</title></rect>"
            )

    fy = top + 7 * step + 18
    out.append(f'<text x="{left}" y="{fy}">son bir yılda {total:,} katkı</text>')
    lx = width - 4 - 5 * step - 58
    out.append(f'<text x="{lx - 22}" y="{fy}">az</text>')
    for i in range(5):
        out.append(f'<rect class="l{i}" x="{lx + i * step}" y="{fy - 9}" width="{cell}" height="{cell}" rx="2"/>')
    out.append(f'<text x="{lx + 5 * step + 4}" y="{fy}">çok</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    theme, palette, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("PROFILE_TOKEN")
    if not token:
        print("GITHUB_TOKEN missing", file=sys.stderr)
        return 1
    total, weeks = fetch(token)
    svg = render(total, weeks, theme, palette)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{out_path}: {total} contributions, {len(weeks)} weeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
