from get_old_price import get_old_price
from write_new_price import write_new_price
from get_new_price import get_new_price
from decimal import *
from telegram_send_message import send_telegram_message

THRESHOLD = 2


def check_price_and_alert(request):

    old_price = get_old_price()
    new_price = get_new_price()
    result = write_new_price(new_price)

    if old_price is None or Decimal(old_price) == 0:
        return "First run, nothing to compare yet", 200

    percentage = Decimal(new_price) * 100 / Decimal(old_price)
    difference_percent = percentage - 100

    alert = abs(difference_percent) >= THRESHOLD

    if difference_percent > 0:
        change = "positive"
    else: 
        change = "negative"

    message = f"Old price: {old_price}, new price: {new_price}, direction: {change}, change: {round(abs(difference_percent), 3)}"
    print(message)

    if alert:
        try:
            send_telegram_message(message)
        except Exception as error:
            print(f"Telegram failed: {error}")

    return message, 200