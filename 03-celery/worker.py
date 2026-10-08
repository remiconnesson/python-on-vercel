# Subscriber entrypoint, referenced by [[tool.vercel.subscribers]] in pyproject.toml.
# Importing `tasks` registers the tasks on the Celery app. Vercel runs this as a
# private function that only Vercel Queues can invoke: one task per invocation,
# scaled out by Queues instead of by a long-lived `celery worker` process.
from tasks import app

__all__ = ["app"]
