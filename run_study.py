"""Parsing-fidelity study for best-web-scraping-apis (sheet row 511).

Two sandbox targets with exact ground truth, three runs per vendor per target,
each vendor queried through its own native extraction mechanism:

- HasData: POST /scrape/web with extractRules (CSS + @attr), jsRendering for the JS target
- ScrapingBee: GET /api/v1 with extract_rules (list extraction), render_js for the JS target
- Zyte: POST /v1/extract productList (automatic extraction; no generic selector
  mechanism, so the quotes target falls back to browserHtml and is scored as recall)
- ScraperAPI: GET / with output_format=markdown (no selector mechanism for arbitrary
  sites; scored as recall of ground-truth strings in the text)
- Apify: cheerio-scraper / web-scraper actors with a pageFunction per target,
  run-sync-get-dataset-items with the Apify proxy

Targets:
- books.toscrape.com (static): 20 books x title/price/availability/rating
- quotes.toscrape.com/js/ (JS-rendered): 10 quotes x text/author

Usage: python run_study.py   (keys from environment variables, see README)
Raw responses land next to this script as raw/{vendor}-{target}-run{n}.json
"""
import requests, json, os, time, pathlib, sys

ROOT = pathlib.Path(__file__).parent
RAW = ROOT / "raw-fresh"  # the shipped raw/ stays the published evidence
RAW.mkdir(exist_ok=True)

# Vendor keys come from the environment, one variable per vendor.
keys = {k: os.environ[k] for k in
        ("SCRAPINGBEE_KEY", "ZYTE_KEY", "SCRAPERAPI_KEY", "APIFY_TOKEN")
        if k in os.environ}
HK = os.environ["HASDATA_API_KEY"]

BOOKS = "https://books.toscrape.com/"
QUOTES_JS = "https://quotes.toscrape.com/js/"
RUNS = 3


def save(vendor, target, run, payload):
    p = RAW / f"{vendor}-{target}-run{run}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def hasdata(target, run):
    if target == "books":
        body = {"url": BOOKS, "extractRules": {
            "title": "article.product_pod h3 a @title",
            "price": "article.product_pod p.price_color",
            "availability": "article.product_pod p.instock",
            "rating": "article.product_pod p.star-rating @class"}}
    else:
        body = {"url": QUOTES_JS, "jsRendering": True, "extractRules": {
            "text": "div.quote span.text",
            "author": "div.quote small.author"}}
    t0 = time.time()
    r = requests.post("https://api.hasdata.com/scrape/web",
                      headers={"x-api-key": HK, "Content-Type": "application/json"},
                      json=body, timeout=180)
    dt = time.time() - t0
    d = r.json()
    save("hasdata", target, run, {"status": r.status_code, "seconds": round(dt, 2),
                                   "extractedData": d.get("extractedData")})
    return r.status_code, dt


def scrapingbee(target, run):
    if target == "books":
        rules = {"items": {"selector": "article.product_pod", "type": "list", "output": {
            "title": "h3 a @title", "price": "p.price_color",
            "availability": "p.instock", "rating": "p.star-rating @class"}}}
        params = {"api_key": keys["SCRAPINGBEE_KEY"], "url": BOOKS,
                  "render_js": "false", "extract_rules": json.dumps(rules)}
    else:
        rules = {"items": {"selector": "div.quote", "type": "list", "output": {
            "text": "span.text", "author": "small.author"}}}
        params = {"api_key": keys["SCRAPINGBEE_KEY"], "url": QUOTES_JS,
                  "render_js": "true", "extract_rules": json.dumps(rules)}
    t0 = time.time()
    r = requests.get("https://app.scrapingbee.com/api/v1/", params=params, timeout=180)
    dt = time.time() - t0
    try:
        d = r.json()
    except Exception:
        d = {"nonjson": r.text[:2000]}
    save("scrapingbee", target, run, {"status": r.status_code, "seconds": round(dt, 2), "data": d})
    return r.status_code, dt


