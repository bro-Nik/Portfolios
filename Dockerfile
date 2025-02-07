FROM python:slim
WORKDIR /app
COPY requirements.txt /app
RUN pip3 install --upgrade pip -r requirements.txt
COPY . /app
ENV FLASK_APP start.py
EXPOSE 5000
