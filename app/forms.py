from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField 
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from .models import User, Sector

class RegistrationForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Registrar')

    # Validador customizado para verificar se o username já existe
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Este nome de usuário já está em uso. Por favor, escolha outro.')

    # Validador customizado para verificar se o e-mail já existe
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este e-mail já está em uso. Por favor, escolha outro.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember = BooleanField('Lembrar-me')
    submit = SubmitField('Login')

class SectorForm(FlaskForm):
    name = StringField('Nome do Setor', validators=[DataRequired(), Length(min=3, max=100)])
    description = StringField('Descrição (Opcional)', validators=[Length(max=255)])
    submit = SubmitField('Salvar')

class ChecklistTemplateForm(FlaskForm):
    title = StringField('Título do Checklist', validators=[DataRequired(), Length(max=150)])
    description = StringField('Descrição (Opcional)')
    # Este campo será populado dinamicamente com os setores do banco de dados
    sector = SelectField('Setor', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar Modelo')

class ChecklistItemForm(FlaskForm):
    question = StringField('Texto do Item', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Adicionar Item')