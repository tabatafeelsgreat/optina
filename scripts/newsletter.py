"""Collect all parish Mailchimp issues (archive page + RSS) into _data/newsletter.json, keeping old ones."""
import json, os, re, html, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
U, ID = "e4b5fdbc56722abc123064202", "1f29cdbfa9"
FEED = f"https://us4.campaign-archive.com/feed?u={U}&id={ID}"
HOME = f"https://us4.campaign-archive.com/home/?u={U}&id={ID}"
PATH = "_data/newsletter.json"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (parish website updater)"})
    return urllib.request.urlopen(req, timeout=30).read()

found = {}
def add(title, url, date):
    title = html.unescape(re.sub(r"\s+", " ", title)).strip()
    url = html.unescape(url).strip()
    if title and url:
        found[url] = {"title": title, "url": url, "date": date or found.get(url, {}).get("date", "")}

try:
    page = get(HOME).decode("utf-8", "replace")
    n = 0
    for m in re.finditer(r'<li class="campaign">\s*([\d/]+)\s*-\s*<a href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        d = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat()
        add(re.sub(r"<[^>]+>", "", m.group(3)), m.group(2), d); n += 1
    print(f"archive page: {n} issues")
    if n == 0:
        print(page[:3000])
except Exception as e:
    print("archive page failed:", e)

try:
    for it in ET.fromstring(get(FEED)).iter("item"):
        pub = it.findtext("pubDate")
        add(it.findtext("title") or "", it.findtext("link") or "",
            parsedate_to_datetime(pub).date().isoformat() if pub else "")
except Exception as e:
    print("feed failed:", e)

old = open(PATH, encoding="utf-8").read() if os.path.exists(PATH) else '{"issues":[]}'
for i in json.loads(old).get("issues", []):
    if i["url"] not in found:
        found[i["url"]] = i
issues, seen = [], set()
for i in sorted(found.values(), key=lambda x: (x["date"], "mailchi.mp" in x["url"]), reverse=True):
    key = re.sub(r"\W+", "", i["title"].lower())
    if key not in seen:  # the same issue is often sent twice; keep the newest copy
        seen.add(key); issues.append(i)
for i in issues:  # titles look like "Русский · English"
    parts = re.split(r"\s+[·|]\s+", i["title"], maxsplit=1)
    i["ru"], i["en"] = (parts[0], parts[1]) if len(parts) == 2 else (i["title"], i["title"])
if not issues:
    raise SystemExit("no issues found; keeping the old file")
new = json.dumps({"issues": issues}, ensure_ascii=False, indent=2) + "\n"
if new != old:
    open(PATH, "w", encoding="utf-8").write(new)
    print(f"updated: {len(issues)} issues, newest {issues[0]['date']} {issues[0]['title']}")
else:
    print(f"no change ({len(issues)} issues)")
