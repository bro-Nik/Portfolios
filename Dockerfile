# Выкачиваем из dockerhub образ с python
FROM python:slim
# Устанавливаем рабочую директорию для проекта в контейнере
WORKDIR /app
# Скачиваем/обновляем необходимые библиотеки для проекта
COPY requirements.txt /app
RUN pip3 install --upgrade pip -r requirements.txt
# RUN pip3 install gunicorn
# |ВАЖНЫЙ МОМЕНТ| копируем содержимое папки, где находится Dockerfile,
# в рабочую директорию контейнера
COPY . /app
ENV FLASK_APP start.py
# Устанавливаем порт, который будет использоваться для сервера
EXPOSE 5000
