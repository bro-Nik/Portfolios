from datetime import datetime
import decimal
from babel.numbers import format_number, format_decimal, format_percent, parse_decimal, format_currency
from babel.dates import format_datetime, format_date
from flask_babel import Locale
from flask_login import current_user
from portfolio_tracker.app import app
from portfolio_tracker.general_functions import get_price_list


def smart_int(number):
    ''' Float без точки, если оно целое '''
    if not number:
        return 0
    elif int(number) == number:
        return int(number)
    return number

app.add_template_filter(smart_int)


def smart_round(number):
    ''' Окрушление зависимое от величины числа для Jinja '''
    if not number:
        return 0
    try:
        number = float(number)
        if number >= 1000:
            number = int(number)
        elif number >= 100:
            number = round(number, 1)
        elif number >= 10:
            number = round(number, 2)
        elif number >= 1:
            number = round(number, 3)
        elif number >= 0.1:
            number = round(number, 5)
        elif number >= 0.0001:
            number = round(number, 7)
        elif -0.000000000000001 < number < 0.000000000000001:
            number = 0


        if int(number) == number:
            return int(number)
        else:
            return number
    except:  # строка не является float / int
        return 0


app.add_template_filter(smart_round)


def number_group(number):
    ''' Разделитель тысяных для Jinja '''
    return long_number(number) if (0 < number < 0.0005) else '{:,}'.format(number).replace(',', ' ')


app.add_template_filter(number_group)


def long_number(number):
    ''' для Jinja '''
    return '{:.18f}'.format(number).rstrip('0') if number < 0.0005 else number


app.add_template_filter(long_number)


def user_currency(number):
    number = smart_round(number)
    currency = current_user.currency
    locale = current_user.locale
    price_list = get_price_list()
    number *= price_list.get('cu-' + currency)
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
        s = str(number)
        length = len(s[s.index('.') + 1:])
        force_frac = (length, length)
    return pattern.apply(number, locale, currency=currency, force_frac=force_frac)

app.add_template_filter(user_currency)


def other_currency(number, currency):
    number = smart_round(number)
    locale = Locale.parse(current_user.locale)
    pattern = locale.currency_formats['standard']
    force_frac = None
    if number == int(number):
        force_frac = (0, 0)
    elif number == round(number, 1):
        force_frac = (1, 1)
    elif number < 1:
        s = str(number)
        length = len(s[s.index('.') + 1:])
        force_frac = (length, length)
    return pattern.apply(number, locale, currency=currency.upper(), force_frac=force_frac)

app.add_template_filter(other_currency)


def user_date(date):
    if type(date) == str:
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except:
            return date
    locale = current_user.locale.upper()
    
    return format_date(date, locale=locale)

app.add_template_filter(user_date)


def ticker_currency(number):
    locale = current_user.locale
    
    return format_decimal(number, locale=locale)

app.add_template_filter(ticker_currency)
