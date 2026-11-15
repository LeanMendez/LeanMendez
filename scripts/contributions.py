"""Render assets/contributions.svg from the GitHub contribution calendar.

Usage: GITHUB_TOKEN=... GH_LOGIN=LeanMendez python3 scripts/contributions.py
Standard library only, so it runs on a bare GitHub Actions runner.
"""

import base64
import datetime as dt
import html
import json
import os
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "contributions.svg"
LOGIN = os.environ.get("GH_LOGIN", "LeanMendez")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""

BG, LINE, DIM, CYAN = "#0c0812", "#2a1d36", "#8a7f95", "#62d8ff"
EMPTY = "#1a1224"
# Even the lowest level must read clearly against EMPTY: a single commit is still a marked day.
LEVELS = {
    "FIRST_QUARTILE": "#7b5cff",
    "SECOND_QUARTILE": "#a64dff",
    "THIRD_QUARTILE": "#e04bff",
    "FOURTH_QUARTILE": "#ff4f9a",
}
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def fetch(token):
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        payload = json.load(res)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def font_css():
    data = base64.b64encode((ROOT / "scripts" / "fonts" / "dvsm-700.woff2").read_bytes()).decode()
    return f"@font-face{{font-family:'DVM';src:url(data:font/woff2;base64,{data}) format('woff2');font-weight:700}}"


def label(x, y, s):
    return f'<text x="{x}" y="{y}" font-size="9.5" font-weight="700" fill="{DIM}">{s}</text>'


def color_for(day):
    if not day["contributionCount"]:
        return EMPTY
    return LEVELS.get(day["contributionLevel"], LEVELS["FIRST_QUARTILE"])


def render(cal):
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    W, H = 840, 154
    cell, gap = 11, 3
    step = cell + gap
    gx, gy = 62, 38
    b = []

    for row, name in ((1, "MON"), (3, "WED"), (5, "FRI")):
        b.append(label(24, gy + row * step + 9, name))
    last_month = None
    for col, week in enumerate(weeks):
        first = dt.date.fromisoformat(week[0]["date"])
        if first.month != last_month and col < len(weeks) - 2:
            if last_month is not None or first.day <= 7:
                b.append(label(gx + col * step, gy - 10, MONTHS[first.month - 1]))
            last_month = first.month
        for d in week:
            row = dt.date.fromisoformat(d["date"]).isoweekday() % 7
            fill = color_for(d)
            extra = f' stroke="{LINE}"' if fill == EMPTY else ' filter="url(#gl)"'
            b.append(
                f'<rect x="{gx + col * step}" y="{gy + row * step}" width="{cell}" height="{cell}" rx="2" '
                f'fill="{fill}"{extra}><title>{d["contributionCount"]} on {d["date"]}</title></rect>'
            )
    grid_w = len(weeks) * step - gap
    b.append(
        f'<rect class="scan" x="{gx - 2}" y="{gy - 3}" width="2" height="{7 * step + 3}" fill="{CYAN}" '
        f'opacity=".8" filter="url(#gl)"/>'
    )

    css = (
        font_css()
        + "text{font-family:'DVM','DejaVu Sans Mono',ui-monospace,monospace}"
        + f".scan{{animation:scan 7s linear infinite}}@keyframes scan{{0%{{transform:translateX(0);opacity:0}}"
        f"4%{{opacity:.8}}96%{{opacity:.8}}100%{{transform:translateX({grid_w + 4}px);opacity:0}}}}"
        + "@media (prefers-reduced-motion:reduce){.scan{display:none}}"
    )
    defs = (
        '<defs><filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '<pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#1d1428"/></pattern></defs>'
    )
    title = f"{cal['totalContributions']} GitHub contributions in the last 12 months."
    frame = f'x="1" y="1" width="{W - 2}" height="{H - 2}" rx="8"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
        f'aria-label="{html.escape(title)}"><title>{html.escape(title)}</title><style>{css}</style>{defs}'
        f'<rect {frame} fill="{BG}"/><rect {frame} fill="url(#grid)"/>{"".join(b)}'
        f'<rect {frame} fill="none" stroke="{LINE}" stroke-width="1.5"/></svg>'
    )


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    OUT.write_text(render(fetch(token)), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
