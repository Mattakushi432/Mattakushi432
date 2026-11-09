"""Generate profile stat cards: assets/{stats,languages}.svg (EN) and *.uk.svg (UA).

Stdlib only. Uses GITHUB_TOKEN if set (needed for commit counts and to avoid
the 60 req/h anonymous limit). Run from the repository root:

    python scripts/gen_stats.py Mattakushi432
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUT = Path(__file__).resolve().parent.parent / "assets"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#663399", "Shell": "#89e051",
    "PowerShell": "#5391FE", "Dockerfile": "#384d54", "C#": "#178600",
    "Mako": "#7e858d", "Jinja": "#a52a22",
}
FALLBACK = ["#22d3ee", "#a78bfa", "#e879f9", "#4ade80", "#fbbf24", "#f87171"]
SKIP_LANGS = {"HTML", "CSS", "Mako", "Dockerfile"}  # markup/config skews the chart


def req(url: str, data: dict | None = None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=30) as r:
        return json.load(r)


def collect(user: str) -> dict:
    profile = req(f"{API}/users/{user}")
    repos, page = [], 1
    while True:
        batch = req(f"{API}/users/{user}/repos?per_page=100&page={page}&type=owner")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]

    langs: dict[str, int] = {}
    for r in own:
        try:
            breakdown = req(r["languages_url"])
        except urllib.error.HTTPError:  # rate-limited: approximate by primary language
            breakdown = {r["language"]: r["size"] * 1024} if r["language"] else {}
        for name, size in breakdown.items():
            langs[name] = langs.get(name, 0) + size

    commits = None
    if TOKEN:
        q = """query($u:String!){user(login:$u){contributionsCollection{
               totalCommitContributions restrictedContributionsCount
               totalPullRequestContributions}}}"""
        c = req(f"{API}/graphql", {"query": q, "variables": {"u": user}})
        cc = c["data"]["user"]["contributionsCollection"]
        commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
        prs = cc["totalPullRequestContributions"]
    else:
        prs = None

    created = datetime.fromisoformat(profile["created_at"].replace("Z", "+00:00"))
    return {
        "own": len(own),
        "forks": len(repos) - len(own),
        "stars": sum(r["stargazers_count"] for r in own),
        "followers": profile["followers"],
        "years": max(1, (datetime.now(timezone.utc) - created).days // 365),
        "commits": commits,
        "prs": prs,
        "langs": langs,
    }


STYLE = """<style>
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
.sans{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif}
.h{font-size:11px;fill:#64748b;letter-spacing:1.5px}
.v{font-size:26px;font-weight:800;fill:#e2e8f0}
.l{font-size:12px;fill:#94a3b8}
.n{font-size:12.5px;fill:#cbd5e1}
.p{font-size:12px;fill:#64748b}
.in{animation:in .8s ease-out both}
@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion: reduce){.in{animation:none}}
</style>"""


def frame(w: int, h: int, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">{STYLE}'
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="14" fill="#0b1020" '
        f'stroke="#334155" stroke-opacity=".7"/>'
        f'<text x="22" y="30" class="mono h">{escape(title.upper())}</text>{body}</svg>'
    )


T = {
    "en": {"own": "own repositories", "stars": "stars earned", "commits": "commits this year",
           "forks": "forks studied", "followers": "followers", "prs": "pull requests",
           "years": "on GitHub", "langs": "languages", "y": "y",
           "t_stats": "GitHub at a glance", "t_langs": "Languages · own code"},
    "uk": {"own": "власних репозиторіїв", "stars": "зірок отримано", "commits": "комітів цього року",
           "forks": "форків вивчено", "followers": "підписників", "prs": "pull requests",
           "years": "на GitHub", "langs": "мов", "y": "р",
           "t_stats": "GitHub коротко", "t_langs": "Мови · власний код"},
}


def stats_svg(s: dict, lang: str = "en") -> str:
    t = T[lang]
    yrs = f'{s["years"]}{t["y"]}'
    has = s["commits"] is not None
    items = [
        (s["own"], t["own"]),
        (s["stars"], t["stars"]),
        (s["commits"] if has else s["forks"], t["commits"] if has else t["forks"]),
        (s["followers"], t["followers"]),
        (s["prs"] if has else yrs, t["prs"] if has else t["years"]),
        (yrs if has else len(s["langs"]), t["years"] if has else t["langs"]),
    ]
    accents = ["#22d3ee", "#a78bfa", "#e879f9", "#4ade80", "#fbbf24", "#f87171"]
    body = ""
    for i, (val, label) in enumerate(items):
        col, row = i % 3, i // 3
        x, y = 22 + col * 140, 62 + row * 70
        body += (
            f'<g class="in" style="animation-delay:{i*0.08:.2f}s">'
            f'<rect x="{x}" y="{y}" width="3" height="44" rx="1.5" fill="{accents[i]}"/>'
            f'<text x="{x+14}" y="{y+24}" class="sans v">{escape(str(val))}</text>'
            f'<text x="{x+14}" y="{y+42}" class="sans l">{escape(label)}</text></g>'
        )
    return frame(440, 210, t["t_stats"], body)


def langs_svg(s: dict, lang: str = "en") -> str:
    langs = {k: v for k, v in s["langs"].items() if k not in SKIP_LANGS}
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    colors = [LANG_COLORS.get(n, FALLBACK[i % len(FALLBACK)]) for i, (n, _) in enumerate(top)]

    bar, x, width = "", 22.0, 396.0
    bar += f'<clipPath id="c"><rect x="22" y="50" width="{width}" height="10" rx="5"/></clipPath><g clip-path="url(#c)">'
    for (name, size), color in zip(top, colors):
        w = width * size / total
        bar += f'<rect x="{x:.2f}" y="50" width="{w + 0.5:.2f}" height="10" fill="{color}"/>'
        x += w
    bar += f'<rect x="{x:.2f}" y="50" width="{max(0, 418 - x):.2f}" height="10" fill="#1e293b"/></g>'

    rows = ""
    for i, ((name, size), color) in enumerate(zip(top, colors)):
        col, row = i % 2, i // 2
        cx, cy = 22 + col * 200, 92 + row * 34
        rows += (
            f'<g class="in" style="animation-delay:{i*0.08:.2f}s">'
            f'<circle cx="{cx+6}" cy="{cy-4}" r="5" fill="{color}"/>'
            f'<text x="{cx+18}" y="{cy}" class="sans n">{escape(name)}</text>'
            f'<text x="{cx+180}" y="{cy}" text-anchor="end" class="mono p">{size/total*100:.1f}%</text></g>'
        )
    return frame(440, 210, T[lang]["t_langs"], bar + rows)


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else "Mattakushi432"
    s = collect(user)
    OUT.mkdir(exist_ok=True)
    for lang in T:
        suffix = "" if lang == "en" else f".{lang}"
        (OUT / f"stats{suffix}.svg").write_text(stats_svg(s, lang), encoding="utf-8")
        (OUT / f"languages{suffix}.svg").write_text(langs_svg(s, lang), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k != "langs"}), file=sys.stderr)


if __name__ == "__main__":
    main()
