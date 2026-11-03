#!/usr/bin/env python3
"""
Profile boss fight: visitors open an issue titled "boss: attack" or
"boss: heavy" and this script deals the damage.

Reads ISSUE_TITLE, ISSUE_USER and ISSUE_NUMBER from the environment (never
from the command line, so a hostile title cannot reach a shell). Updates
assets/boss.json and assets/boss.svg, and writes the reply for the issue to
the file named by REPLY_PATH.

Run with --selftest to simulate a fight without touching the real state.
Standard library only.
"""

import json
import os
import random
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

STATE_PATH = "assets/boss.json"
SVG_PATH = "assets/boss.svg"
COOLDOWN = timedelta(minutes=5)
SEE_IT = "\n\nSee the card on [the profile](https://github.com/Codex-Crusader) in a few minutes (images are cached briefly)."
TITLE_RE = re.compile(r"^\s*boss:\s*(attack|heavy)\s*$", re.IGNORECASE)
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?$")

# name, epithet, max hp, body colour
BOSSES = [
    ("The Off-by-One Ogre", "who guards every loop boundary", 80, "#8C6A3F"),
    ("Null Pointer Wraith", "who is there until you look", 100, "#6E7FA8"),
    ("The Merge Conflict Hydra", "two heads for every one you resolve", 120, "#4F8A5B"),
    ("Heisenbug, the Unobserved", "vanishes the moment you add a print", 140, "#8A5BB0"),
    ("Segfault, Devourer of Stacks", "core dumped, soul intact", 160, "#A8483A"),
    ("The Flaky Test", "passes on your machine", 180, "#B5953A"),
    ("Dependency Hell Knight", "sworn to version 0.0.1-rc3", 200, "#5A6470"),
    ("The Race Condition Twins", "always arrive in the wrong order", 220, "#3F8C8C"),
]

# Orvia palette, shared with the character sheet.
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


def new_state():
    return {
        "boss": 0,
        "hp": BOSSES[0][2],
        "felled": [],
        "log": [],
        "damage": {},
        "last_hit": {},
        "processed": [],
    }


