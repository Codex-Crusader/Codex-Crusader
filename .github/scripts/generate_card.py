#!/usr/bin/env python3
"""
Generate a GitHub stats SVG card from the GitHub GraphQL API.

Reads GH_TOKEN and GH_USER from the environment, writes assets/stats.svg.
No external dependencies; standard library only.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime

API_URL = "https://api.github.com/graphql"
OUTPUT_PATH = "assets/stats.svg"

# Matches the purple used by the capsule-render banners in the README.
ACCENT = "#9D5CFF"
BACKGROUND = "#1A1B27"
TEXT = "#C0CAF5"
MUTED = "#6E7396"

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#F1E05A",
    "TypeScript": "#3178C6",
    "HTML": "#E34C26",
    "CSS": "#663399",
    "Shell": "#89E051",
    "C": "#555555",
    "C++": "#F34B7D",
    "Java": "#B07219",
    "Go": "#00ADD8",
    "Rust": "#DEA584",
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
            "User-Agent": f"{login}-stats-card",
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
    if not days:
        return 0

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


def escape(text):
    """Escape the three characters that matter inside SVG text nodes."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def language_bar(languages, x, y, width):
    """Render a proportional stacked bar plus a legend row."""
    if not languages:
        return ""

    total = sum(count for _, count in languages)
    parts = []
    offset = x

    for name, count in languages:
        segment = width * count / total
        colour = LANGUAGE_COLORS.get(name, LANGUAGE_FALLBACK)
        parts.append(
            f'<rect x="{offset:.1f}" y="{y}" width="{segment:.1f}" height="8" '
            f'fill="{colour}"/>'
        )
        offset += segment

    legend_x = x
    for name, _ in languages:
        colour = LANGUAGE_COLORS.get(name, LANGUAGE_FALLBACK)
        parts.append(
            f'<circle cx="{legend_x + 4}" cy="{y + 30}" r="4" fill="{colour}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 14}" y="{y + 34}" fill="{TEXT}" '
            f'font-size="12">{escape(name)}</text>'
        )
        legend_x += 26 + len(name) * 6.6

    return "\n  ".join(parts)


def stat_rows(stats, x, y):
    """Render the two-column list of headline numbers."""
    rows = [
        ("Commits (last year)", stats["commits"]),
        ("Stars earned", stats["stars"]),
        ("Pull requests", stats["pull_requests"]),
        ("Issues opened", stats["issues"]),
        ("Reviews given", stats["reviews"]),
        ("Public repositories", stats["repos"]),
    ]

    parts = []
    for index, (label, value) in enumerate(rows):
        column = index % 2
        row = index // 2
        row_x = x + column * 240
        row_y = y + row * 30
        parts.append(
            f'<text x="{row_x}" y="{row_y}" fill="{MUTED}" font-size="13">'
            f"{escape(label)}</text>"
        )
        parts.append(
            f'<text x="{row_x + 200}" y="{row_y}" fill="{TEXT}" font-size="13" '
            f'font-weight="600" text-anchor="end">{escape(value)}</text>'
        )

    return "\n  ".join(parts)


def render(stats):
    """Assemble the full SVG document."""
    font = (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', "
        "Helvetica, Arial, sans-serif"
    )
    updated = datetime.utcnow().strftime("%d %b %Y")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="300"
     viewBox="0 0 820 300" font-family="{font}" role="img"
     aria-label="GitHub statistics for {escape(stats['login'])}">
  <rect width="820" height="300" rx="10" fill="{BACKGROUND}"/>
  <rect x="0" y="0" width="820" height="3" rx="1.5" fill="{ACCENT}"/>

  <text x="32" y="46" fill="{ACCENT}" font-size="16" font-weight="700">
    {escape(stats['login'])}
  </text>
  <text x="32" y="66" fill="{MUTED}" font-size="12">
    {escape(stats['contributions'])} contributions in the last year
  </text>

  {stat_rows(stats, 32, 110)}

  <line x1="560" y1="40" x2="560" y2="200" stroke="{MUTED}" stroke-opacity="0.3"/>

  <text x="690" y="86" fill="{ACCENT}" font-size="42" font-weight="700"
        text-anchor="middle">{escape(stats['current_streak'])}</text>
  <text x="690" y="106" fill="{MUTED}" font-size="12" text-anchor="middle">
    day current streak
  </text>

  <text x="690" y="160" fill="{TEXT}" font-size="24" font-weight="600"
        text-anchor="middle">{escape(stats['longest_streak'])}</text>
  <text x="690" y="180" fill="{MUTED}" font-size="12" text-anchor="middle">
    longest this year
  </text>

  {language_bar(stats['languages'], 32, 226, 756)}

  <text x="788" y="290" fill="{MUTED}" font-size="10" text-anchor="end">
    updated {updated}
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
