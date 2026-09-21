from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def send_verification_email(user) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    url = settings.SITE_URL + reverse("accounts:verify_email", args=[uid, token])
    body = render_to_string("emails/verify_email.txt", {"user": user, "url": url})
    send_mail("Confirmă adresa de email · dictare.ro", body, None, [user.email])
