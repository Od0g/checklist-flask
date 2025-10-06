from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash




db = SQLAlchemy()

# Tabela de associação para a relação muitos-para-muitos entre Líderes e Setores
leader_sector_association = db.Table('leader_sector',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('sector_id', db.Integer, db.ForeignKey('sector.id'))
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256)) # Aumentamos o tamanho para o hash
    role = db.Column(db.String(20), nullable=False)  # 'Administrador', 'Líder', 'Operador'

    sectors = db.relationship('Sector', secondary=leader_sector_association, back_populates='leaders')

    # Novo método para definir a senha
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Novo método para verificar a senha
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Sector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    
    # Relação: Um setor pode ter vários líderes
    leaders = db.relationship('User', secondary=leader_sector_association, back_populates='sectors')
    checklist_templates = db.relationship('ChecklistTemplate', backref='sector', lazy=True)

    def __repr__(self):
        return f'<Sector {self.name}>'

class ChecklistTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=False)
    
    items = db.relationship('ChecklistItemTemplate', backref='template', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ChecklistTemplate {self.title}>'

class ChecklistItemTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('checklist_template.id'), nullable=False)

    def __repr__(self):
        return f'<ChecklistItemTemplate {self.question[:30]}>'

class ChecklistInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(30), default='Pendente') # Pendente, Aprovado, Reprovado
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    approval_date = db.Column(db.DateTime)
    
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    template_id = db.Column(db.Integer, db.ForeignKey('checklist_template.id'))
    
    operator_signature = db.Column(db.String(255)) # Caminho para o arquivo da imagem da assinatura
    leader_signature = db.Column(db.String(255))
    
    # Relações
    operator = db.relationship('User', foreign_keys=[operator_id])
    leader = db.relationship('User', foreign_keys=[leader_id])
    template = db.relationship('ChecklistTemplate')
    responses = db.relationship('ChecklistItemResponse', backref='instance', lazy=True, cascade="all, delete-orphan")

class ChecklistItemResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    response = db.Column(db.String(20)) # Sim, Não, Parcial, NSP
    comment = db.Column(db.Text)
    photo_evidence = db.Column(db.String(255)) # Caminho para a foto
    
    instance_id = db.Column(db.Integer, db.ForeignKey('checklist_instance.id'), nullable=False)
    item_template_id = db.Column(db.Integer, db.ForeignKey('checklist_item_template.id'), nullable=False)
    
    item_template = db.relationship('ChecklistItemTemplate')