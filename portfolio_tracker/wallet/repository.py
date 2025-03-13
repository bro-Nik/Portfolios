from __future__ import annotations

from portfolio_tracker.repository import DefaultRepository
from portfolio_tracker.wallet.models import Wallet, WalletAsset


class WalletRepository(DefaultRepository):
    model = Wallet


class WalletAssetRepository(DefaultRepository):
    model = WalletAsset
