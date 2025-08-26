# opustools/authentication/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

@shared_task
def send_password_reset_email(user_id, uid, token):
    """
    A Celery task to send a password reset email asynchronously.
    """
    try:
        user = User.objects.get(pk=user_id)
        frontend_url = 'https://opustools.xyz' # Your frontend domain
        reset_url = f"{frontend_url}/password/reset/confirm/{uid}/{token}/"

        subject = 'Reset Your Password for OpusTools'
        message = (
            f"Hello {user.username},\n\n"
            f"You are receiving this email because you requested a password reset for your account at OpusTools.\n\n"
            f"Please go to the following page and choose a new password:\n"
            f"{reset_url}\n\n"
            f"If you did not request a password reset, please ignore this email.\n\n"
            f"Thanks,\nThe OpusTools Team"
        )

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except User.DoesNotExist:
        # Handle case where user might be deleted before task runs
        pass