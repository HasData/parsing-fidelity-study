"""Grade the parsing-fidelity raw responses against ground truth.

Structured vendors (hasdata, scrapingbee, zyte-books): field-level exact match
after normalization. Text vendors (scraperapi, zyte-quotes browserHtml): recall
of ground-truth strings in the output.

Normalization: whitespace collapsed; price compared as the numeric part; rating
compared as the star word (Three) extracted from the class string; availability
compared with whitespace stripped.
"""
import json, pathlib, re, statistics

ROOT = pathlib.Path(__file__).parent
GT = json.loads((ROOT / "ground-truth.json").read_text(encoding="utf-8"))
import sys
RAW = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "raw")  # pass raw-fresh to grade your own run

def norm_price(s):
    m = re.search(r"[\d.]+", str(s) or "")
    return str(float(m.group(0))) if m else ""

def norm_rating(s):
    for w in ("One", "Two", "Three", "Four", "Five"):
        if w in str(s):
            return w
    return str(s)

def norm_ws(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

def grade_books_items(items, title_key, price_key, avail_key, rating_key):
    """items: list of dicts. Returns per-field correct counts out of 20."""
    gt = GT["books"]
    res = {"items": len(items), "title": 0, "price": 0, "availability": 0, "rating": 0}
    for g, it in zip(gt, items):
        if norm_ws(it.get(title_key)) == norm_ws(g["title"]):
            res["title"] += 1
        if norm_price(it.get(price_key)) == norm_price(g["price"]):
            res["price"] += 1
        if avail_key and norm_ws(it.get(avail_key)) == norm_ws(g["availability"]):
            res["availability"] += 1
        if rating_key and norm_rating(it.get(rating_key)) == g["rating"]:
            res["rating"] += 1
    return res

def grade_quotes_items(items, text_key, author_key):
    gt = GT["quotes"]
    res = {"items": len(items), "text": 0, "author": 0}
    for g, it in zip(gt, items):
        if norm_ws(it.get(text_key)) == norm_ws(g["text"]):
            res["text"] += 1
        if norm_ws(it.get(author_key)) == norm_ws(g["author"]):
            res["author"] += 1
    return res

def recall_in_text(text, target):
    """Fraction of ground-truth field values present in the text output."""
    text_n = norm_ws(text)
    if target == "books":
        vals = [b["title"] for b in GT["books"]] + [norm_price(b["price"]) for b in GT["books"]]
    else:
        vals = [q["text"].strip("“”") for q in GT["quotes"]] + [q["author"] for q in GT["quotes"]]
    hit = sum(1 for v in vals if v in text_n)
    return {"recall_pct": round(100 * hit / len(vals), 1), "hit": hit, "of": len(vals)}

summary = {}
for target in ("books", "quotes"):
    for vendor in ("hasdata", "scrapingbee", "zyte", "scraperapi", "apify"):
        runs = []
        secs = []
        for run in (1, 2, 3):
            p = RAW / f"{vendor}-{target}-run{run}.json"
            if not p.exists():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            secs.append(d.get("seconds"))
            if vendor == "hasdata":
                ed = d.get("extractedData") or {}
                if target == "books":
                    titles = ed.get("title") or []
                    items = [{"title": t, "price": p2, "availability": a, "rating": r}
                             for t, p2, a, r in zip(titles, ed.get("price") or [],
                                                     ed.get("availability") or [], ed.get("rating") or [])]
                    runs.append(grade_books_items(items, "title", "price", "availability", "rating"))
                else:
                    items = [{"text": t, "author": a} for t, a in
                             zip(ed.get("text") or [], ed.get("author") or [])]
                    runs.append(grade_quotes_items(items, "text", "author"))
            elif vendor == "scrapingbee":
                items = (d.get("data") or {}).get("items") or []
                if target == "books":
                    runs.append(grade_books_items(items, "title", "price", "availability", "rating"))
                else:
                    runs.append(grade_quotes_items(items, "text", "author"))
            elif vendor == "zyte":
                if target == "books":
                    items = d.get("products") or []
                    runs.append(grade_books_items(items, "name", "price", None, None))
                else:
                    runs.append(recall_in_text(d.get("browserHtml") or "", target))
            elif vendor == "scraperapi":
                runs.append(recall_in_text(d.get("markdown") or "", target))
            elif vendor == "apify":
                items = d.get("items")
                if not isinstance(items, list):
                    runs.append({"error": "actor not approved"})
                elif target == "books":
                    runs.append(grade_books_items(items, "title", "price", "availability", "rating"))
                else:
                    runs.append(grade_quotes_items(items, "text", "author"))
        key = f"{vendor}-{target}"
        summary[key] = {"runs": runs, "seconds": secs,
                        "consistent": len({json.dumps(r, sort_keys=True) for r in runs}) == 1}

(ROOT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
for k, v in summary.items():
    print(k, "| consistent:", v["consistent"], "| p50s:", statistics.median(v["seconds"]) if v["seconds"] else "-")
    print("   ", v["runs"][0] if v["runs"] else "no runs")
