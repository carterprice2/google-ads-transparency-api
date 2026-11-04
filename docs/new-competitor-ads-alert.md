# Get an alert when a competitor launches new Google ads

New ads usually mean a new offer, a new market or a new message. This guide sets up a free daily check with GitHub Actions. It lists every ad your competitors started showing since yesterday and posts them to Slack, or just to the job log.

## How it works
1. Every morning, fetch each competitor's ads shown in the last 2 days.
2. Compare their IDs (`creativeId`) with the ones seen before. The new ones are new ads.
3. Save the list of seen IDs for tomorrow.

## The script
Save it as `new_ads.py` in a new GitHub repo:
```python
import json, os, pathlib, urllib.request
from google_ads_transparency import GoogleAdsTransparency, flatten

COMPETITORS = ["hubspot.com", "salesforce.com", "pipedrive.com"]
seen_file = pathlib.Path("seen.json")
seen = set(json.loads(seen_file.read_text())) if seen_file.exists() else set()

ads = GoogleAdsTransparency().search(COMPETITORS, region="US", last_days=2, max_ads=500, ad_text=True)
new = [flatten(a) for a in ads if a["creativeId"] not in seen]

lines = [f"*{a['advertiserName']}* · {a['format']} · {a['headline'] or '(image ad)'} · {a['adUrl']}" for a in new]
print(f"{len(new)} new ads", *lines, sep="\n")
if new and seen and os.environ.get("SLACK_WEBHOOK_URL"):  # skip the alert on the very first run
    body = json.dumps({"text": f"{len(new)} new competitor ads:\n" + "\n".join(lines[:30])}).encode()
    urllib.request.urlopen(urllib.request.Request(os.environ["SLACK_WEBHOOK_URL"], body, {"content-type": "application/json"}))

seen_file.write_text(json.dumps(sorted(seen | {a["creativeId"] for a in ads})))
```

## The schedule
Save this as `.github/workflows/new-ads.yml`:
```yaml
name: new competitor ads
on:
  schedule: [{ cron: "0 8 * * *" }]   # every day at 08:00 UTC
  workflow_dispatch:
permissions:
  contents: write
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install "google-ads-transparency-api @ git+https://github.com/carterprice2/google-ads-transparency-api"
      - run: python new_ads.py
        env:
          APIFY_TOKEN: ${{ secrets.APIFY_TOKEN }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
      - run: |
          git config user.name "new-ads-bot"; git config user.email "bot@users.noreply.github.com"
          git add seen.json && git commit -m "seen ads" && git push || true
```
Then add `APIFY_TOKEN` (free account at [apify.com](https://apify.com?fpr=fi898m)) and, optionally, a [Slack incoming webhook URL](https://api.slack.com/messaging/webhooks) as repository secrets, and run the workflow once by hand.

## Cost
- Three competitors with ad copy usually cost a few cents a day: $1.50 per 1,000 ads, +$1.50 per 1,000 with copy, plus a small fee per run.
- `max_ads=500` per competitor caps the worst case at about $4.50 a run if all three hit the cap with copy on. Lower it if you watch huge advertisers.

## No-code alternative
On Apify, open [Google Ads Transparency Scraper](https://apify.com/seodatalab/google-ads-transparency-scraper?fpr=fi898m):
1. Enter the domains and set "Shown in the last N days" to 1.
2. Save it as a task and add a daily schedule.
3. Connect the Slack, Google Sheets or email integration.

You'll get every ad shown that day, not only new ones, but no code is involved.

*Disclosure: I maintain this library and the Apify scraper it calls. Links to apify.com include my referral code, so Apify may pay me a commission if you sign up. It doesn't change your price.*
