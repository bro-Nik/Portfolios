from __future__ import annotations

from ..app import db
from .models import OtherBody, OtherTransaction, Portfolio, Asset, \
    OtherAsset, PriceHistory, Ticker, Transaction


class PortfolioRepository:

    @staticmethod
    def get(portfolio_id: int | str | None) -> Portfolio | None:
        if portfolio_id:
            return db.session.execute(
                db.select(Portfolio).filter_by(id=portfolio_id)).scalar()

    @staticmethod
    def save(portfolio: Portfolio) -> None:
        if not portfolio in db.session:
            db.session.add(portfolio)
        db.session.commit()

    @staticmethod
    def delete(portfolio: Portfolio) -> None:
        db.session.delete(portfolio)
        db.session.commit()


class TickerRepository:

    @staticmethod
    def get(ticker_id: str | None) -> Ticker | None:
        if ticker_id:
            return db.session.execute(
                db.select(Ticker).filter_by(id=ticker_id)).scalar()

    @staticmethod
    def get_with_market_paginate(market, search: str = '', page: int = 1):
        """Выдает частями тикеры определенного рынка"""
        select = db.select(Ticker).where(Ticker.market == market)
        select = select.order_by(Ticker.market_cap_rank.is_(None),
                                 Ticker.market_cap_rank.asc())

        if search:
            select = select.filter(Ticker.name.contains(search) |
                                   Ticker.symbol.contains(search))

        return db.paginate(select, page=page, per_page=20, error_out=False)

    @staticmethod
    def get_with_ids(ids: list | None = None):
        """Выдает частями тикеры определенного рынка"""
        select = db.select(Ticker).filter(Ticker.id.in_(ids))
        return db.session.execute(select).scalars()

    @staticmethod
    def delete(ticker: Ticker) -> None:
        db.session.delete(ticker)
        db.session.commit()


class AssetRepository:

    @staticmethod
    def save(asset: Asset) -> None:
        if not asset in db.session:
            db.session.add(asset)
        db.session.commit()

    @staticmethod
    def delete(asset: Asset) -> None:
        db.session.delete(asset)
        db.session.commit()


class OtherAssetRepository:

    @staticmethod
    def save(asset: OtherAsset) -> None:
        if not asset in db.session:
            db.session.add(asset)
        db.session.commit()

    @staticmethod
    def delete(asset: OtherAsset) -> None:
        db.session.delete(asset)
        db.session.commit()


class TransactionRepository:

    # @staticmethod
    # def add(transaction: Transaction) -> None:
    #     """Добавляет новую транзакцию в сессиию."""
    #     if not transaction.id:
    #         db.session.add(transaction)

    @staticmethod
    def save(transaction: Transaction) -> None:
        if not transaction in db.session:
            db.session.add(transaction)
        db.session.commit()

    @staticmethod
    def delete(transaction: Transaction) -> None:
        db.session.delete(transaction)
        db.session.commit()


class OtherTransactionRepository:

    @staticmethod
    def save(transaction: OtherTransaction) -> None:
        if not transaction in db.session:
            db.session.add(transaction)
        db.session.commit()

    @staticmethod
    def delete(transaction: OtherTransaction) -> None:
        db.session.delete(transaction)
        db.session.commit()

class BodyRepository:

    @staticmethod
    def save(body: OtherBody) -> None:
        if not body in db.session:
            db.session.add(body)
        db.session.commit()

    @staticmethod
    def delete(body: OtherBody) -> None:
        db.session.delete(body)
        db.session.commit()


class PriceHistoryRepository:

    @staticmethod
    def delete(price: PriceHistory) -> None:
        db.session.delete(price)
        db.session.commit()
