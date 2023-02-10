from flask_login import UserMixin

from portfolio_tracker.app import db


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset = db.relationship('Asset', backref=db.backref('transactions', lazy=True))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total_spent = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    wallet = db.relationship('Wallet', backref=db.backref('transactions', lazy=True))
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'))
    order = db.Column(db.Boolean)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.relationship('Ticker', backref=db.backref('assets', lazy=True))
    ticker_id = db.Column(db.String(255), db.ForeignKey('ticker.id'))
    quantity = db.Column(db.Float)
    total_spent = db.Column(db.Float)
    percent = db.Column(db.Float)
    comment = db.Column(db.String(1024))
    portfolio = db.relationship('Portfolio', backref=db.backref('assets', lazy=True))
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))

class otherAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    url = db.Column(db.String(32))
    total_spent = db.Column(db.Float)
    percent = db.Column(db.Float)
    comment = db.Column(db.String(1024))
    portfolio = db.relationship('Portfolio', backref=db.backref('other_assets', lazy=True))
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'))

class otherAssetOperation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset = db.relationship('otherAsset', backref=db.backref('operations', lazy=True))
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    total_spent = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))

class otherAssetBody(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    date = db.Column(db.String(32))
    asset = db.relationship('otherAsset', backref=db.backref('bodys', lazy=True))
    asset_id = db.Column(db.Integer, db.ForeignKey('other_asset.id'))
    total_spent = db.Column(db.Float)
    cost_now = db.Column(db.Float)
    comment = db.Column(db.String(1024))

class Ticker(db.Model):
    id = db.Column(db.String(255), primary_key=True)
    name = db.Column(db.String(255))
    symbol = db.Column(db.String(128))
    image = db.Column(db.String(128))
    market_cap_rank = db.Column(db.Integer)
    market = db.relationship('Market', backref=db.backref('tickers', lazy=True))
    market_id = db.Column(db.String(32), db.ForeignKey('market.id'))

class Market(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(255))

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    money_all = db.Column(db.Float)
    money_in_order = db.Column(db.Float)
    user = db.relationship('User', backref=db.backref('wallets', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(32))
    name = db.Column(db.String(255))
    comment = db.Column(db.String(1024))
    market = db.relationship('Market', backref=db.backref('portfolios', lazy=True))
    market_id = db.Column(db.String(32), db.ForeignKey('market.id'))
    user = db.relationship('User', backref=db.backref('portfolios', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(32))
    asset = db.relationship('Asset', backref=db.backref('alerts', lazy=True))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    trackedticker = db.relationship('Trackedticker', backref=db.backref('alerts', lazy=True))
    trackedticker_id = db.Column(db.Integer, db.ForeignKey('trackedticker.id'))
    price = db.Column(db.Float)
    type = db.Column(db.String(24))
    comment = db.Column(db.String(1024))
    worked = db.Column(db.Boolean)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    value = db.Column(db.String(32))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

class userInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.relationship('User', backref=db.backref('info', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    first_visit = db.Column(db.String(255))
    last_visit = db.Column(db.String(255))
    country = db.Column(db.String(255))
    city = db.Column(db.String(255))

class Trackedticker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.relationship('Ticker', backref=db.backref('trackedtickers', lazy=True))
    ticker_id = db.Column(db.String(255), db.ForeignKey('ticker.id'))
    user = db.relationship('User', backref=db.backref('trackedtickers', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(1024))
    user = db.relationship('User', backref=db.backref('feedbacks', lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))