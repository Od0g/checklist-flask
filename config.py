import os

# Pega o caminho absoluto do diretório onde o arquivo config.py está
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Chave secreta para proteger a aplicação contra ataques (CSRF)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'Gust@101203'
    
    # --- MODIFICAÇÃO AQUI ---
    # Render irá fornecer uma variável de ambiente chamada DATABASE_URL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        # Se estiver no Render, use o PostgreSQL
        SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    else:
        # Se estiver rodando localmente, use o SQLite
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

        # Configurações do Flask-Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.googlemail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') # Seu e-mail do Gmail
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') # Sua Senha de App de 16 dígitos
    
    # E-mail do administrador que enviará as notificações
    ADMINS = ['seu-email-de-admin@example.com']