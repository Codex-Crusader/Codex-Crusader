"""
Refresh the Hall of Relics and the "recently forged" line in README.md.

The relic list is curated by hand below; stars and rarity come from the
GitHub API each day. Standard library only.
"""

import json
import os
import urllib.request
from urllib.parse import quote

USERNAME = "Codex-Crusader"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
SITE = "https://codex-crusader.github.io"

# (repo, display name, one-line pitch, write-up path on the portfolio or None)
RELICS = [
    ("unstrung", "Unstrung", "Local AI characters that remember you. Rust, Tauri and React; nothing leaves your machine.", "/writing/rust-local-ai-memory-management/"),
    ("digital-footprint-cleaner", "Digital Footprint Cleaner", "Finds and erases your digital footprint across public websites. Flask, fully automated.", None),
    ("t-rustable", "T-Rustable", "Offline, mod-first PDF editor for Linux and Windows. Rust and Svelte.", "/writing/i-hate-rust/"),
    ("Rice-sauce-hair", "Rice-sauce-hair", "Arch + Hyprland desktop with a local AI companion that plans, acts safely and hands hard tasks to Claude Code.", "/writing/local-ai-desktop-companion-hyprland/"),
    ("azlite_type_chess_bot", "AZLite", "AlphaZero-style chess engine in PyTorch that learns only from self-play.", "/writing/alphazero-chess-engine-python/"),
    ("bruhswer-the-homebrew-pseudo-browser", "bruhswer", "Hardened Edge with fail-closed startup and download quarantine. Says NOT ENFORCEABLE when it cannot.", "/writing/browser-hardening/"),
    ("Uni-basketball-ETL-pipeline", "NCAA Predictor", "NCAA predictor: ESPN data, six models, data leakage removed, live dashboard.", "/writing/data-leakage-basketball-model/"),
    ("visitor-access-project", "Visitor Access Study", "UX study of campus visitor entry: interviews, card sorts, tree tests and a new information architecture.", "/writing/campus-visitor-access-ux-study/"),
]

# Live links are listed by hand: a repo's homepage field can point at a dead site.
LIVE = {
    "unstrung": f"{SITE}/unstrung/",
    "Uni-basketball-ETL-pipeline": "https://uni-basketball-etl-pipeline.onrender.com/",
}

# (minimum stars, label, colour from the portfolio's rarity scale)
RARITY = [
    (10, "Legendary", "F0A23A"),
    (5, "Epic", "B784F2"),
    (2, "Rare", "74AEF2"),
    (0, "Common", "A9A396"),
]

SKIP_RECENT = {USERNAME.lower(), f"{USERNAME.lower()}.github.io"}


def fetch_all_repos():
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{USERNAME}-readme"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as res:
            batch = json.loads(res.read().decode())
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def rarity(stars):
    return next((label, colour) for floor, label, colour in RARITY if stars >= floor)


def badge(stars):
    label, colour = rarity(stars)
    return f"![{label}](https://img.shields.io/badge/{quote(f'★ {stars}')}-{label}-{colour}?style=flat-square)"


def build_relics(repos):
    by_name = {r["name"]: r for r in repos if not r.get("private")}
    rows = []
    for name, title, pitch, post in RELICS:
        repo = by_name.get(name)
        if repo is None:
            continue  # renamed, deleted or made private: drop it rather than link a 404
        links = f"[code]({repo['html_url']})"
        if name in LIVE:
            links += f" · [live]({LIVE[name]})"
        if post:
            links += f" · [post]({SITE}{post})"
        rows.append((repo["stargazers_count"], f"| **{title}** | {badge(repo['stargazers_count'])} | {pitch} | {links} |"))

    rows.sort(key=lambda row: -row[0])
    header = ["| Relic | Rarity | What it does | Links |", "|---|---|---|---|"]
    return "\n".join(header + [line for _, line in rows])


def build_recent(repos):
    owned = [
        r for r in repos
        if not r["fork"] and not r.get("private") and r["name"].lower() not in SKIP_RECENT
    ]
    owned.sort(key=lambda r: r["pushed_at"], reverse=True)
    items = [f"[{r['name']}]({r['html_url']}) ({r['pushed_at'][:10]})" for r in owned[:3]]
    return "**Recently forged:** " + " · ".join(items)


def replace_block(content, tag, body):
    start, end = f"<!-- {tag}_START -->", f"<!-- {tag}_END -->"
    if start not in content or end not in content:
        raise SystemExit(f"Markers {start} / {end} not found in README.md.")
    before = content.split(start)[0]
    after = content.split(end)[1]
    return f"{before}{start}\n{body}\n{end}{after}"


def main():
    repos = fetch_all_repos()
    with open("README.md", encoding="utf-8") as f:
        content = f.read()
    content = replace_block(content, "REPOS", build_relics(repos))
    content = replace_block(content, "RECENT", build_recent(repos))
    with open("README.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("README updated.")


if __name__ == "__main__":
    main()
