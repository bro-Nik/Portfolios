from portfolio_tracker.app import create_app, init_celery, celery, redis

app = create_app()
init_celery(app, celery)

# Delete old tasks
keys = redis.keys('*task*')
if keys:
    redis.delete(*keys)
