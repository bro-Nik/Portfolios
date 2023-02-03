from flask_login import UserMixin

from portfolio_tracker.app import db


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String)
    asset = db.relationship('Asset', backref=db.backref('transactions', lazy=True))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total_spent = db.Column(db.Float)
    type = db.Column(db.String)
    comment = db.Column(db.String)
    wallet = db.relationship('Wallet', backref=db.backref('transactions', lazy=True))
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    order = db.Column(db.Boolean)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.relationship('Ticker', backref=db.backref('assets', lazy=True))
    ticker_id = db.Column(db.Integer, db.ForeignKey('ticker.id'))
    quantity = db.Column(db.Float)
    total_spent = db.Column(db.Float)
    #order = db.Column(db.Float)
    percent = db.Column(db.Float)
    comment = db.Column(db.String)
    portfolio = db.relationship('Portfolio', backref=db.backref('assets', lazy=True))
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))

class Ticker(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)
    symbol = db.Column(db.String)
    image = db.Column(db.String)
    market_cap_rank = db.Column(db.Integer)
    link = db.Column(db.String)
    market = db.relationship('Market', backref=db.backref('tickers', lazy=True))
    market_id = db.Column(db.Integer, db.ForeignKey('market.id'))

class Market(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    money_all = db.Column(db.Float)
    money_in_order = db.Column(db.Float)
    user = db.relationship('User', backref=db.backref('wallets', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String)
    name = db.Column(db.String)
    comment = db.Column(db.String)
    market = db.relationship('Market', backref=db.backref('portfolios', lazy=True))
    market_id = db.Column(db.Integer, db.ForeignKey('market.id'))
    user = db.relationship('User', backref=db.backref('portfolios', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String)
    asset = db.relationship('Asset', backref=db.backref('alerts', lazy=True))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    trackedticker = db.relationship('Trackedticker', backref=db.backref('alerts', lazy=True))
    trackedticker_id = db.Column(db.Integer, db.ForeignKey('trackedticker.id'))
    price = db.Column(db.Float)
    type = db.Column(db.String)
    comment = db.Column(db.String)
    worked = db.Column(db.Boolean)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    value = db.Column(db.String)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    email = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

class Trackedticker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.relationship('Ticker', backref=db.backref('trackedtickers', lazy=True))
    ticker_id = db.Column(db.Integer, db.ForeignKey('ticker.id'))
    user = db.relationship('User', backref=db.backref('trackedtickers', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))