def load_state(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return new_state()


def save_state(state, path):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def roll(move, rng):
    """Return (damage, flavour) for one move."""
    if move == "heavy":
        if rng.random() < 0.5:
            return 0, "wound up a heavy attack and whiffed. Classic."
        return rng.randint(22, 30), "landed a heavy attack."
    if rng.random() < 0.1:
        return rng.randint(8, 14) * 2, "landed a CRITICAL backstab."
    return rng.randint(8, 14), "landed a light attack."


def attack(state, title, user, number, now, rng):
    """
    Apply one issue to the state. Returns the reply text, or None when the
    issue is not a boss move and must be left alone.
    """
    match = TITLE_RE.match(title or "")
    if not match or not LOGIN_RE.match(user or ""):
        return None
    if number in state["processed"]:
        return f"Issue #{number} already counted. The bug remembers."

    state["processed"] = (state["processed"] + [number])[-200:]

    last = state["last_hit"].get(user)
    if last and now - datetime.fromisoformat(last) < COOLDOWN:
        wait = COOLDOWN - (now - datetime.fromisoformat(last))
        return (
            f"@{user}, your stamina bar is empty. Rest for {int(wait.total_seconds() // 60) + 1} "
            "more minute(s), then try again. The boss took no damage."
        )

    name = BOSSES[state["boss"] % len(BOSSES)][0]
    damage, flavour = roll(match.group(1).lower(), rng)
    damage = min(damage, state["hp"])
    state["hp"] -= damage
    state["last_hit"][user] = now.isoformat()
    state["damage"][user] = state["damage"].get(user, 0) + damage
    state["log"] = ([{"user": user, "dmg": damage}] + state["log"])[:5]

    reply = f"@{user} {flavour} **{damage}** damage to {name}. "
    if state["hp"] > 0:
        reply += f"It has **{state['hp']} HP** left.{SEE_IT}"
        return reply

    state["felled"].append({"name": name, "by": user, "date": now.date().isoformat()})
    state["boss"] += 1
    next_name, _, next_hp, _ = BOSSES[state["boss"] % len(BOSSES)]
    state["hp"] = next_hp
    state["log"] = []
    reply += (
        f"\n\n**BUG FELLED.** You struck the final blow. Your name is now on the profile.\n\n"
        f"Something stirs in the fog... **{next_name}** approaches with {next_hp} HP.{SEE_IT}"
    )
    return reply


def escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def sprite(colour, hurt):
    """A many-legged bug drawn in plain SVG, centred on (0, 0)."""
    legs = "".join(
        f'<path d="M{side * 18} {y} q{side * 26} {-10 + i * 4} {side * 40} {8 + i * 6}" '
        f'stroke="{colour}" stroke-width="5" fill="none" stroke-linecap="round"/>'
        for i, y in enumerate((-10, 6, 22))
        for side in (-1, 1)
    )
    eye = EMBER if hurt else GOLD_HI
    return f"""
    {legs}
    <ellipse cx="0" cy="8" rx="30" ry="36" fill="{colour}"/>
    <ellipse cx="0" cy="8" rx="30" ry="36" fill="none" stroke="{INK}" stroke-opacity="0.4" stroke-width="2"/>
    <path d="M0 -26 L0 42" stroke="{INK}" stroke-opacity="0.35" stroke-width="2"/>
    <circle cx="0" cy="-34" r="18" fill="{colour}"/>
    <path d="M-8 -50 q-10 -16 -22 -14 M8 -50 q10 -16 22 -14" stroke="{colour}" stroke-width="3" fill="none"/>
    <circle cx="-7" cy="-36" r="4" fill="{eye}">
      <animate attributeName="opacity" values="1;0.3;1" dur="2.4s" repeatCount="indefinite"/>
    </circle>
    <circle cx="7" cy="-36" r="4" fill="{eye}">
      <animate attributeName="opacity" values="1;0.3;1" dur="2.4s" repeatCount="indefinite"/>
    </circle>"""


def render(state):
    name, epithet, max_hp, colour = BOSSES[state["boss"] % len(BOSSES)]
    hp = state["hp"]
    share = hp / max_hp
    cycle = state["boss"] // len(BOSSES)
    title = f"{name}{' +' * min(cycle, 3)}"

    def short(user):
        return user if len(user) <= 18 else user[:17] + "~"

    if state["log"]:
        blows = [
            f'<text x="578" y="{78 + i * 20}" fill="{TEXT}" font-size="13">'
            f'@{escape(short(hit["user"]))} <tspan fill="{EMBER if hit["dmg"] else MUTED}">'
            f'{"-" + str(hit["dmg"]) if hit["dmg"] else "missed"}</tspan></text>'
            for i, hit in enumerate(state["log"])
        ]
    else:
        blows = [
            f'<text x="578" y="78" fill="{MUTED}" font-size="13" font-style="italic">'
            "No one has struck yet.</text>"
        ]

    top = sorted(state["damage"].items(), key=lambda item: (-item[1], item[0]))[:3]
    slayers = [
        f'<text x="578" y="{206 + i * 18}" fill="{TEXT}" font-size="13">'
        f'@{escape(short(user))} <tspan fill="{GOLD_HI}">{dmg}</tspan></text>'
        for i, (user, dmg) in enumerate(top)
    ] or [f'<text x="578" y="206" fill="{MUTED}" font-size="13" font-style="italic">none yet</text>']

    last_kill = state["felled"][-1] if state["felled"] else None
    kill_lines = (
        f'<text x="220" y="196" fill="{MUTED}" font-size="12">Last felled: <tspan fill="{TEXT}">{escape(last_kill["name"])}</tspan></text>'
        f'<text x="220" y="216" fill="{MUTED}" font-size="12">final blow by <tspan fill="{GOLD_HI}">@{escape(short(last_kill["by"]))}</tspan> on {escape(last_kill["date"])}</text>'
        if last_kill
        else f'<text x="220" y="196" fill="{MUTED}" font-size="12">No bug has fallen yet.</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="280"
     viewBox="0 0 820 280" font-family="{SANS}" role="img"
     aria-label="Boss fight: {escape(name)} has {hp} of {max_hp} HP. Bugs felled: {len(state['felled'])}.">
  <rect width="820" height="280" rx="12" fill="{INK}"/>
  <rect x="8" y="8" width="804" height="264" rx="8" fill="{PLATE}" stroke="{LINE}"/>
  <rect x="14" y="14" width="792" height="252" rx="6" fill="none" stroke="{EMBER}" stroke-opacity="0.35"/>

  <g transform="translate(110 142)">
    <animateTransform attributeName="transform" type="translate"
      values="110 142; 110 136; 110 142" dur="3s" repeatCount="indefinite"/>
    {sprite(colour, share < 0.35)}
  </g>

  <text x="220" y="62" fill="{GOLD_HI}" font-family="{SERIF}" font-size="22" font-weight="700">{escape(title)}</text>
  <text x="220" y="84" fill="{MUTED}" font-family="{SERIF}" font-size="13" font-style="italic">{escape(epithet)}</text>

  <rect x="220" y="104" width="300" height="12" rx="2" fill="{LINE}"/>
  <rect x="220" y="104" width="{300 * share:.1f}" height="12" rx="2" fill="{EMBER}"/>
  <text x="220" y="136" fill="{TEXT}" font-size="13">{hp} / {max_hp} HP</text>

  <text x="220" y="172" fill="{MUTED}" font-size="12">Bugs felled: <tspan fill="{GOLD_HI}" font-weight="700">{len(state['felled'])}</tspan></text>
  {kill_lines}

  <line x1="558" y1="36" x2="558" y2="244" stroke="{GOLD}" stroke-opacity="0.2"/>
  <text x="578" y="54" fill="{GOLD}" font-family="{SERIF}" font-size="12" letter-spacing="2">LAST BLOWS</text>
  {"".join(blows)}
  <text x="578" y="184" fill="{GOLD}" font-family="{SERIF}" font-size="12" letter-spacing="2">TOP DAMAGE</text>
  {"".join(slayers)}

  <text x="220" y="250" fill="{MUTED}" fill-opacity="0.7" font-size="10">one issue, one swing · 5 minute stamina cooldown</text>
</svg>
"""


def main():
    title = os.environ.get("ISSUE_TITLE", "")
    user = os.environ.get("ISSUE_USER", "")
    try:
        number = int(os.environ.get("ISSUE_NUMBER", ""))
    except ValueError:
        sys.exit("ISSUE_NUMBER must be an integer.")
    reply_path = os.environ.get("REPLY_PATH", "reply.md")

    state = load_state(STATE_PATH)
    reply = attack(state, title, user, number, datetime.now(timezone.utc), random.SystemRandom())
    if reply is None:
        print("Not a boss move. Nothing to do.")
        return

    save_state(state, STATE_PATH)
    with open(SVG_PATH, "w", encoding="utf-8") as handle:
        handle.write(render(state))
    with open(reply_path, "w", encoding="utf-8") as handle:
        handle.write(reply + "\n")
    print(reply)


def selftest():
    rng = random.Random(7)
    state = new_state()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert attack(state, "please fix my bug", "alice", 1, now, rng) is None
    assert attack(state, "boss: attack; rm -rf /", "alice", 2, now, rng) is None
    assert attack(state, "boss: attack", "bad user!", 3, now, rng) is None
    assert state == new_state(), "rejected issues must not change state"

    assert "damage" in attack(state, "Boss: Attack", "alice", 4, now, rng)
    assert "stamina" in attack(state, "boss: heavy", "alice", 5, now, rng)
    assert "already counted" in attack(state, "boss: attack", "alice", 4, now, rng)

    for n in range(6, 400):
        attack(state, "boss: heavy", f"user{n}", n, now + timedelta(minutes=n * 6), rng)
        assert 0 < state["hp"] <= BOSSES[state["boss"] % len(BOSSES)][2]
    assert len(state["felled"]) >= 2, "a long fight must fell bosses"
    assert len(state["processed"]) <= 200 and len(state["log"]) <= 5

    svg = render(state)
    assert svg.startswith("<svg") and "<script" not in svg
    with tempfile.TemporaryDirectory() as folder:
        save_state(state, os.path.join(folder, "s.json"))
        assert load_state(os.path.join(folder, "s.json")) == state
    print(f"selftest ok: {len(state['felled'])} bosses felled")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
