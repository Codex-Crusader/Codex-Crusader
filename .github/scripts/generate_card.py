#!/usr/bin/env python3
"""
Generate the profile character sheet SVG from the GitHub GraphQL API.

Reads GH_TOKEN and GH_USER from the environment, writes assets/character.svg.
No external dependencies; standard library only.
"""

import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

API_URL = "https://api.github.com/graphql"
OUTPUT_PATH = "assets/character.svg"

# The Orvia palette, shared with codex-crusader.github.io.
INK = "#0A0806"
PLATE = "#15100B"
GOLD = "#D6A553"
GOLD_HI = "#F3D48E"
EMBER = "#E8662C"
TEXT = "#EFE4CC"
MUTED = "#BCAC8D"
LINE = "#3B2E1E"

SERIF = "Georgia, 'Times New Roman', serif"
SANS = "-apple-system, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#F1E05A",
    "TypeScript": "#3178C6",
    "HTML": "#E34C26",
    "CSS": "#663399",
    "Shell": "#89E051",
    "Rust": "#DEA584",
    "Svelte": "#FF3E00",
    "C": "#555555",
    "C++": "#F34B7D",
    "Go": "#00ADD8",
    "Jupyter Notebook": "#DA5B0B",
}
LANGUAGE_FALLBACK = "#8B949E"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        primaryLanguage { name }
      }
    }
  }
}
"""


def fetch(login, token):
    """Call the GraphQL API and return the `user` object."""
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-character-sheet",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if "errors" in payload:
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def flatten_days(calendar):
    """Return contribution days as a flat, date-ordered list."""
    days = []
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])
    days.sort(key=lambda day: day["date"])
    return days


def current_streak(days):
    """
    Count consecutive contribution days ending today.

    A zero-count today does not break the streak, since the day is still
    in progress when the workflow runs.
    """
    streak = 0
    for index, day in enumerate(reversed(days)):
        if day["contributionCount"] > 0:
            streak += 1
        elif index == 0:
            continue
        else:
            break
    return streak


def longest_streak(days):
    """Longest run of consecutive contribution days in the window."""
    best = 0
    running = 0
    for day in days:
        if day["contributionCount"] > 0:
            running += 1
            best = max(best, running)
        else:
            running = 0
    return best


def top_languages(repositories, limit=5):
    """Count primary languages across repos, most common first."""
    counts = {}
    for repo in repositories:
        language = repo.get("primaryLanguage")
        if language:
            counts[language["name"]] = counts.get(language["name"], 0) + 1

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return ranked[:limit]


def collect(user):
    """Reduce the API response to the numbers the card displays."""
    contributions = user["contributionsCollection"]
    calendar = contributions["contributionCalendar"]
    days = flatten_days(calendar)
    repositories = user["repositories"]["nodes"]

    return {
        "login": user["login"],
        "stars": sum(repo["stargazerCount"] for repo in repositories),
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "commits": contributions["totalCommitContributions"],
        "pull_requests": contributions["totalPullRequestContributions"],
        "issues": contributions["totalIssueContributions"],
        "reviews": contributions["totalPullRequestReviewContributions"],
        "contributions": calendar["totalContributions"],
        "current_streak": current_streak(days),
        "longest_streak": longest_streak(days),
        "languages": top_languages(repositories),
    }


def level_of(contributions):
    """One level per 100 contributions in the last year. Returns (level, xp into it)."""
    return 1 + contributions // 100, contributions % 100


def escape(text):
    """Escape the characters that matter inside SVG text and attributes."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def attribute_rows(stats, x, y):
    """Six RPG attributes, each backed by a real number and a log-scaled bar."""
    # (short name, real meaning, value, value that fills the bar)
    rows = [
        ("STR", "commits", stats["commits"], 2000),
        ("DEX", "pull requests", stats["pull_requests"], 200),
        ("INT", "repositories", stats["repos"], 60),
        ("WIS", "reviews given", stats["reviews"], 50),
        ("CHA", "followers", stats["followers"], 200),
        ("LCK", "stars earned", stats["stars"], 200),
    ]

    parts = []
    for index, (short, meaning, value, cap) in enumerate(rows):
        column = index % 2
        row = index // 2
        rx = x + column * 250
        ry = y + row * 44
        fill = min(1.0, math.log10(value + 1) / math.log10(cap + 1))
        parts.append(
            f'<text x="{rx}" y="{ry}" fill="{GOLD}" font-family="{SERIF}" '
            f'font-size="15" font-weight="700" letter-spacing="2">{short}</text>'
        )
        parts.append(
            f'<text x="{rx + 44}" y="{ry}" fill="{MUTED}" font-size="12">'
            f"{escape(meaning)}</text>"
        )
        parts.append(
            f'<text x="{rx + 220}" y="{ry}" fill="{TEXT}" font-size="14" '
            f'font-weight="600" text-anchor="end">{escape(value)}</text>'
        )
        parts.append(
            f'<rect x="{rx}" y="{ry + 9}" width="220" height="5" rx="2.5" fill="{LINE}"/>'
        )
        parts.append(
            f'<rect x="{rx}" y="{ry + 9}" width="{220 * fill:.1f}" height="5" rx="2.5" '
            f'fill="{GOLD}"/>'
        )
    return "\n  ".join(parts)


