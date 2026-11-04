import json
import urllib.request as req
import pandas as pd
from pathlib import Path
import pyarrow


with req.urlopen('https://api.hypixel.net/v2/skyblock/bazaar') as r:
    raw_data = json.load(r)

print(raw_data['success'], raw_data['lastUpdated'], len(raw_data['products']))


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

    with open('data/bz.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

    return data


KEEP = pd.Timedelta("30days")


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


data = processData(raw_data)
for field in ('buy_price', 'sell_price'):
    row = createRowSnapshot(data, field)
    hist = updateHistory(row, f"data/{field}.parquet")
    