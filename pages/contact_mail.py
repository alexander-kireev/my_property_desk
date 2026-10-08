"""Deliver public messages through the application's configured Django email backend."""

from django.conf import settings
from django.core.mail import EmailMessage


def send_problem_report(data):
    details = [
        "Problem report from the My Property Desk website",
        "",
        f"Area: {data['area'] or 'Not specified'}",
        f"Reply address: {data['email'] or 'Anonymous'}",
        "",
        "What happened:",
        data["description"],
        "",
        "Steps to repeat:",
        data["steps"] or "Not provided",
    ]
    message = EmailMessage(
        subject="My Property Desk problem report",
        body="\n".join(details),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.PMS_CONTACT_EMAIL],
        reply_to=[data["email"]] if data["email"] else None,
    )
    for screenshot in data["screenshots"]:
        message.attach(screenshot.name, screenshot.read(), screenshot.content_type)
    return message.send(fail_silently=False)


def send_public_message(data):
    message = EmailMessage(
        subject=f"My Property Desk: {data['topic']}",
        body="\n".join(
            [
                f"Reply address: {data['email'] or 'Anonymous'}",
                "",
                data["body"],
            ]
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.PMS_CONTACT_EMAIL],
        reply_to=[data["email"]] if data["email"] else None,
    )
    return message.send(fail_silently=False)
