import json
import os
import time
import urllib.request
from pathlib import Path

LISTINGS_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
SEEN_FILE = Path("seen.txt")
MAX_AGE_DAYS = 14
TERM = "Summer 2027"
EMBEDS_PER_MESSAGE = 10
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


def http(req):
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_listings():
    req = urllib.request.Request(LISTINGS_URL, headers={"User-Agent": "job-notif-bot"})
    return json.loads(http(req))


def to_embed(l):
    locations = ", ".join(l.get("locations") or []) or "N/A"
    return {
        "title": f"{l['company_name']} — {l['title']}"[:256],
        "url": l["url"],
        "fields": [{"name": "Locations", "value": locations[:1024]}],
    }


def post(embeds):
    body = json.dumps({"embeds": embeds}).encode()
    req = urllib.request.Request(
        WEBHOOK, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "job-notif-bot"},
    )
    for _ in range(5):
        try:
            http(req)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(json.loads(e.read()).get("retry_after", 1)) + 0.5)
                continue
            print(f"Discord error {e.code}: {e.read()[:200]}")
            return False
    return False


def main():
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    current = [
        l for l in fetch_listings()
        if l.get("active") and l.get("is_visible", True)
        and TERM in l.get("terms", []) and l.get("date_posted", 0) >= cutoff
    ]

    if not SEEN_FILE.exists():
        SEEN_FILE.write_text("".join(l["id"] + "\n" for l in current))
        print(f"First run: recorded {len(current)} ids, posted nothing.")
        return

    seen = set(SEEN_FILE.read_text().split())
    new = [l for l in current if l["id"] not in seen]
    print(f"{len(new)} new listings")

    posted = []
    for i in range(0, len(new), EMBEDS_PER_MESSAGE):
        chunk = new[i:i + EMBEDS_PER_MESSAGE]
        if not post([to_embed(l) for l in chunk]):
            break  # leave the rest unseen so they retry next run
        posted += chunk
        time.sleep(1)

    if posted:
        with SEEN_FILE.open("a") as f:
            f.writelines(l["id"] + "\n" for l in posted)


if __name__ == "__main__":
    main()
