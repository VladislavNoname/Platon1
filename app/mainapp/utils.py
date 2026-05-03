import logging
import requests
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger('mainapp')

def log_event(user, event):
    logger.info(f'Пользователь {user.email}: {event}')

def send_notification(user, message):
    # Email
    send_mail(
        'Уведомление от Platon',
        message,
        'noreply@platon.ru',
        [user.email],
        fail_silently=True
    )
    # Telegram (если настроен)
    if user.telegram_id:
        try:
            requests.post(f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage', json={
                'chat_id': user.telegram_id,
                'text': message
            })
        except Exception:
            pass