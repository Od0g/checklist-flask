from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user, login_required
from .models import db, User, Sector, ChecklistTemplate, ChecklistItemTemplate, ChecklistInstance, ChecklistItemResponse
from .forms import LoginForm, RegistrationForm, SectorForm, ChecklistTemplateForm, ChecklistItemForm
from functools import wraps
from flask import abort
import qrcode
import io
from flask import send_file
import base64
import uuid
import os
from config import basedir # Importe o 'basedir' do seu config.py
from .email import send_email




bp = Blueprint('main', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Administrador':
            abort(403) # Proibido o acesso
        return f(*args, **kwargs)
    return decorated_function

def leader_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or (current_user.role not in ['Líder', 'Administrador']):
            abort(403) # Proibido
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@bp.route('/index')
@login_required # Protege a página inicial, exigindo login
def index():
    return render_template('index.html', title='Página Inicial')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Email ou senha inválidos', 'danger')
            return redirect(url_for('main.login'))
        
        login_user(user, remember=form.remember.data)
        flash('Login realizado com sucesso!', 'success')
        return redirect(url_for('main.index'))
        
    return render_template('login.html', title='Login', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role='Operador') # Padrão
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Sua conta foi criada! Agora você pode fazer o login.', 'success')
        return redirect(url_for('main.login'))
        
    return render_template('register.html', title='Registro', form=form)

# --- ROTAS DO PAINEL DE ADMINISTRAÇÃO ---

@bp.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin/admin_dashboard.html', title='Painel do Admin')

@bp.route('/admin/sectors')
@login_required
@admin_required
def list_sectors():
    sectors = Sector.query.all()
    return render_template('admin/sectors.html', sectors=sectors, title='Gerenciar Setores')

@bp.route('/admin/sector/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_sector():
    form = SectorForm()
    if form.validate_on_submit():
        sector = Sector(name=form.name.data, description=form.description.data)
        db.session.add(sector)
        db.session.commit()
        flash('Setor criado com sucesso!', 'success')
        return redirect(url_for('main.list_sectors'))
    return render_template('admin/sector_form.html', form=form, title='Novo Setor')

@bp.route('/admin/sector/<int:sector_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_sector(sector_id):
    sector = Sector.query.get_or_404(sector_id)
    form = SectorForm(obj=sector)
    if form.validate_on_submit():
        sector.name = form.name.data
        sector.description = form.description.data
        db.session.commit()
        flash('Setor atualizado com sucesso!', 'success')
        return redirect(url_for('main.list_sectors'))
    return render_template('admin/sector_form.html', form=form, title='Editar Setor')

@bp.route('/admin/sector/<int:sector_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_sector(sector_id):
    sector = Sector.query.get_or_404(sector_id)
    db.session.delete(sector)
    db.session.commit()
    flash('Setor excluído com sucesso!', 'success')
    return redirect(url_for('main.list_sectors'))

# --- ROTAS PARA GERENCIAR MODELOS DE CHECKLIST ---

@bp.route('/admin/checklists')
@login_required
@admin_required
def list_checklists():
    templates = ChecklistTemplate.query.all()
    return render_template('admin/checklists.html', templates=templates, title='Modelos de Checklist')

@bp.route('/admin/checklist/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_checklist():
    form = ChecklistTemplateForm()
    # Popula as opções do campo 'sector' com os setores cadastrados
    form.sector.choices = [(s.id, s.name) for s in Sector.query.order_by('name').all()]

    if form.validate_on_submit():
        template = ChecklistTemplate(
            title=form.title.data,
            description=form.description.data,
            sector_id=form.sector.data
        )
        db.session.add(template)
        db.session.commit()
        flash('Modelo de checklist criado com sucesso!', 'success')
        # Redireciona para a página de detalhes para adicionar itens
        return redirect(url_for('main.checklist_detail', template_id=template.id))
        
    return render_template('admin/checklist_template_form.html', form=form, title='Novo Modelo de Checklist')

@bp.route('/admin/checklist/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def checklist_detail(template_id):
    template = ChecklistTemplate.query.get_or_404(template_id)
    item_form = ChecklistItemForm()

    if item_form.validate_on_submit():
        new_item = ChecklistItemTemplate(
            question=item_form.question.data,
            template_id=template.id
        )
        db.session.add(new_item)
        db.session.commit()
        flash('Item adicionado com sucesso!', 'success')
        item_form.question.data = '' # Limpa o campo após adicionar
    
    return render_template('admin/checklist_detail.html', template=template, item_form=item_form, title=template.title)

@bp.route('/admin/checklist/item/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_checklist_item(item_id):
    item = ChecklistItemTemplate.query.get_or_404(item_id)
    template_id = item.template_id
    db.session.delete(item)
    db.session.commit()
    flash('Item removido com sucesso!', 'success')
    return redirect(url_for('main.checklist_detail', template_id=template_id))

@bp.route('/admin/checklist/<int:template_id>/qrcode')
@login_required
@admin_required
def generate_qrcode(template_id):
    # Linha ANTIGA: url_to_fill = url_for('main.index', _external=True)
    # Linha NOVA:
    url_to_fill = url_for('main.fill_checklist', template_id=template_id, _external=True)
    
    qr_img = qrcode.make(url_to_fill)
    
    buf = io.BytesIO()
    qr_img.save(buf)
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png')

# --- ROTAS DO OPERADOR ---

@bp.route('/checklist/fill/<int:template_id>', methods=['GET', 'POST'])
@login_required
def fill_checklist(template_id):
    template = ChecklistTemplate.query.get_or_404(template_id)

    if request.method == 'POST':
        # 1. Lógica para salvar a assinatura
        signature_data_url = request.form.get('signature')
        signature_filename = None
        if signature_data_url:
            # Decodifica a imagem base64
            header, encoded = signature_data_url.split(",", 1)
            data = base64.b64decode(encoded)
            
            # Gera um nome de arquivo único
            signature_filename = f"{uuid.uuid4()}.png"
            signatures_dir = os.path.join(basedir, 'app', 'static', 'signatures')
            os.makedirs(signatures_dir, exist_ok=True) # Cria a pasta se não existir
            
            with open(os.path.join(signatures_dir, signature_filename), "wb") as f:
                f.write(data)

        # 2. Cria a instância principal do checklist preenchido
        instance = ChecklistInstance(
            status='Pendente',
            operator_id=current_user.id,
            template_id=template.id,
            operator_signature=signature_filename # Salva o nome do arquivo
        )
        db.session.add(instance)
        db.session.flush() # Usa flush para obter o ID da instância antes do commit final

        # 3. Itera sobre os itens do formulário para salvar as respostas
        for item in template.items:
            response_value = request.form.get(f'item_{item.id}_response')
            comment_value = request.form.get(f'item_{item.id}_comment')
            
            response = ChecklistItemResponse(
                response=response_value,
                comment=comment_value,
                instance_id=instance.id,
                item_template_id=item.id
            )
            db.session.add(response)

        # --- LÓGICA DE NOTIFICAÇÃO ---
        # Encontra os líderes associados ao setor do checklist
        leaders = template.sector.leaders
        if leaders:
            leader_emails = [leader.email for leader in leaders]
            # (URL de aprovação será criada no próximo passo, por enquanto usamos um placeholder)
            approval_url = url_for('main.review_checklist', instance_id=instance.id, _external=True)

            send_email(
                subject=f'Novo Checklist para Aprovação: {template.title}',
                sender=current_app.config['ADMINS'][0],
                recipients=leader_emails,
                template='email/new_checklist_notification',
                instance=instance,
                approval_url=approval_url
            )
            flash('Checklist enviado e líder notificado por e-mail!', 'success')
        else:
            flash('Checklist enviado com sucesso! (Aviso: Nenhum líder configurado para este setor para receber notificação.)', 'warning')
        
        return redirect(url_for('main.index'))

    return render_template('fill_checklist.html', template=template, title='Preencher Checklist')

    # Se for um request GET, apenas exibe a página
    return render_template('fill_checklist.html', template=template, title='Preencher Checklist')

@bp.route('/leader/dashboard')
@login_required
@leader_required
def leader_dashboard():
    # Pega os IDs dos setores que o líder atual gerencia
    managed_sectors_ids = [s.id for s in current_user.sectors]
    
    # Encontra todos os templates de checklist desses setores
    checklist_templates_ids = [t.id for t in ChecklistTemplate.query.filter(ChecklistTemplate.sector_id.in_(managed_sectors_ids)).all()]

    # Filtra as instâncias pendentes que correspondem a esses templates
    pending_checklists = ChecklistInstance.query.filter(
        ChecklistInstance.template_id.in_(checklist_templates_ids),
        ChecklistInstance.status == 'Pendente'
    ).order_by(ChecklistInstance.submission_date.desc()).all()

    return render_template('leader/leader_dashboard.html', checklists=pending_checklists, title='Painel do Líder')

@bp.route('/leader/checklist/<intinstance_id>/review', methods=['GET', 'POST'])
@login_required
@leader_required
def review_checklist(instance_id):
    instance = ChecklistInstance.query.get_or_404(instance_id)

    # Verificação de segurança: O líder pode revisar este checklist?
    if instance.template.sector not in current_user.sectors and current_user.role != 'Administrador':
        abort(403)

    if request.method == 'POST':
        action = request.form.get('action') # 'Aprovar' ou 'Reprovar'
        
        # Salva a assinatura do líder
        signature_data_url = request.form.get('signature')
        if signature_data_url:
            header, encoded = signature_data_url.split(",", 1)
            data = base64.b64decode(encoded)
            signature_filename = f"{uuid.uuid4()}.png"
            signatures_dir = os.path.join(basedir, 'app', 'static', 'signatures')
            os.makedirs(signatures_dir, exist_ok=True)
            with open(os.path.join(signatures_dir, signature_filename), "wb") as f:
                f.write(data)
            instance.leader_signature = signature_filename

        instance.status = action # 'Aprovado' ou 'Reprovado'
        instance.approval_date = datetime.utcnow()
        instance.leader_id = current_user.id
        
        db.session.commit()
        flash(f'Checklist {action.lower()} com sucesso!', 'success')
        return redirect(url_for('main.leader_dashboard'))

    return render_template('leader/review_checklist.html', instance=instance, title='Revisar Checklist')