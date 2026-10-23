"""Decides whether it's time for the Claude routine, and prepares fixtures.json.

Runs hourly in GitHub Actions (the routine's own sandbox can't reach the FPL
API). When the next FPL deadline is 1-3 hours away and the routine hasn't run
for that gameweek yet, it writes the gameweek's fixtures to fixtures.json,
records the gameweek in state.json and sets `run=true` for the workflow, which
then fires the routine.

`--force` skips the timing check (for manual runs).
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

API = "https://fantasy.premierleague.com/api"
WINDOW_HOURS = (1, 3)


def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0 (pl-widget-news)"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def output(**values):
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for k, v in values.items():
                f.write(f"{k}={v}\n")


now = datetime.now(timezone.utc)
force = "--force" in sys.argv

events = get("/bootstrap-static/")["events"]
upcoming = [
    e for e in events
    if e.get("deadline_time") and datetime.fromisoformat(e["deadline_time"].replace("Z", "+00:00")) > now
]
if not upcoming:
    print("No upcoming deadline (season over?)")
    output(run="false")
    sys.exit(0)

event = min(upcoming, key=lambda e: e["deadline_time"])
deadline = datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))
hours = (deadline - now).total_seconds() / 3600

try:
    state = json.load(open("state.json", encoding="utf-8"))
except FileNotFoundError:
    state = {}

print(f"Next deadline: GW{event['id']} at {event['deadline_time']} ({hours:.1f} h away); last run for GW{state.get('lastEvent')}")

due = WINDOW_HOURS[0] <= hours <= WINDOW_HOURS[1] and state.get("lastEvent") != event["id"]
if not (due or force):
    output(run="false")
    sys.exit(0)

teams = {t["id"]: t["name"] for t in json.load(open("teams.json", encoding="utf-8"))}
fixtures = sorted(
    (
        {
            "id": f["id"],
            "event": f["event"],
            "home": teams.get(f["team_h"], str(f["team_h"])),
            "away": teams.get(f["team_a"], str(f["team_a"])),
            "kickoff": f["kickoff_time"],
        }
        for f in get(f"/fixtures/?event={event['id']}")
        if f.get("kickoff_time")
    ),
    key=lambda f: f["kickoff"],
)

with open("fixtures.json", "w", encoding="utf-8") as out:
    json.dump(
        {
            "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event["id"],
            "deadline": event["deadline_time"],
            "fixtures": fixtures,
        },
        out, ensure_ascii=False, indent=2,
    )
with open("state.json", "w", encoding="utf-8") as out:
    json.dump({"lastEvent": event["id"], "triggeredAt": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, out, indent=2)

print(f"Prepared {len(fixtures)} fixtures for GW{event['id']}")
output(run="true", event=event["id"])
