from flask import Flask
from config import Config
from .models import db
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail 



migrate = Migrate()
login_manager = LoginManager()



# Corrija esta linha para incluir o nome do Blueprint
login_manager.login_view = 'main.login'

mail = Mail() # Crie a instância do Mail

def create_app(config_class=Config):
    # Cria a instância da aplicação Flask
    app = Flask(__name__)
    # Carrega as configurações a partir da classe Config
    app.config.from_object(config_class)

    mail.init_app(app)

    # Inicializa as extensões com a aplicação
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Importa os modelos aqui para garantir que eles sejam registrados com o SQLAlchemy
    from . import models

    # Importa e registra as rotas (ainda vamos criá-las)
    from . import routes
    app.register_blueprint(routes.bp) # Usaremos um Blueprint para organizar as rotas

    # Configura o carregador de usuário para o Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    return app