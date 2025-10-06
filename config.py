import os

# Pega o caminho absoluto do diretório onde o arquivo config.py está
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Chave secreta para proteger a aplicação contra ataques (CSRF)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-secreta-muito-dificil-de-adivinhar'

    # Configuração do banco de dados SQLAlchemy
    # Usa SQLite, que cria um arquivo 'app.db' na raiz do projeto
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')

    # Desativa um recurso do SQLAlchemy que não usaremos, para economizar recursos
    SQLALCHEMY_TRACK_MODIFICATIONS = False

        # Configurações do Flask-Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.googlemail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') # Seu e-mail do Gmail
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') # Sua Senha de App de 16 dígitos
    
    # E-mail do administrador que enviará as notificações
    ADMINS = ['seu-email-de-admin@example.com']