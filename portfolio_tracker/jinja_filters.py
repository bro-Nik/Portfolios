import time
from datetime import datetime, timedelta

from babel.dates import format_datetime
from flask import Blueprint, g
from flask_babel import Locale
from flask_login import current_user

from .general_functions import add_prefix
from .portfolio.repository import TickerRepository
from .user.services.ui import get_currency, get_locale


bp = Blueprint('jinja_filters', __name__)


def smart_round(num: int | float = 0, margin_of_error: int | float = 0
                ) -> int | float:
    """ Округление зависимое от величины числа для Jinja """
    try:
        # С дробной частью
        if margin_of_error:
            num_abs = abs(num)
            for accuracy in range(0, 10):
                if abs(num_abs - round(num_abs, accuracy)) <= margin_of_error:
                    num = round(num, accuracy)
                    break

        # Без дробной части
        num_abs = abs(num)
        if abs(num_abs - round(num_abs)) <= margin_of_error:
            num = round(num)

        return num

    except TypeError:  # строка не является float / int
        return 0


def long_number(n: int | float) -> str:
    return '{:.18f}'.format(n).rstrip('0') if 0 < abs(n) < 0.0005 else str(n)


def get_currency_ticker(u=current_user):
    currency_ticker = getattr(g, 'currency_ticker', None)
    if currency_ticker is None:
        if u.is_authenticated and u.type != 'demo' and u.currency:
            currency_ticker = u.currency_ticker
        else:
            currency_ticker = TickerRepository.get(add_prefix(get_currency(), 'currency'))

        g.currency_ticker = currency_ticker
    return currency_ticker


def currency_price(num: int | float, currency: str = '', default: str = '',
                   round_per: int = 0, round_to: str = '') -> str:
    currency_ticker = get_currency_ticker()
    locale = get_locale()

    if not currency:
        currency = get_currency()
        if num:
            num *= 1 / currency_ticker.price
    currency = currency.upper()

    num = currency_round(num, round_per=round_per, round_to=round_to)
    if not num and default:
        return default

    if num == int(num):
        frac = (0, 0)
    elif num == round(num, 1):
        frac = (1, 1)
    else:
        s = str(long_number(num))
        length = len(s[s.index('.') + 1:])
        frac = (length, length)

    locale = Locale.parse(locale)
    p = locale.currency_formats['standard']
    rez = str(p.apply(num, locale, currency=currency.upper(), force_frac=frac))

    # Разрыв, если у валюта пишется вначале и у нее нет символа
    if rez.startswith(currency):
        rez = rez.replace(currency, f'{currency} ')

    return rez


def currency_round(num: int | float, round_per: int = 0, round_to: str = ''
                   ) -> int | float:
    margin_of_error = 0
    currency_ticker = get_currency_ticker()
    if round_per:
        margin_of_error = abs(num * round_per / 100)
    elif round_to:
        if round_to == 'usd':
            margin_of_error = 1 / currency_ticker.price
        else:
            margin_of_error = 1 / float(round_to)

    return smart_round(num, margin_of_error)


def currency_quantity(num: int | float, currency: str = '', default: str = '',
                      round_per: int = 0, round_to: str = '') -> str:
    num = currency_round(num, round_per=round_per, round_to=round_to)
    if not num and default:
        return default

    if not currency:
        currency = get_currency()

    locale = get_locale()
    s = str(long_number(num))
    index = s.find('.')
    length = len(s[index + 1:]) if index >0 else 0
    frac = (length, length)

    locale = Locale.parse(locale)
    p = locale.currency_formats['standard']
    rez = str(p.apply(num, locale, currency=currency.upper(), force_frac=frac))

    # Разрыв, если у валюта пишется вначале и у нее нет символа
    if rez.startswith(currency):
        rez = rez.replace(currency, f'{currency} ')

    return rez


def user_datetime(date: datetime, not_format: bool = False) -> str:
    locale = get_locale()
    date = date - timedelta(seconds=time.timezone)
    if not_format:
        date = date.replace(tzinfo=None)
        return date.isoformat(sep='T', timespec='minutes')
    return format_datetime(date, 'short', locale=locale)


def percent(obj):
    percent = smart_round(getattr(obj, 'percent', 0))
    return f'{percent}%' if percent > 0 else '-'


def share_of(obj, parent_amount):
    if obj.amount <= 0 or parent_amount <= 0:
        return '-'
    num = smart_round(obj.amount / parent_amount * 100, 0.1)

    locale = get_locale()
    s = str(long_number(num))
    length = len(s[s.find('.'):])
    frac = (length, length)

    locale = Locale.parse(locale)
    p = locale.currency_formats['standard']
    rez = str(p.apply(num, locale, currency='%', force_frac=frac))
    return rez


def profit(obj):
    profit = currency_price(obj.profit, round_to='usd')
    percent_str = ''
    if obj.profit and obj.amount > 1:
        percent = abs(round(obj.profit / obj.amount * 100))
        percent_str = f' ({percent}%)' if percent else ''
    return f'{profit}{percent_str}' if profit else '-'


def color(obj):
    round_profit = round(obj.profit)
    if round_profit > 0:
        return 'text-green'
    if round_profit < 0:
        return 'text-red'


bp.add_app_template_filter(smart_round)
bp.add_app_template_filter(long_number)
bp.add_app_template_filter(currency_price)
bp.add_app_template_filter(currency_quantity)
bp.add_app_template_filter(user_datetime)
bp.add_app_template_filter(percent)
bp.add_app_template_filter(share_of)
bp.add_app_template_filter(profit)
bp.add_app_template_filter(color)
bp.add_app_template_filter(get_locale)
bp.add_app_template_filter(get_currency)
