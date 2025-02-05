from __future__ import annotations
from typing import TYPE_CHECKING

from portfolio_tracker.portfolio.models import Ticker
from portfolio_tracker.wallet.models import Wallet, WalletAsset

from ..app import db

if TYPE_CHECKING:
    pass


class WalletRepository:

    @staticmethod
    def get(wallet_id: int | str | None) -> Wallet | None:
        if wallet_id:
            return db.session.execute(
                db.select(Wallet).filter_by(id=wallet_id)).scalar()

    @staticmethod
    def save(wallet: Wallet) -> None:
        if not wallet.id:
            db.session.add(wallet)
        db.session.commit()

    @staticmethod
    def delete(wallet: Wallet) -> None:
        db.session.delete(wallet)
        db.session.commit()

class WalletAssetRepository:

    @staticmethod
    def create() -> WalletAsset:
        """Возвращает новый актив"""
        return WalletAsset()

    @staticmethod
    def save(asset: WalletAsset) -> None:
        if not asset.id:
            db.session.add(asset)
        db.session.commit()

    @staticmethod
    def delete(wallet: WalletAsset) -> None:
        db.session.delete(wallet)
        db.session.commit()
