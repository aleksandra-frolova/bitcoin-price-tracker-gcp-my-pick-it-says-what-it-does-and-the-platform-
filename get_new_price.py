import functions_framework
import http.client
import os
import json
from google.cloud import bigquery

@functions_framework.http
def get_new_price():
    conn = http.client.HTTPSConnection("crypto-market-prices.p.rapidapi.com", timeout=10)
    headers = {
        "x-rapidapi-key": os.environ["rapidapi-key"],
        "x-rapidapi-host": "crypto-market-prices.p.rapidapi.com",
    }
    conn.request("GET", "/exchanges/binance/BTC?base=USDT", headers=headers)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    
    py_object = json.loads(data)
    price = py_object.get("data").get("price")
    return price