def zyte(target, run):
    if target == "books":
        body = {"url": BOOKS, "productList": True}
    else:
        body = {"url": QUOTES_JS, "browserHtml": True}
    t0 = time.time()
    r = requests.post("https://api.zyte.com/v1/extract", auth=(keys["ZYTE_KEY"], ""),
                      json=body, timeout=180)
    dt = time.time() - t0
    d = r.json()
    if target == "books":
        payload = {"status": r.status_code, "seconds": round(dt, 2),
                   "products": (d.get("productList") or {}).get("products")}
    else:
        payload = {"status": r.status_code, "seconds": round(dt, 2),
                   "browserHtml": (d.get("browserHtml") or "")[:200000]}
    save("zyte", target, run, payload)
    return r.status_code, dt


def scraperapi(target, run):
    if target == "books":
        params = {"api_key": keys["SCRAPERAPI_KEY"], "url": BOOKS, "output_format": "markdown"}
    else:
        params = {"api_key": keys["SCRAPERAPI_KEY"], "url": QUOTES_JS,
                  "render": "true", "output_format": "markdown"}
    t0 = time.time()
    r = requests.get("https://api.scraperapi.com/", params=params, timeout=180)
    dt = time.time() - t0
    save("scraperapi", target, run, {"status": r.status_code, "seconds": round(dt, 2),
                                      "markdown": r.text[:200000]})
    return r.status_code, dt


CHEERIO_PF = """async function pageFunction(context) {
  const { $ } = context;
  const out = [];
  $('article.product_pod').each((i, el) => {
    out.push({
      title: $(el).find('h3 a').attr('title'),
      price: $(el).find('p.price_color').text().trim(),
      availability: $(el).find('p.instock').text().trim(),
      rating: $(el).find('p.star-rating').attr('class'),
    });
  });
  return out;
}"""

WEB_PF = """async function pageFunction(context) {
  const out = [];
  document.querySelectorAll('div.quote').forEach((q) => {
    out.push({
      text: q.querySelector('span.text').textContent.trim(),
      author: q.querySelector('small.author').textContent.trim(),
    });
  });
  return out;
}"""


def apify(target, run):
    if target == "books":
        actor, inp = "apify~cheerio-scraper", {
            "startUrls": [{"url": BOOKS}], "pageFunction": CHEERIO_PF,
            "proxyConfiguration": {"useApifyProxy": True},
            "maxCrawlingDepth": 0, "maxPagesPerCrawl": 1}
    else:
        actor, inp = "apify~web-scraper", {
            "startUrls": [{"url": QUOTES_JS}], "pageFunction": WEB_PF,
            "proxyConfiguration": {"useApifyProxy": True},
            "injectJQuery": False, "maxCrawlingDepth": 0, "maxPagesPerCrawl": 1}
    t0 = time.time()
    r = requests.post(f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
                      params={"token": keys["APIFY_TOKEN"], "timeout": 150},
                      json=inp, timeout=200)
    dt = time.time() - t0
    try:
        items = r.json()
    except Exception:
        items = {"nonjson": r.text[:2000]}
    save("apify", target, run, {"status": r.status_code, "seconds": round(dt, 2), "items": items})
    return r.status_code, dt


VENDORS = {"hasdata": hasdata, "scrapingbee": scrapingbee, "zyte": zyte, "scraperapi": scraperapi,
           "apify": apify}
VENDOR_KEY = {"hasdata": "HASDATA_API_KEY", "scrapingbee": "SCRAPINGBEE_KEY", "zyte": "ZYTE_KEY",
              "scraperapi": "SCRAPERAPI_KEY", "apify": "APIFY_TOKEN"}

if __name__ == "__main__":
    for name, env in VENDOR_KEY.items():
        if env not in os.environ:
            print(f"{name}: no {env} in the environment, skipping", flush=True)
    for target in ("books", "quotes"):
        for vendor, fn in VENDORS.items():
            if VENDOR_KEY[vendor] not in os.environ:
                continue
            for run in range(1, RUNS + 1):
                try:
                    st, dt = fn(target, run)
                    print(f"{vendor} {target} run{run}: {st} in {dt:.1f}s", flush=True)
                except Exception as e:
                    print(f"{vendor} {target} run{run}: ERROR {e}", flush=True)
                    save(vendor, target, run, {"error": str(e)})
                time.sleep(2)
    print("collection complete")
