import os
import json
import urllib.request

USERNAME = "Codex-Crusader"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def fetch_all_repos():
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json"
        })
        with urllib.request.urlopen(req) as res:
            batch = json.loads(res.read().decode())
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos

def build_table(repos):
    # Filter out forks, sort by creation date descending
    owned = [r for r in repos if not r["fork"] and r["name"].lower() != USERNAME.lower()]
    owned.sort(key=lambda r: r["created_at"], reverse=True)

    lines = [
        "| Repository | Stars | Description |",
        "|------------|-------|-------------|"
    ]
    for r in owned:
        name = f"[{r['name']}](https://github.com/{USERNAME}/{r['name']})"
        stars = f"⭐ {r['stargazers_count']}"
        raw_desc = (r["description"] or "—").replace("|", "\\|")
        repo_url = f"https://github.com/{USERNAME}/{r['name']}"
        if len(raw_desc) > 80:
            desc = f"{raw_desc[:80]}... [read more]({repo_url})"
        else:
            desc = raw_desc
        lines.append(f"| {name} | {stars} | {desc} |")

    return "\n".join(lines)

def update_readme(table):
    with open("README.md", "r") as f:
        content = f.read()

    start = "<!-- REPOS_START -->"
    end = "<!-- REPOS_END -->"

    if start not in content or end not in content:
        print("Markers not found in README.md — add them first.")
        return

    new_block = f"{start}\n{table}\n{end}"
    before = content.split(start)[0]
    after = content.split(end)[1]

    with open("README.md", "w") as f:
        f.write(before + new_block + after)

    print("README updated.")

if __name__ == "__main__":
    repos = fetch_all_repos()
    table = build_table(repos)
    update_readme(table)
