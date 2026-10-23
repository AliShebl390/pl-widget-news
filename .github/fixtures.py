"""Writes fixtures.json: FPL fixtures kicking off in the next 4 days, with team names.

The Claude routine's cloud sandbox can't reach the FPL API, so this runs in
GitHub Actions shortly before the routine and leaves the list in the repo.
"""
import json
import urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://fantasy.premierleague.com/api/fixtures/?future=1"

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (pl-widget-news)"})
fixtures = json.load(urllib.request.urlopen(req, timeout=30))
teams = {t["id"]: t["name"] for t in json.load(open("teams.json", encoding="utf-8"))}

now = datetime.now(timezone.utc)
window = []
for f in fixtures:
    if not f.get("kickoff_time"):
        continue
    kickoff = datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00"))
    if now - timedelta(hours=3) <= kickoff <= now + timedelta(days=4):
        window.append({
            "id": f["id"],
            "event": f["event"],
            "home": teams.get(f["team_h"], str(f["team_h"])),
            "away": teams.get(f["team_a"], str(f["team_a"])),
            "kickoff": f["kickoff_time"],
        })

window.sort(key=lambda f: f["kickoff"])
with open("fixtures.json", "w", encoding="utf-8") as out:
    json.dump({"generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "fixtures": window}, out, ensure_ascii=False, indent=2)
print(f"{len(window)} fixtures in the window")