def language_bar(languages, x, y, width):
    """Proportional stacked bar plus a legend row."""
    if not languages:
        return ""

    total = sum(count for _, count in languages)
    parts = [
        f'<text x="{x}" y="{y - 12}" fill="{MUTED}" font-family="{SERIF}" '
        f'font-size="12" letter-spacing="2">SCHOOLS OF MAGIC</text>'
    ]
    offset = x
    for name, count in languages:
        segment = width * count / total
        colour = LANGUAGE_COLORS.get(name, LANGUAGE_FALLBACK)
        parts.append(
            f'<rect x="{offset:.1f}" y="{y}" width="{segment:.1f}" height="8" fill="{colour}"/>'
        )
        offset += segment

    legend_x = x
    for name, count in languages:
        colour = LANGUAGE_COLORS.get(name, LANGUAGE_FALLBACK)
        label = f"{name} {round(100 * count / total)}%"
        parts.append(f'<circle cx="{legend_x + 4}" cy="{y + 26}" r="4" fill="{colour}"/>')
        parts.append(
            f'<text x="{legend_x + 14}" y="{y + 30}" fill="{TEXT}" font-size="12">'
            f"{escape(label)}</text>"
        )
        legend_x += 30 + len(label) * 6.6
    return "\n  ".join(parts)


def render(stats, now=None):
    """Assemble the full SVG document."""
    now = now or datetime.now(timezone.utc)
    level, xp = level_of(stats["contributions"])
    streak = stats["current_streak"]
    lit = streak > 0

    # The bonfire flickers while the streak is alive and is grey ash otherwise.
    flame = EMBER if lit else LINE
    flicker = (
        '<animate attributeName="opacity" values="1;0.65;1;0.8;1" dur="1.6s" '
        'repeatCount="indefinite"/>'
        if lit
        else ""
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="350"
     viewBox="0 0 820 350" font-family="{SANS}" role="img"
     aria-label="Character sheet for {escape(stats['login'])}: level {level}, {stats['contributions']} contributions in the last year, {stats['commits']} commits, {stats['stars']} stars, {streak} day streak">
  <rect width="820" height="350" rx="12" fill="{INK}"/>
  <rect x="8" y="8" width="804" height="334" rx="8" fill="{PLATE}" stroke="{LINE}"/>
  <rect x="14" y="14" width="792" height="322" rx="6" fill="none" stroke="{GOLD}" stroke-opacity="0.35"/>

  <text x="36" y="52" fill="{GOLD_HI}" font-family="{SERIF}" font-size="22" font-weight="700" letter-spacing="1">
    {escape(stats['login'])}
  </text>
  <text x="36" y="72" fill="{MUTED}" font-family="{SERIF}" font-size="13" font-style="italic">
    Codemancer of Orvia · Vijaybhoomi University · CSE '28
  </text>

  <text x="530" y="52" fill="{GOLD}" font-family="{SERIF}" font-size="13" letter-spacing="2" text-anchor="end">LEVEL</text>
  <text x="530" y="78" fill="{GOLD_HI}" font-family="{SERIF}" font-size="30" font-weight="700" text-anchor="end">{level}</text>

  <rect x="36" y="88" width="494" height="6" rx="3" fill="{LINE}"/>
  <rect x="36" y="88" width="{494 * xp / 100:.1f}" height="6" rx="3" fill="{EMBER}"/>
  <text x="36" y="110" fill="{MUTED}" font-size="11">
    {stats['contributions']} contributions this year · {100 - xp} XP to level {level + 1}
  </text>

  {attribute_rows(stats, 36, 142)}

  <line x1="572" y1="36" x2="572" y2="240" stroke="{GOLD}" stroke-opacity="0.25"/>

  <g transform="translate(690 70)">
    <path d="M-22 44 L22 44 M-16 50 L16 50" stroke="{MUTED}" stroke-width="3" stroke-linecap="round"/>
    <path d="M-3 46 L6 -6" stroke="{MUTED}" stroke-width="4" stroke-linecap="round"/>
    <path d="M0 40 C-20 30 -14 10 -4 -2 C-6 14 4 16 4 4 C14 16 18 32 0 40 Z" fill="{flame}">{flicker}</path>
  </g>
  <text x="690" y="152" fill="{GOLD_HI}" font-family="{SERIF}" font-size="34" font-weight="700" text-anchor="middle">{streak}</text>
  <text x="690" y="172" fill="{MUTED}" font-size="12" text-anchor="middle">
    {"day bonfire streak" if lit else "bonfire unlit (no streak)"}
  </text>
  <text x="690" y="204" fill="{TEXT}" font-size="13" text-anchor="middle">
    longest this year: {stats['longest_streak']} days
  </text>
  <text x="690" y="226" fill="{MUTED}" font-size="12" text-anchor="middle">
    {stats['issues']} issues opened
  </text>

  {language_bar(stats['languages'], 36, 290, 748)}

  <text x="784" y="332" fill="{MUTED}" fill-opacity="0.7" font-size="10" text-anchor="end">
    rested at a bonfire {now.strftime('%d %b %Y')}
  </text>
</svg>
"""


def main():
    token = os.environ.get("GH_TOKEN")
    login = os.environ.get("GH_USER")

    if not token or not login:
        sys.exit("GH_TOKEN and GH_USER must both be set.")

    stats = collect(fetch(login, token))

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        handle.write(render(stats))

    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
