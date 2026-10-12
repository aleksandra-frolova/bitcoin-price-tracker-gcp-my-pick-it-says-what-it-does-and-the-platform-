from google.cloud import bigquery
from datetime import datetime, timezone

def write_new_price(new_price):
    TABLE_ID = "project-7d74aa98-cf44-4087-9fc.cryptocurrency.Bitcoin USD price"
    client = bigquery.Client()
    row = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "price": new_price,  # a number extracted from the API response
    }
    errors = client.insert_rows_json(TABLE_ID, [row])
    if errors:
        print(errors)
        raise Exception("Insert failed", 500)
    return f"Saved {new_price}", 200