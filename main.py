import json
import urllib.request as req
import pandas as pd
from pathlib import Path


URL = "https://api.hypixel.net/v2/skyblock/bazaar"
DATA_DIR = Path("data")
KEEP = pd.Timedelta("30days")
WEEK = pd.Timedelta("7D")


def fetchBazaarData():
    with req.urlopen(URL) as r:
        raw = json.load(r)
    if not raw.get('success'):
        raise RuntimeError("Bazaar API returned 'UNSUCCESSFUL'")
    return raw

def top(orders, pick):
    prices = [price['pricePerUnit'] for price in orders]
    return round(pick(prices), 1) if prices else None


def processData(dat: dict):
    data = {k: {
            "sell_price": top(v['sell_summary'], max),
            "buy_price": top(v['buy_summary'], min),
            "sell_volume": v['quick_status']['sellVolume'],
            "buy_volume": v['quick_status']['buyVolume'],
            "sell_moving_Week": v['quick_status']['sellMovingWeek'],
            "buy_moving_week": v['quick_status']['buyMovingWeek'],
            "sell_orders": v['quick_status']['sellOrders'],
            "buy_orders": v['quick_status']['buyOrders']
        }
        for k, v in dat['products'].items()
    }
    data = (dat['lastUpdated'], dict(sorted(data.items())))

    # with open('data/bz.json', 'w', encoding='utf-8') as f:
    #     json.dump(data, f, indent=4)

    return data


def createRowSnapshot(dat: tuple, field: str):
    timestamp = pd.to_datetime(dat[0], unit="ms", utc=True)
    row = pd.DataFrame([{k: v[field] for k, v in dat[1].items()}], index=[timestamp])
    return row.astype('Float64')


def updateHistory(row, path):
    path = Path(path)
    if path.exists():
        hist = pd.read_parquet(path)
        if row.index[0] <= hist.index[-1]:
            return hist
        hist = pd.concat([hist, row])
    else:
        hist = row

    hist = hist.loc[hist.index[-1] - KEEP:]
    hist.to_parquet(path, compression="zstd")
    return hist


def cleanNumber(x): return None if pd.isna(x) else round(float(x), 1)


def computeStats(histories):
    fields = {}
    for field, history in histories.items():
        latest_ts = history.index[-1]
        now = history.iloc[-1]
        week = history.loc[latest_ts - WEEK:].median()
        month = history.median()
        fields[field] = {
            name: [cleanNumber(now[name]), cleanNumber(week[name]), cleanNumber(month[name])]
            for name in history.columns
        }

    empty_template = [None, None, None]
    unique_item_names = sorted(set(fields["sell_price"]) | set(fields["buy_price"]))
    return {
        name: [fields["sell_price"].get(name, empty_template), fields["buy_price"].get(name, empty_template)]
        for name in unique_item_names
    }



def main():
    DATA_DIR.mkdir(exist_ok=True)
    raw_data = fetchBazaarData()
    print(raw_data['success'], raw_data['lastUpdated'], len(raw_data['products']))
    data = processData(raw_data)

    histories = {}
    for field in ('buy_price', 'sell_price'):
        row = createRowSnapshot(data, field)
        histories[field] = updateHistory(row, DATA_DIR / f"{field}.parquet")

    stats = computeStats(histories, )
    with open(DATA_DIR / "stats.json", 'w', encoding='utf-8') as f:
        json.dump(stats, f, separators=(',', ':'))


if __name__ == "__main__":
    main()