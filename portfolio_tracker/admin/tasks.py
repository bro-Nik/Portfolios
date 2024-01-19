from ..app import db, celery
from ..watchlist.models import WatchlistAsset
from . import currency, stocks, crypto


@celery.task(bind=True, name='crypto_load_prices', default_retry_delay=300)
def crypto_load_prices(self):
    crypto.load_prices()
    self.retry()


@celery.task(name='crypto_load_tickers')
def crypto_load_tickers():
    crypto.load_tickers()


@celery.task(name='stocks_load_images')
def stocks_load_images():
    stocks.load_images()


@celery.task(name='stocks_load_tickers')
def stocks_load_tickers():
    stocks.load_tickers()


@celery.task(bind=True, name='stocks_load_prices', default_retry_delay=300)
def stocks_load_prices(self):
    stocks.load_prices()
    self.retry()


@celery.task(name='currency_load_tickers')
def currency_load_tickers():
    currency.load_tickers()


@celery.task(bind=True, name='currency_load_prices', default_retry_delay=300)
def currency_load_prices(self):
    currency.load_prices()
    self.retry()


@celery.task(name='currency_load_history')
def currency_load_history():
    currency.load_history()


@celery.task(bind=True, name='alerts_update', default_retry_delay=300)
def alerts_update(self):
    # Отслеживаемые тикеры
    tracked_tickers = db.session.execute(db.select(WatchlistAsset)).scalars()

    for ticker in tracked_tickers:
        price = ticker.ticker.price
        if not ticker.alerts or not price:
            continue

        for alert in ticker.alerts:
            if alert.status != 'on':
                continue

            if ((alert.type == 'down' and price <= alert.price)
                    or (alert.type == 'up' and price >= alert.price)):
                alert.status = 'worked'

    db.session.commit()
    self.retry()
