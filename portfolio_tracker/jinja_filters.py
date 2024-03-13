import time
from datetime import datetime, timedelta
from typing import Tuple

from babel.dates import format_datetime
from flask import Blueprint
from flask_babel import Locale
from flask_login import current_user


bp = Blueprint('jinja_filters', __name__)


def smart_int(number: int | float) -> int | float:
    """ Float без точки, если оно целое """
    try:
        int_num = int(number)
        return int_num if int_num == number else number
    except TypeError:  # строка не является float / int
        return 0


bp.add_app_template_filter(smart_int)


def smart_round(num: int | float | None, percent: int = 0) -> int | float:
    """ Округление зависимое от величины числа для Jinja """
    if not num:
        return 0
    if not percent:
        return num

    try:
        num_abs = abs(num)
        margin_of_error = num_abs * percent / 100
        for accuracy in range(0, 10):
            if abs(num_abs - round(num_abs, accuracy)) <= margin_of_error:
                return round(num, accuracy)
        return num

    except TypeError:  # строка не является float / int
        return 0


bp.add_app_template_filter(smart_round)


def number_group(number: int | float) -> str:
    """ Разделитель тысяных для Jinja """
    return (long_number(number) if (0 < number < 0.0005)
            else '{:,}'.format(number).replace(',', ' '))


bp.add_app_template_filter(number_group)


def long_number(number: int | float) -> str:
    return ('{:.18f}'.format(number).rstrip('0') if number < 0.0005
            else str(number))


bp.add_app_template_filter(long_number)


def currency_price(num: int | float, currency: str = '', default: str = '',
                   round_per: int = 0) -> str:
    if not num and default:
        return default

    num = smart_round(num, round_per)

    if not currency:
        currency = current_user.currency
        num *= 1 / current_user.currency_ticker.price
    else:
        currency += ' '  # для разделения
    return currency_format(num, currency, currency_frac(num))


def currency_quantity(num: int | float, currency: str = '', default: str = '',
                      round_per: int = 0) -> str:
    if not num and default:
        return default

    num = smart_round(num, round_per)
    if num == int(num):
        num = int(num)

    if not currency:
        currency = current_user.currency

    return f'{num} {currency.upper()}'


def currency_frac(num: int | float) -> Tuple:

    if num == int(num):
        force_frac = (0, 0)
    elif num == round(num, 1):
        force_frac = (1, 1)
    else:
        s = str(long_number(num))
        length = len(s[s.index('.') + 1:])
        force_frac = (length, length)

    return force_frac


def currency_format(num: int | float, currency, force_frac) -> str:
    locale = Locale.parse(current_user.locale)
    pattern = locale.currency_formats['standard']

    return pattern.apply(num, locale, currency=currency.upper(),
                         force_frac=force_frac)


bp.add_app_template_filter(currency_price)
bp.add_app_template_filter(currency_quantity)


def user_datetime(date: datetime, not_format: bool = False) -> str:
    locale = current_user.locale.upper()
    date = date - timedelta(seconds=time.timezone)
    if not_format:
        return date.isoformat(sep='T', timespec='minutes')
    return format_datetime(date, locale=locale)


bp.add_app_template_filter(user_datetime)
