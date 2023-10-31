from datetime import datetime, timedelta
import math
from babel.numbers import format_decimal
from babel.dates import format_date, format_datetime
from flask import current_app
from flask_babel import Locale
from flask_login import current_user
import time
# from portfolio_tracker.app import app
from portfolio_tracker.general_functions import get_price_list
from portfolio_tracker.main import bp


def smart_int(number):
    ''' Float без точки, если оно целое '''
    if not number:
        return 0
    elif int(number) == number:
        return int(number)
    return number

# current_app.add_template_filter(smart_int)
bp.add_app_template_filter(smart_int)


def smart_round(number):
    ''' Окрушление зависимое от величины числа для Jinja '''
    try:
        # number = float(number)
        abs_number = abs(number)
        if abs_number >= 1000:
            number = int(number)
        elif abs_number >= 100:
            number = round(number, 1)
        elif abs_number >= 10:
            number = round(number, 2)
        else:
            dist = int(math.log10(abs_number)) #number of zeros after decimal point
            if dist:
                number = (round(number, abs(dist) + 2))
        return number

    except:  # строка не является float / int
        return 0

bp.add_app_template_filter(smart_round)


# def big_round(number):
#     try:
#         abs_number = abs(number)
#         if abs_number >= 1000:
#             number = int(number)
#         elif abs_number >= 100:
#             number = round(number, 1)
#         elif abs_number >= 10:
#             number = round(number, 2)
#         else:
#             dist = int(math.log10(abs_number)) #number of zeros after decimal point
#             if dist:
#                 number = (round(number, abs(dist) + 2))
#         return number
#
#     except:  # строка не является float / int
#         return 0
#
# app.add_template_filter(smart_round)


def number_group(number):
    ''' Разделитель тысяных для Jinja '''
    return long_number(number) if (0 < number < 0.0005) else '{:,}'.format(number).replace(',', ' ')


bp.add_app_template_filter(number_group)


def long_number(number):
    ''' для Jinja '''
    return '{:.18f}'.format(number).rstrip('0') if number < 0.0005 else number


bp.add_app_template_filter(long_number)


def user_currency(number, param=None):
    currency = current_user.currency
    locale = current_user.locale
    price_list = get_price_list()
    price_currency_to_usd = price_list.get(current_app.config['CURRENCY_PREFIX'] + currency, 1)
    number *= price_currency_to_usd

    # round
    if param == 'big':
        if number - round(number) < price_currency_to_usd:
            number = round(number)
        elif number - round(number, 1) < price_currency_to_usd:
            number = round(number, 1)

    currency = currency.upper()

    # for integer
    # number = decimal.Decimal(number)
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
    return pattern.apply(number, locale, currency=currency, force_frac=force_frac)

bp.add_app_template_filter(user_currency)


def other_currency(number, currency, param=''):
    # round
    if param == 'big':
        if number - int(number) < 1:
            number = int(number)
        elif number - round(number, 1) < 1:
            number = round(number, 1)

    locale = Locale.parse(current_user.locale)
    pattern = locale.currency_formats['standard']
    force_frac = None
    if number == int(number):
        force_frac = (0, 0)
    elif number == round(number, 1):
        force_frac = (1, 1)
    # elif abs(number) < 1:
    else:
        s = str(long_number(number))
        length = len(s[s.index('.') + 1:])
        force_frac = (length, length)
    return pattern.apply(number, locale, currency=currency.upper(), force_frac=force_frac)

bp.add_app_template_filter(other_currency)


def user_datetime(date, not_format=False):
    locale = current_user.locale.upper()
    date = date - timedelta(seconds=time.timezone)
    if not_format:
        return date.isoformat(sep='T', timespec='minutes')
    return format_datetime(date, locale=locale)

bp.add_app_template_filter(user_datetime)


def ticker_currency(number):
    locale = current_user.locale
    
    return format_decimal(number, locale=locale)

bp.add_app_template_filter(ticker_currency)
