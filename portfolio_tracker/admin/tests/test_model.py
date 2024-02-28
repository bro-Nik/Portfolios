from datetime import datetime, timedelta
import unittest

from tests import app, db, Api, Stream


class TestApiModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_update_streams(self):
        pass

    def test_nearest_stream(self):
        # Api
        api = Api(name='cr', need_key=False, minute_limit=5, month_limit=10000)

        # Потоки
        stream1 = Stream(active=False,
                            next_call=datetime(2024, 10, 6, 10, 11, 00))
        stream2 = Stream(active=False,
                            next_call=datetime(2024, 10, 5, 10, 14, 00))
        stream3 = Stream(active=False, next_call=None)

        api.streams = [stream1, stream2, stream3]
        db.session.add(api)
        db.session.commit()

        # Нет активных
        self.assertEqual(api.nearest_stream(), None)

        # Отдавать если нет next_call
        stream1.active = True
        stream2.active = True
        stream3.active = True
        self.assertEqual(api.nearest_stream(), stream3)

        # Отдавать ближайший по времени поток
        stream3.next_call = datetime(2024, 10, 5, 10, 17, 00)
        self.assertEqual(api.nearest_stream(), stream2)

    # def test_nearest_stream(self):
    #     # Api
    #     api = Api(name='crypto', need_key=False, minute_limit=5,
    #               month_limit=10000)
    #
    #     # Потоки
    #     stream1 = ApiStream(
    #         month_calls=100, minute_calls=5, active=False,
    #         first_call_minute=datetime(2024, 10, 5, 10, 15, 00),
    #         first_call_month=datetime(2024, 10, 1, 10, 15, 00),
    #         next_call=datetime(2024, 10, 5, 10, 16, 00)
    #     )
    #     stream2 = ApiStream(
    #         month_calls=1000, minute_calls=5, active=False,
    #         first_call_minute=datetime(2024, 10, 5, 10, 13, 00),
    #         first_call_month=datetime(2024, 10, 1, 10, 19, 00),
    #         next_call=datetime(2024, 10, 5, 10, 14, 00)
    #     )
    #     stream3 = ApiStream(
    #         month_calls=2000, minute_calls=3, active=False,
    #         first_call_minute=datetime(2024, 10, 5, 10, 16, 00),
    #         first_call_month=datetime(2024, 10, 1, 10, 15, 00),
    #         next_call=datetime(2024, 10, 5, 10, 17, 00)
    #     )
    #
    #     api.streams = [stream1, stream2, stream3]
    #     db.session.add(api)
    #     db.session.commit()
    #
    #     # Нет активных
    #     self.assertEqual(api.nearest_stream(), None)
    #
    #     #
    #     stream1.active = True
    #     stream3.active = True
    #     # self.assertEqual(api.nearest_stream(), stream2)


class TestApiStreamModel(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_new_call(self):
        # Api
        api = Api(name='cr', need_key=False, minute_limit=5, month_limit=10000)

        now = datetime.now()

        # Поток
        stream = Stream(month_calls=100, minute_calls=4)

        api.streams = [stream]
        db.session.add(api)
        db.session.commit()

        # Прошло более минуты с первого запроса - обнуляем
        stream.first_call_minute = now - timedelta(minutes=1)
        stream.new_call()
        self.assertEqual(stream.minute_calls, 1)
        self.assertTrue((now - stream.first_call_minute).total_seconds() < 1)

        # Прошло более месяца с первого запроса - обнуляем
        stream.first_call_month = now - timedelta(days=31)
        stream.new_call()
        self.assertEqual(stream.month_calls, 1)
        self.assertTrue((now - stream.first_call_month).total_seconds() < 1)

        # Не записываем следующий вызов пока не достигнут минутный лимит
        stream.minute_calls = 2
        stream.next_call = now
        stream.new_call()
        self.assertEqual(stream.next_call, now)

        # Записываем следующий вызов по достижении минутного лимита
        stream.minute_calls = 5
        stream.new_call()
        self.assertTrue((now - stream.next_call + timedelta(minutes=1)).total_seconds() < 1)

        # Записываем следующий вызов по достижении месячного лимита
        stream.next_call = now
        stream.month_calls = 10000
        stream.new_call()
        self.assertTrue((now - stream.next_call + timedelta(days=31)).total_seconds() < 1)
