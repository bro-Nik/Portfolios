import time
from datetime import datetime, timedelta

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


def smart_round(num: int | float | None, margin_of_error: int | float = 0
                ) -> int | float:
    """ Округление зависимое от величины числа для Jinja """
    if not num:
        return 0
    if not margin_of_error:
        return num

    try:
        num_abs = abs(num)
        for accuracy in range(0, 10):
            if abs(num_abs - round(num_abs, accuracy)) <= margin_of_error:
                return round(num, accuracy)
        return num

    except TypeError:  # строка не является float / int
        return 0


def number_group(number: int | float) -> str:
    """ Разделитель тысяных для Jinja """
    return (long_number(number) if (0 < number < 0.0005)
            else '{:,}'.format(number).replace(',', ' '))


def long_number(number: int | float) -> str:
    return ('{:.18f}'.format(number).rstrip('0') if number < 0.0005
            else str(number))


def currency_price(num: int | float, currency: str = '', default: str = '',
                   round_per: int = 0, round_to: str = '') -> str:
    if not currency:
        currency = current_user.currency
        num *= 1 / current_user.currency_ticker.price
    else:
        currency += ' '  # для разделения

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

    locale = Locale.parse(current_user.locale)
    p = locale.currency_formats['standard']
    # rez = p.apply(num, locale, currency=currency.upper(), force_frac=frac)
    # return f'{"~" if round_per or round_to else ""}{rez}'
    return p.apply(num, locale, currency=currency.upper(), force_frac=frac)


def currency_round(num: int | float, round_per: int = 0, round_to: str = ''
                   ) -> int | float:
    margin_of_error = 0
    if round_per:
        margin_of_error = abs(num * round_per / 100)
    elif round_to:
        if round_to == 'usd':
            margin_of_error = 1 / current_user.currency_ticker.price
        else:
            margin_of_error = 1 / float(round_to)

    return smart_round(num, margin_of_error)


def currency_quantity(num: int | float, currency: str = '', default: str = '',
                      round_per: int = 0, round_to: str = '') -> str:
    num = currency_round(num, round_per=round_per, round_to=round_to)
    if not num and default:
        return default

    if not currency:
        currency = current_user.currency

    return f'{long_number(smart_int(num))} {currency.upper()}'


def user_datetime(date: datetime, not_format: bool = False) -> str:
    locale = current_user.locale
    date = date - timedelta(seconds=time.timezone)
    if not_format:
        date = date.replace(tzinfo=None)
        return date.isoformat(sep='T', timespec='minutes')
    return format_datetime(date, 'short', locale=locale)


bp.add_app_template_filter(smart_int)
bp.add_app_template_filter(smart_round)
bp.add_app_template_filter(long_number)
bp.add_app_template_filter(number_group)
bp.add_app_template_filter(currency_price)
bp.add_app_template_filter(currency_quantity)
bp.add_app_template_filter(user_datetime)
