# Bitcoin Price Tracker on Google Cloud

A small serverless pipeline on Google Cloud Platform that checks the Bitcoin price on a schedule, stores every price in BigQuery, compares it with the previous price and sends a Telegram message when the price changes by more than a set threshold.

The project is designed to stay inside the free tiers of the Google Cloud services it uses (target: well under 100 CZK per month).

## Technologies

| Technology | Role in the project |
|---|---|
| RapidAPI: Crypto Market Prices | Source of the BTC/USDT price (Binance). The function calls its HTTP API with an API key. |
| Google Cloud Run functions | Serverless hosting for the Python function (HTTP trigger). The code runs only when it is triggered and is billed per use, with no server to maintain. Formerly called Cloud Functions. |
| Google Cloud Scheduler | Triggers the function every 2 hours with an authenticated HTTP request. |
| Google BigQuery | Stores the price history and provides the previous price for comparison. |
| Google Secret Manager | Stores the RapidAPI key and the Telegram bot token. |
| Telegram Bot API | Delivers the notification to Telegram when the price change reaches the threshold. |
| Python | Language of the function. |

## Goal

1. Get the latest BTC/USDT price from a price API.
2. Save the price with a UTC timestamp in BigQuery.
3. On the next run, read the previous price from BigQuery and calculate the percentage change.
4. If the change reaches the threshold (2% by default), send a notification to Telegram.
5. Run all of this automatically every 2 hours.

## Architecture

```
Cloud Scheduler (every 2 hours)
        |  HTTPS request with OIDC token
        v
Cloud Run function (Python, HTTP)
        |-- reads previous price  --> BigQuery
        |-- gets current price    --> RapidAPI (crypto market prices, Binance BTC/USDT)
        |-- writes new price      --> BigQuery
        '-- if change >= threshold --> Telegram Bot API --> message on phone
```

Secrets (the RapidAPI key and the Telegram bot token) are stored in Secret Manager and passed to the function as environment variables that reference the secrets.

## Repository structure

| File | Purpose |
|---|---|
| `main.py` | HTTP entry point (`check_price_and_alert`). Coordinates all steps and compares the prices. |
| `get_old_price.py` | Reads and returns the most recent price from the last 24 hours in BigQuery. |
| `get_new_price.py` | Calls the price API and returns the current price. |
| `write_new_price.py` | Inserts one row (timestamp and price) into BigQuery. |
| `telegram_send_message.py` | Sends a message through the Telegram Bot API. |
| `requirements.txt` | Python dependencies: `functions-framework`, `google-cloud-bigquery`, `python-telegram-bot`. |

## How it works

1. Cloud Scheduler sends an authenticated HTTP request to the function.
2. The function reads the previous price from BigQuery. This happens **before** the new price is saved, otherwise the "previous" price would be the new one.
3. It fetches the current price from the API.
4. It saves the new price as one row with a UTC timestamp.
5. If there is no previous price (first run), it returns a "first run" response without comparing. The new price has already been saved at this point.
6. Otherwise it calculates the percentage change (`new * 100 / old - 100`) with `Decimal` and compares its absolute value with the threshold (`THRESHOLD = 2`, a constant in `main.py`).
7. If the threshold is reached, it sends a Telegram message with the old price, the new price, the direction (`positive` or `negative`) and the size of the change.
8. It returns a short text response.

**Error handling**

- If saving the price fails, `write_new_price.py` raises an exception. The call ends with a 500 and the logs show BigQuery's reason, so a failed save is never silent.
- If the Telegram call fails, the error is caught in `main.py` and printed to the logs. The saved price is not affected and the call still returns normally.
- Every code path in the entry point must return a response (text, optionally with a status code). Returning nothing (`None`) causes a 500.

## Design decisions

- **Timestamps are stored in UTC.** A timezone is only needed when showing a time to a person.
- **`Decimal` for the calculation.** The API returns the price as a string, and `Decimal` handles it exactly. Decimals and floats must not be mixed in arithmetic.
- **Read the old price before writing the new one.** Otherwise the "previous" price would be the price that was just saved.
- **Threshold as a constant in code.** It is the simplest option for a small project. It can later move to an environment variable.
- **Safeguards.** Max instances 1 and minimal Scheduler retries keep mistakes and costs small.

## Setup

### 1. Google Cloud project

- Create a project and link a billing account (needed for Cloud Run functions and Cloud Scheduler, even when staying in the free tier).
- Create a budget alert (for example around 50 CZK). A budget only sends notifications; it does not stop spending.
- Choose one region for all resources (this project uses `europe-west1`).

### 2. APIs to enable

| API | Why it is needed |
|---|---|
| BigQuery API | Create the dataset and table, write and query prices. |
| Cloud Run functions API (`run.googleapis.com`, `cloudfunctions.googleapis.com`) | Create and deploy the function. |
| Cloud Build API | Builds the function code into a container image at deploy time. |
| Artifact Registry API | Stores the built image. |
| Cloud Scheduler API | Create the scheduled job. |
| Secret Manager API | Store the API key and the Telegram token. |

Enabling an API is free. You only pay for usage above the free tiers.

External APIs (nothing to enable in Google Cloud): a crypto price API on RapidAPI and the Telegram Bot API.

### 3. BigQuery

- Dataset: `cryptocurrency` (same region as the other resources; the location cannot be changed later).
- Table with at least these columns:

| Column | Type | Meaning |
|---|---|---|
| `timestamp` | TIMESTAMP | When the price was fetched (UTC). |
| `price` | FLOAT or NUMERIC | Bitcoin price in USD (USDT). |

- Optional: partition the table by day on `timestamp`. It makes queries cheaper as the table grows.
- Tip: use a simple table name without spaces (for example `bitcoin_usd_price`). Names with spaces need backticks in SQL.

