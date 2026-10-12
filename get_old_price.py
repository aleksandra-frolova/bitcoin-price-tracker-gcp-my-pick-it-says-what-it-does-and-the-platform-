from google.cloud import bigquery

def get_old_price():
    client = bigquery.Client()
    query = """SELECT price FROM `project-7d74aa98-cf44-4087-9fc.cryptocurrency.Bitcoin USD price` 
    WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
    ORDER BY timestamp DESC
    LIMIT 1"""

    query_job = client.query(query)
    rows = query_job.result()
    for row in rows:
        return row["price"]


