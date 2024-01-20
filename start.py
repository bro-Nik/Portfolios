from portfolio_tracker.app import create_app, init_celery, redis

app = create_app()
celery = init_celery(app)

# Delete old tasks
keys = redis.keys('*task*')
if keys:
    redis.delete(*keys)