### 4. Secrets

Create two secrets in Secret Manager:

| Secret | Content |
|---|---|
| `rapidapi-key` | RapidAPI key |
| `telegram-key` | Telegram bot token (from @BotFather) |

When deploying the function, expose each secret as an environment variable with the same name by **referencing the secret** (not by typing the value as a plain variable).

**Never commit keys or tokens.** If a key was ever pasted into code or a chat, rotate it.

### 5. Telegram bot

1. Create a bot with @BotFather and save the token (into Secret Manager).
2. Send any message to your bot.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read the chat ID from `message.chat.id`. Do **not** use `update_id`; that is a different number.
4. Put the chat ID in `telegram_send_message.py` (or, optionally, in an environment variable).

### 6. IAM roles

The function runs as a service account (here the default Compute Engine service account). Grant it the narrowest roles that work:

| Role | Granted on | Why |
|---|---|---|
| Secret Manager Secret Accessor | each secret | Read the API key and the Telegram token. |
| BigQuery Data Editor | the dataset | Insert rows. |
| BigQuery Job User | the project | Run the query that reads the previous price. |

The service account used by Cloud Scheduler needs:

| Role | Granted on | Why |
|---|---|---|
| Cloud Run Invoker | the function (its Cloud Run service) | Allow Scheduler to call the function. |

For better isolation, create a dedicated service account for the function instead of using the default one.

### 7. Deploying the function

- Runtime: Python, trigger: HTTP, authentication required.
- Entry point: `check_price_and_alert` (must match the function name in `main.py` exactly).
- Region: `europe-west1`.
- Max instances: 1 (protects against runaway costs).
- Dependencies in `requirements.txt`: `functions-framework`, `google-cloud-bigquery`, `python-telegram-bot`.

### 8. Cloud Scheduler job

| Setting | Value |
|---|---|
| Frequency | `0 */2 * * *` (every 2 hours) |
| Target type | HTTP |
| URL | the function URL |
| Method | POST |
| Auth header | Add OIDC token |
| Service account | the account with Cloud Run Invoker |
| Audience | the function URL (no path or parameters) |
| Retry settings | Keep minimal. A retry after a partial failure could save a duplicate row. |

### 9. Testing and monitoring

- **Manual call:** open the function in the console, go to the Testing tab and choose "Test in Cloud Shell". It runs a `curl` command with an identity token, and the function's response appears in the terminal. The JSON payload shown there is ignored by this function.
- **Scheduler run:** use "Force run". The job status only says whether the attempt succeeded. The text returned by the function is not visible there.
- **Logs:** the function's Logs tab, or `gcloud run services logs read SERVICE_NAME --region=REGION`. They contain `print` output, tracebacks and one entry per request with its status code. Cloud Scheduler writes its own entries (for example `AttemptFinished`) in a separate log.
- **Test the alert path:** temporarily set `THRESHOLD` to a very small value, run the function twice, and check that the Telegram message arrives with the right direction. Then set it back to 2.
- **Check the whole chain after a run:** Scheduler status, function logs, a new BigQuery row, and Telegram when the threshold is reached.

## Cost

At 12 runs per day (about 360 per month), the function, Scheduler, BigQuery and Secret Manager should stay within their free tiers. Things that can still cost a little: repeated deployments (Cloud Build minutes), old images in Artifact Registry, and the API plan limits on RapidAPI. Check Billing reports after the first few days.

## Troubleshooting notes

| Symptom | Cause and fix |
|---|---|
| Deploy fails with "container failed to start and listen on port 8080" | The Python code crashed while loading: a syntax error (for example a `return` outside the function, or `raise` written with a comma), a missing file or library, or an entry point not matching the function name. Read the logs. |
| `500 Internal Server Error` when calling the function | The code failed while handling the request. The Traceback in the logs shows the reason. |
| Scheduler shows `403 PERMISSION_DENIED` | The Scheduler service account lacks Cloud Run Invoker, or the job has no OIDC token. |
| Telegram returns `400` | Wrong chat ID (for example `update_id` used instead of `chat.id`), or the bot has not received a message from you yet. |
| `No matching signature for operator =` in BigQuery | A TIMESTAMP column was compared with a DATE. Compare timestamps with timestamps (for example a sliding window with `TIMESTAMP_SUB`). |
| `bigquery.client()` fails | The class is `bigquery.Client()` with a capital C. |
| Every call returns a 500 right after the helper functions run | The entry point returned nothing. Every code path must return a response. |
| The deploy succeeds but a test still shows the old behavior | A failed deploy leaves the previous revision serving traffic. Check that the latest revision deployed successfully. |

## Known limitations and ideas

- The comparison uses the last saved price, so slow drifts that never exceed the threshold between two runs do not trigger an alert.
- If the function stops working, nothing notifies you. Idea: send a Telegram message on errors, or add a Cloud Monitoring alert.
- A failed Telegram message is only visible in the logs.
- If there is no price in the last 24 hours, the next run is treated as a first run.
- Rows added by streaming inserts may not be deletable or editable for a while, so clean up test rows later.
- Ideas: print the result message to the logs so every run leaves a trace, compare against an hourly or daily average, move the threshold to an environment variable, add partition expiration, chart the history in Looker Studio, track more coins.

## Security

- No keys, tokens or passwords in the repository (use Secret Manager).
- Rotate any key that was ever exposed.
- Keep the function private (authentication required) and call it only through Cloud Scheduler.
- Grant only the roles listed above, on the narrowest scope possible.
- Git keeps its history. A key that was ever committed must be rotated, even if it was deleted later.
- Chat IDs and project IDs are not secrets, but use placeholders or environment variables in a public repository.
- Never print a token, a key, or a URL that contains one.
