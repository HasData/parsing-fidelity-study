# Parsing Fidelity Study

![HasData, one of the vendors measured and the company that ran the study](banner.png)

Five web scraping APIs asked to extract the same structured data from the same pages through their own native mechanisms, graded field by field against locally parsed ground truth. This is the study behind the parsing column of [our web scraping APIs comparison](https://hasdata.com/blog/best-web-scraping-apis?utm_source=github&utm_medium=syndication&utm_campaign=best-web-scraping-apis&utm_content=parsing-fidelity-study-readme).

## Table of Contents

- [Method](#method)
- [Results](#results)
- [Project Structure](#project-structure)
- [Running It](#running-it)
- [Disclaimer](#disclaimer)
- [More Resources](#more-resources)

## Method

The targets are two sandbox pages with exact ground truth, a static catalogue (20 books, four fields each) and a JS-rendered quotes page (10 quotes, two fields each). Each vendor ran three times per target through its own extraction mechanism. HasData and ScrapingBee used declarative rules, Zyte its automatic schema, Apify a `pageFunction`, and ScraperAPI its markdown output. Every vendor's three runs graded identically, field for field (`consistent` in `summary.json`).

## Results

`summary.json` carries the grades, `raw/` the untouched responses per vendor per run.

| Vendor | Mechanism | Static catalogue | JS-rendered quotes |
|---|---|---|---|
| HasData | `extractRules`, CSS with `@attr` | 20/20 on all four fields | 10/10 on both fields |
| ScrapingBee | `extract_rules` list | 20/20 on all four fields | 10/10 on both fields |
| Apify | `pageFunction` you write | 20/20 on all four fields | 10/10 on both fields |
| Zyte | automatic `productList` schema | names 10/20 (truncated link text), price 20/20, no availability or rating fields | no selector mechanism, full recall in raw `browserHtml` |
| ScraperAPI | markdown output | no structured output, full recall in markdown | full recall, render on |

The declarative-rules vendors and the `pageFunction` route reproduce the page exactly. The automatic-schema route returns the fields its schema covers, and the markdown route hands the parsing back to you. Apify's grade tracks your own selectors by construction, since the mechanism is code you write.

## Project Structure

```
parsing-fidelity-study/
├── run_study.py        # sends the three runs per vendor per target
├── grade.py            # grades responses against ground truth
├── ground-truth.json   # the locally parsed expected values
├── summary.json        # the grades
└── raw/                # every response, per vendor per run
```

The shipped `raw/` holds all 30 responses, three per vendor per target.

## Running It

`run_study.py` reads one environment variable per vendor (`HASDATA_API_KEY`, `SCRAPINGBEE_KEY`, `ZYTE_KEY`, `SCRAPERAPI_KEY`, `APIFY_TOKEN`). `HASDATA_API_KEY` is required, and the other four vendors are skipped when their key is missing. `grade.py` re-grades the shipped `raw/` by default, and a fresh collection lands in `raw-fresh/` so the published evidence stays intact, graded with `python grade.py raw-fresh`. A full pass spends paid credits on every vendor it reaches.

## Disclaimer

The targets are public scraping sandboxes built for exactly this use. Whether and how scraping fits other targets depends on jurisdiction and terms, and nothing in this repository is legal advice. [Is Web Scraping Legal?](https://hasdata.com/blog/is-web-scraping-legal?utm_source=github&utm_medium=syndication&utm_campaign=best-web-scraping-apis&utm_content=parsing-fidelity-study-readme) covers how we think about the question.

## More Resources

- [Best Web Scraping APIs](https://hasdata.com/blog/best-web-scraping-apis?utm_source=github&utm_medium=syndication&utm_campaign=best-web-scraping-apis&utm_content=parsing-fidelity-study-readme), the comparison this study feeds
- [Web Scraping with AI](https://hasdata.com/blog/web-scraping-with-ai?utm_source=github&utm_medium=syndication&utm_campaign=best-web-scraping-apis&utm_content=parsing-fidelity-study-readme), where extraction fidelity meets LLMs
