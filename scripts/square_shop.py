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
# Tees of one design in several colours are shown on the site as one card with colour swatches.
SWATCH = {"anthracite": "#4b4746", "deep teal": "#58718a", "green bay": "#7d9a8f", "kaffa coffee": "#9c766c"}
COVER = {"A Saint Is A Sinner": "anthracite", "Building Here Remembered There": "deep teal",
         "Higgs Boson To Love?": "green bay", "Sin Builds Walls We Build A Church": "kaffa coffee"}

PRINTS = {"Churches": ("churches", "Церкви", "Churches", "hoodie"),
          "Angels": ("angels", "Ангелы", "Angels", "dress"),
          "Reindeer and Trees": ("reindeer", "Олени и ёлки", "Reindeer and Trees", "sweatshirt")}
TYPES = {"hoodie": ("Худи", "Hoodie"), "sweatshirt": ("Свитшот", "Sweatshirt"),
         "tee": ("Футболка", "T-shirt"), "dress": ("Платье", "Dress")}
TYPE_ORDER = ["hoodie", "sweatshirt", "tee", "dress"]

def print_grouping(it):
    """All-over print items (white fabric) are grouped by print; the variants are item types."""
    m = re.search(r'"(Churches|Angels|Reindeer and Trees)"', it["name_en"])
    if not m:
        return None
    key, ru, en, cover = PRINTS[m.group(1)]
    n = it["name_en"].lower()
    t = "dress" if "dress" in n else "hoodie" if "hoodie" in n else "sweatshirt" if "sweatshirt" in n else "tee"
    return {"group": "print-" + key, "group_title_ru": f"Принт «{ru}»", "group_title_en": f"Print “{en}”",
            "color_ru": TYPES[t][0], "color_en": TYPES[t][1], "swatch": "", "chip": True,
            "order": TYPE_ORDER.index(t), "cover": t == cover}

def grouping(it):
    """T-shirt “Text”, Colour -> group/colour fields (empty for single items)."""
    pg = print_grouping(it)
    if pg:
        return pg
    m = re.match(r"T-shirt “(.+)”, (.+)$", it["name_en"])
    if not m:
        return {"group": "", "color_en": "", "color_ru": "", "swatch": "", "cover": False}
    g, c = m.group(1), m.group(2)
    return {"group": g, "color_en": c, "color_ru": COLORS_RU.get(c.lower(), c.lower()),
            "swatch": SWATCH.get(c.lower(), "#999"), "cover": COVER.get(g, "") == c.lower()}

KEEP = ("name_ru", "name_en", "kind", "note_ru", "note_en")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (parish website updater)", "Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))

def names(sq):
    """Square name -> (ru, en). 'T-Shirt "Text"' becomes 'Футболка «Text»'."""
    sq = re.sub(r"\s+", " ", html.unescape(sq)).strip()
    m = re.search(r'"([^"]+)"', sq)
    if m and re.search(r"(?i)dress|hoodie|sweatshirt|all-over|men.s", sq):
        # patterned items: keep the English name, build a Russian one by item type
        pat = m.group(1)
        ru_pat = {"Churches": "Церкви", "Angels": "Ангелы", "Reindeer and Trees": "Олени и ёлки"}.get(pat, pat)
        if re.search(r"(?i)dress", sq): kind = "Платье-футболка"
        elif re.search(r"(?i)hoodie", sq): kind = "Худи"
        elif re.search(r"(?i)sweatshirt", sq): kind = "Свитшот"
        else: kind = "Мужская футболка"
        return f"{kind} «{ru_pat}»", sq
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

for it in items:
    it.update(grouping(it))
items.sort(key=lambda it: (bool(it["group"]), it["group"], it.get("order", 0), it["name_en"].lower()))
shop["items"] = items
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(shop, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"{len(items)} products from Square")
