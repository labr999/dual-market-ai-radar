import datetime as dt
import json
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "quotes.json"
TW = ["2330", "2454", "2317", "2382", "2308"]
US = ["NVDA", "MSFT", "AVGO", "GOOGL", "META", "AAPL", "TSLA", "AMZN"]
INDICES = ["^TWII", "^DJI", "^IXIC", "^SOX"]
HEADERS = {"User-Agent": "Mozilla/5.0 dual-market-ai-radar/1.0", "Accept": "application/json"}

def get_json(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)

def yahoo(symbol):
    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=5m&range=5d&includePrePost=false"
    result = get_json(url)["chart"]["result"][0]
    meta = result.get("meta", {})
    values = result.get("indicators", {}).get("quote", [{}])[0]
    closes = [x for x in values.get("close", []) if isinstance(x, (int, float))]
    price = meta.get("regularMarketPrice", closes[-1] if closes else None)
    previous = meta.get("chartPreviousClose", meta.get("previousClose", closes[-2] if len(closes) > 1 else price))
    market_time = meta.get("regularMarketTime")
    return {
        "symbol": symbol,
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "price": price,
        "previous_close": previous,
        "high": meta.get("regularMarketDayHigh"),
        "low": meta.get("regularMarketDayLow"),
        "market_time": dt.datetime.fromtimestamp(market_time, dt.timezone.utc).isoformat() if market_time else None,
        "history": closes[-60:],
        "source": "Yahoo Finance delayed",
        "twse_verified": False,
    }

def twse_rows():
    rows = get_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
    return {str(row.get("Code")): row for row in rows}

def main():
    official = {}
    try:
        official = twse_rows()
    except Exception as exc:
        print(f"TWSE unavailable: {exc}")
    quotes, errors = {}, {}
    for symbol in [f"{code}.TW" for code in TW] + US + INDICES:
        try:
            item = yahoo(symbol)
            if symbol.endswith(".TW"):
                code = symbol[:-3]
                row = official.get(code)
                if row:
                    item["name"] = row.get("Name") or item["name"]
                    item["twse_verified"] = True
                    item["twse_close"] = row.get("ClosingPrice")
            quotes[symbol] = item
        except Exception as exc:
            errors[symbol] = str(exc)
    payload = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "quotes": quotes, "errors": errors}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not quotes:
        raise SystemExit("No quote provider returned data")

if __name__ == "__main__":
    main()
