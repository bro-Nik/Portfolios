from flask_login import UserMixin

from portfolio_tracker.app import db


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total_spent = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    order = db.Column(db.Boolean)
    # Relationships
    asset = db.relationship('Asset',
                            backref=db.backref('transactions', lazy=True))
    wallet = db.relationship('Wallet',
                             backref=db.backref('transactions', lazy=True))


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker_id = db.Column(db.String(255), db.ForeignKey('ticker.id'))
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    percent = db.Column(db.Float, default=0)
    comment = db.Column(db.String(1024))
    # Relationships
    ticker = db.relationship('Ticker',
                             backref=db.backref('assets', lazy=True))
    portfolio = db.relationship('Portfolio',
                                backref=db.backref('assets', lazy=True))


class otherAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))
    name = db.Column(db.String(255))
    percent = db.Column(db.Float, default=0)
    comment = db.Column(db.String(1024), default='')
    # Relationships
    portfolio = db.relationship('Portfolio',
                                backref=db.backref('other_assets', lazy=True))


class otherAssetOperation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    total_spent = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('otherAsset',
                            backref=db.backref('operations', lazy=True))


class otherAssetBody(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    total_spent = db.Column(db.Float)
    cost_now = db.Column(db.Float)
    comment = db.Column(db.String(1024))
    # Relationships
    asset = db.relationship('otherAsset',
                            backref=db.backref('bodys', lazy=True))


class Ticker(db.Model):
    id = db.Column(db.String(256), primary_key=True)
    name = db.Column(db.String(1024))
    symbol = db.Column(db.String(124))
    image = db.Column(db.String(1024))
    market_cap_rank = db.Column(db.Integer)
    market_id = db.Column(db.String(32),
                          db.ForeignKey('market.id'),
                          primary_key=True)
    # Relationships
    market = db.relationship('Market',
                             backref=db.backref('tickers', lazy=True))


class Market(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(255))


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(255))
    money_all = db.Column(db.Float, default=0)
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('wallets', lazy=True))


class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    market_id = db.Column(db.String(32), db.ForeignKey('market.id'))
    name = db.Column(db.String(255))
    comment = db.Column(db.String(1024))
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('portfolios', lazy=True))
    market = db.relationship('Market',
                             backref=db.backref('portfolios', lazy=True))


class WhitelistTicker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ticker_id = db.Column(db.Integer, db.ForeignKey('ticker.id'))
    comment = db.Column(db.Text)
    # Relationships
    user = db.relationship('User',
                           backref=db.backref('whitelist_tickers', lazy=True))
    ticker = db.relationship('Ticker',
                             backref=db.backref('whitelist_ticker', lazy=True),
                             uselist=False)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    whitelist_ticker_id = db.Column(db.Integer,
                                    db.ForeignKey('whitelist_ticker.id'))
    price = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    status = db.Column(db.String, default='on')
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    # Relationships
    asset = db.relationship('Asset',
                            backref=db.backref('alerts', lazy=True))
    whitelist_ticker = db.relationship('WhitelistTicker',
                                       backref=db.backref('alerts', lazy=True))
    transaction = db.relationship('Transaction',
                                  backref='alert',
                                  uselist=False)


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    value = db.Column(db.String(32))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255))
    locale = db.Column(db.String(32), default='')
    timezone = db.Column(db.String(32), default='')
    # Relationships
    info = db.relationship('userInfo',
                           backref=db.backref('user', lazy=True), uselist=False)


class userInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_visit = db.Column(db.String(255))
    last_visit = db.Column(db.String(255))
    country = db.Column(db.String(255))
    city = db.Column(db.String(255))
