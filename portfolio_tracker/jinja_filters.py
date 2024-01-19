import time
from datetime import datetime, timedelta
import math

from babel.dates import format_datetime
from flask import Blueprint
from flask_babel import Locale
from flask_login import current_user


bp = Blueprint('jinja_filters', __name__)


def smart_int(number: int | float | None) -> int | float:
    """ Float без точки, если оно целое """
    if not number:
        return 0

    try:
        int_num = int(number)
        return int_num if int_num == number else number
    except TypeError:  # строка не является float / int
        return 0


bp.add_app_template_filter(smart_int)


def smart_round(number: int | float | None) -> int | float:
    """ Округление зависимое от величины числа для Jinja """
    if not number:
        return 0

    try:
        abs_number = abs(number)
        if abs_number >= 1000:
            number = int(number)
        elif abs_number >= 100:
            number = round(number, 1)
        elif abs_number >= 10:
            number = round(number, 2)
        else:
            dist = int(math.log10(abs_number))
            if dist:
                number = round(number, abs(dist) + 2)
        return number

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


def user_currency(number: int | float, param: str = '') -> str:
    currency = current_user.currency
    locale = current_user.locale

    price_currency_to_usd = 1 / current_user.currency_ticker.price
    number *= price_currency_to_usd

    # round
    if param == 'big':
        if number - round(number) < price_currency_to_usd:
            number = round(number)
        elif number - round(number, 1) < price_currency_to_usd:
            number = round(number, 1)

    currency = currency.upper()

    # for integer
    locale = Locale.parse(locale)
    pattern = locale.currency_formats['standard']
    force_frac = None
    if number == int(number):
        force_frac = (0, 0)
    elif number == round(number, 1):
        force_frac = (1, 1)
    elif number < 1:
        s = str(long_number(number))
        length = len(s[s.index('.') + 1:])
        force_frac = (length, length)
    return pattern.apply(number, locale, currency=currency,
                         force_frac=force_frac)


bp.add_app_template_filter(user_currency)


def other_currency(number: int | float, currency: str, param: str = '') -> str:
    # round
    if param == 'big':
        if number - int(number) < 1:
            number = int(number)
        elif number - round(number, 1) < 1:
            number = round(number, 1)

    locale = Locale.parse(current_user.locale)
    pattern = locale.currency_formats['standard']

    if number == int(number):
        frac = (0, 0)
    elif number == round(number, 1):
        frac = (1, 1)
    else:
        s = str(long_number(number))
        length = len(s[s.index('.') + 1:])
        frac = (length, length)
    return pattern.apply(number, locale, currency=currency.upper(),
                         force_frac=frac)


bp.add_app_template_filter(other_currency)


def user_datetime(date: datetime, not_format: bool = False) -> str:
    locale = current_user.locale.upper()
    date = date - timedelta(seconds=time.timezone)
    if not_format:
        return date.isoformat(sep='T', timespec='minutes')
    return format_datetime(date, locale=locale)


bp.add_app_template_filter(user_datetime)
