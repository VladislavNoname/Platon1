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