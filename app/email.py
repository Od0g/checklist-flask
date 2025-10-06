from flask import current_app, render_template
from flask_mail import Message
from app import mail # Importa a instância do mail de __init__.py
from threading import Thread

# Função para enviar e-mails em uma thread separada (para não travar a aplicação)
def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, template, **kwargs):
    app = current_app._get_current_object()
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.html = render_template(template + '.html', **kwargs)
    Thread(target=send_async_email, args=(app, msg)).start()