"""Fetch the parish Mailchimp archive RSS and save recent issues to _data/newsletter.json."""
import json, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
FEED = "https://us4.campaign-archive.com/feed?u=e4b5fdbc56722abc123064202&id=1f29cdbfa9"
req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (parish website updater)"})
root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())
issues = []
for it in root.iter("item"):
    title = (it.findtext("title") or "").strip()
    link = (it.findtext("link") or "").strip()
    pub = it.findtext("pubDate")
    date = parsedate_to_datetime(pub).date().isoformat() if pub else ""
    if title and link:
        issues.append({"title": title, "url": link, "date": date})
issues.sort(key=lambda x: x["date"], reverse=True)
if not issues:
    raise SystemExit("feed returned no issues; keeping the old file")
out = {"issues": issues[:60]}
path = "_data/newsletter.json"
old = open(path, encoding="utf-8").read() if __import__("os").path.exists(path) else ""
new = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
if new != old:
    open(path, "w", encoding="utf-8").write(new)
    print(f"updated: {len(issues)} issues, newest {issues[0]['date']} {issues[0]['title']}")
else:
    print("no change")
