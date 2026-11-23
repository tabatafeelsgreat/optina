"""Turn new Mailchimp issues (from _data/newsletter.json) into news cards in _news/.
Each issue mixes Russian and English sections; Russian blocks go to the RU text, English to the EN text."""
import io, json, os, re, sys, html, urllib.request

CUTOFF = "2026-08-01"  # issues sent from this date become news automatically
NEWS = "_news"
LOGOS = ["1c62525d-8d24-b198-f62c-64c5519c180f"]  # header logo images, not photos

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (parish website updater)"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

def dhash(url):
    """Perceptual hash: the same photo re-uploaded to Mailchimp gets a new URL but the same hash."""
    try:
        from PIL import Image
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (parish website updater)"})
        im = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("L").resize((9, 8))
        px = list(im.getdata())
        return sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])
    except Exception:
        return None

def same(a, b):
    return a is not None and b is not None and bin(a ^ b).count("1") <= 10

def pick_cover(imgs, used):
    """First photo of the issue that is not already the cover of a recent news item."""
    for u in imgs:
        h = dhash(u)
        if not any(same(h, x) for x in used):
            used.append(h)
            return u
    return imgs[0] if imgs else ""

def recent_covers(n=15):
    files = sorted(f for f in os.listdir(NEWS) if f.endswith(".md"))[-n:]
    out = []
    for f in files:
        m = re.search(r'^image: "(http[^"]+)"$', open(os.path.join(NEWS, f), encoding="utf-8").read(), re.M)
        if m:
            out.append(dhash(m.group(1)))
    return out

def norm(s):
    return re.sub(r"\W+", "", s.lower())

def convert(page, ru_title, en_title):
    imgs = [u for u in re.findall(r'<img[^>]+src="([^"]+)"', page)
            if "mcusercontent.com" in u and not any(x in u for x in LOGOS)]
    b = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", "", page)
    b = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</div>|</td>|</li>", "\n", b)
    t = html.unescape(re.sub(r"<[^>]+>", "", b)).replace(" ", " ")
    t = re.sub(r"[͏‌­​]", "", t)
    lines = [l.strip() for l in t.split("\n")]
    # skip Mailchimp's archive bar (Subscribe, Translate + language list) and "View this email" line
    start = next((k + 1 for k, l in enumerate(lines) if "View this email" in l), None)
    if start is None:
        start = next((k + 1 for k, l in enumerate(lines) if "Tiếng Việt" in l), 0)
    issue = next((k + 1 for k, l in enumerate(lines[start:start + 30], start) if re.match(r"(ISSUE|ВЫПУСК)\b", l)), None)
    if issue:
        start = issue
    end = next((k for k, l in enumerate(lines) if l.startswith("Copyright")), len(lines))
    body = lines[start:end]
    while body and (body[-1] == "" or body[-1] in ("OPTINA", "ОПТИНА") or body[-1].startswith("ST. JOSEPH OF OPTINA")):
        body.pop()
    blocks, cur = [], []
    for l in body + [""]:
        if l:
            cur.append(l)
        elif cur:
            blocks.append(cur); cur = []
    skip = {norm(ru_title), norm(en_title)}
    ru, en, prev = [], [], None
    for bl in blocks:
        txt = "\n".join(bl)
        if txt == prev or norm(txt) in skip or re.fullmatch(r"(OPTINA|ОПТИНА)\n.*VIRGINIA", txt):
            continue
        prev = txt
        cyr = len(re.findall(r"[А-Яа-яЁё]", txt)); lat = len(re.findall(r"[A-Za-z]", txt))
        if cyr == 0 and lat == 0:
            continue
        if len(bl) == 1 and len(txt) < 60 and txt == txt.upper():
            p = f"<p><strong>{html.escape(txt)}</strong></p>"
        else:
            p = "<p>" + "<br>".join(html.escape(l) for l in bl) + "</p>"
        (ru if cyr >= lat else en).append(p)
    hide = lambda x: re.sub(r"([\w.+-])@([\w-]+\.[\w.]+)", r"\1 [at] \2", x)  # keep emails away from spam bots
    return imgs, hide("\n".join(ru)), hide("\n".join(en))

def q(s):
    return json.dumps(s, ensure_ascii=False)

def write(issue, page, used):
    imgs, ru, en = convert(page, issue.get("ru", issue["title"]), issue.get("en", issue["title"]))
    img = pick_cover(imgs, used)
    slug = re.sub(r"\W+", "-", issue["url"].rstrip("/").split("/")[-1]).strip("-").lower()[-40:]
    path = f"{NEWS}/{issue['date']}-rassylka-{slug}.md"
    fm = ["---", f"title: {q(issue.get('ru', issue['title']))}", f"title_en: {q(issue.get('en', issue['title']))}",
          f"date: {issue['date']}", f"image: {q(img)}", f"link: {q(issue['url'])}", "newsletter: true",
          f"body_en: {q(en)}", "---", ru, ""]
    open(path, "w", encoding="utf-8").write("\n".join(fm))
    return path

if __name__ == "__main__":
    if len(sys.argv) > 1:  # test: python3 nl2news.py URL "RU title" "EN title"
        imgs, ru, en = convert(get(sys.argv[1]), sys.argv[2], sys.argv[3])
        print("IMG", imgs); print("=== RU\n" + ru); print("=== EN\n" + en); sys.exit()
    done, used = set(), None
    for f in os.listdir(NEWS):
        m = re.search(r'^link: "(.*)"$', open(os.path.join(NEWS, f), encoding="utf-8").read(), re.M)
        if m: done.add(m.group(1))
    for issue in json.load(open("_data/newsletter.json", encoding="utf-8"))["issues"]:
        if issue["date"] < CUTOFF or issue["url"] in done or issue.get("ru", "").lower().startswith("prayer request"):
            continue
        try:
            if used is None:
                used = recent_covers()
            print("news added:", write(issue, get(issue["url"]), used))
        except Exception as e:
            print("skipped", issue["url"], e)
