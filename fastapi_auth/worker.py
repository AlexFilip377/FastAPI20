from celery import Celery
from fastapi_auth.config import get_settings

settings = get_settings()


REDIS_URL = settings.REDIS_URL

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

@celery_app.task
def send_email_task(email: str):
    import time
    time.sleep(5)
    print(f"Email sent to {email}")
    return f"Email успешно отправлен на {email}"