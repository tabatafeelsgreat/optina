"""Pull the published products of the parish Square Online store into _data/shop.json.

Uses the store's public storefront API (no keys). Keeps the manual settings
(show, intro, store_url) and any hand-edited Russian/English names or notes
for products that are still in Square (matched by square_id).
"""
import html, json, re, sys, urllib.request

USER, SITE = "153971870", "900513055530914184"
STORE = "https://st-joseph-of-optina-rocor.square.site/"
API = (f"https://cdn5.editmysite.com/app/store/api/v28/editor/users/{USER}/sites/{SITE}/products"
       "?page={page}&per_page=100&include=images&visibilities[]=visible")
PATH = "_data/shop.json"
COLORS_RU = {"anthracite": "антрацитовая", "deep teal": "тёмно-бирюзовая", "green bay": "серо-зелёная",
             "kaffa coffee": "кофейная", "misty grey": "светло-серая", "blue grey": "серо-голубая", "blush": "пудровая"}
KEEP = ("name_ru", "name_en", "kind", "note_ru", "note_en")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (parish website updater)", "Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))

def names(sq):
    """Square name -> (ru, en). 'T-Shirt "Text"' becomes 'Футболка «Text»'."""
    sq = re.sub(r"\s+", " ", html.unescape(sq)).strip()
    m = re.search(r'"([^"]+)"', sq)
    if re.search(r"t-?shirt", sq, re.I) and m:
        color = sq[m.end():].strip(" ,-–")
        if color:
            return (f"Футболка «{m.group(1)}», {COLORS_RU.get(color.lower(), color.lower())}",
                    f"T-shirt “{m.group(1)}”, {color}")
        return f"Футболка «{m.group(1)}»", f"T-shirt “{m.group(1)}”"
    if re.search(r"t-?shirt", sq, re.I):
        model = re.sub(r"(?i)unisex|organic|cotton|t-?shirt", "", sq)
        model = re.sub(r"\s+", " ", model).strip()
        return f"Футболка {model}".strip(), f"T-shirt {model}".strip()
    return sq, sq

def num(x):
    x = round(float(x), 2)
    return int(x) if x == int(x) else f"{x:.2f}"

products, page = [], 1
try:
    while True:
        d = get(API.format(page=page))
        products += d.get("data") or []
        pg = (d.get("meta") or {}).get("pagination") or {}
        if page >= pg.get("total_pages", 1):
            break
        page += 1
except Exception as e:
    print("Square fetch failed, shop left as is:", e)
    sys.exit(0)

shop = json.load(open(PATH, encoding="utf-8"))
old = {it.get("square_id"): it for it in shop.get("items", []) if it.get("square_id")}
items = []
for p in products:
    if p.get("visibility") != "visible":
        continue
    ru, en = names(p.get("name", ""))
    price = p.get("price") or {}
    imgs = (p.get("images") or {}).get("data") or []
    it = {
        "square_id": p["id"],
        "image": imgs[0].get("absolute_url", "") if imgs else "",
        "name_ru": ru, "name_en": en,
        "price": num(price["low"]) if price.get("low") is not None else "",
        "price_from": bool(price.get("high")) and price.get("high") != price.get("low"),
        "kind": "merch",
        "link": p.get("absolute_site_link") or STORE + (p.get("site_link") or ""),
        "note_ru": "", "note_en": "",
        "sold_out": bool((p.get("badges") or {}).get("out_of_stock")),
    }
    prev = old.get(p["id"])
    if prev:  # keep what was edited by hand in Pages CMS
        for k in KEEP:
            if prev.get(k):
                it[k] = prev[k]
    items.append(it)

items.sort(key=lambda it: it["name_en"].lower())
shop["items"] = items
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(shop, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"{len(items)} products from Square")
