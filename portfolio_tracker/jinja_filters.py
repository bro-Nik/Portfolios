from portfolio_tracker.app import app


def smart_int(number):
    ''' Float без точки, если оно целое '''
    if not number:
        return 0
    elif int(number) == number:
        return int(number)
    else:
        return round(number, 2)

app.add_template_filter(smart_int)


def smart_round(number):
    ''' Окрушление зависимое от величины числа для Jinja '''
    if not number:
        return 0
    try:
        number = float(number)
        if number >= 100:
            number = round(number, 1)
        elif number >= 10:
            number = round(number, 2)
        elif number >= 1:
            number = round(number, 3)
        elif number >= 0.1:
            number = round(number, 5)
        elif number >= 0.0001:
            number = round(number, 7)

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
