# app/routes.py (VERSÃO FINAL E CORRIGIDA)

import boto3
from flask import render_template, flash, redirect, url_for, request, Blueprint, abort, send_file, make_response, current_app, jsonify
from datetime import datetime
from flask_login import login_user, logout_user, current_user, login_required
from .models import db, User, Sector, ChecklistTemplate, ChecklistItemTemplate, ChecklistInstance, ChecklistItemResponse
from .forms import LoginForm, RegistrationForm, SectorForm, ChecklistTemplateForm, ChecklistItemForm, UserEditForm
from functools import wraps
import qrcode
import io
import base64
import uuid
import os
from werkzeug.utils import secure_filename
from .email import send_email
from weasyprint import HTML
from openpyxl import Workbook
from sqlalchemy import func, case

bp = Blueprint('main', __name__)

# --- DECORATORS ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Administrador':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def leader_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or (current_user.role not in ['Líder', 'Administrador']):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS PRINCIPAIS E DE AUTENTICAÇÃO ---
@bp.route('/')
@bp.route('/index')
@login_required
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
        user = User(username=form.username.data, email=form.email.data, role='Operador')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Sua conta foi criada! Agora você pode fazer o login.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Registro', form=form)

# --- ROTAS DO OPERADOR ---
@bp.route('/checklist/fill/<int:template_id>', methods=['GET', 'POST'])
@login_required
def fill_checklist(template_id):
    template = ChecklistTemplate.query.get_or_404(template_id)
    if request.method == 'POST':
        # 1. Salva Assinatura do Operador no S3
        s3_operator_signature_url = None
        signature_data_url = request.form.get('signature')
        if signature_data_url:
            header, encoded = signature_data_url.split(",", 1)
            data = base64.b64decode(encoded)
            signature_filename = f"signatures/{uuid.uuid4()}.png"
            s3 = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
            s3.put_object(Body=data, Bucket=os.environ.get('S3_BUCKET_NAME'), Key=signature_filename, ContentType='image/png')
            s3_operator_signature_url = f"https{os.environ.get('S3_BUCKET_NAME')}.s3.amazonaws.com/{signature_filename}"

        # 2. Cria a Instância do Checklist
        instance = ChecklistInstance(status='Pendente', operator_id=current_user.id, template_id=template.id, operator_signature=s3_operator_signature_url)
        db.session.add(instance)
        db.session.flush()

        # 3. Salva Respostas e Fotos de Evidência no S3
        for item in template.items:
            response_value = request.form.get(f'item_{item.id}_response')
            comment_value = request.form.get(f'item_{item.id}_comment')
            s3_photo_url = None
            photo_file = request.files.get(f'item_{item.id}_photo')
            if photo_file and photo_file.filename != '':
                photo_filename = f"evidence/{uuid.uuid4()}_{secure_filename(photo_file.filename)}"
                s3 = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
                s3.upload_fileobj(photo_file, os.environ.get('S3_BUCKET_NAME'), photo_filename, ExtraArgs={'ContentType': photo_file.content_type})
                s3_photo_url = f"https{os.environ.get('S3_BUCKET_NAME')}.s3.amazonaws.com/{photo_filename}"
            
            response = ChecklistItemResponse(response=response_value, comment=comment_value, instance_id=instance.id, item_template_id=item.id, photo_evidence=s3_photo_url)
            db.session.add(response)
        
        db.session.commit()

        # 4. Envia Notificação por E-mail
        leaders = template.sector.leaders
        if leaders:
            leader_emails = [leader.email for leader in leaders]
            approval_url = url_for('main.review_checklist', instance_id=instance.id, _external=True)
            send_email(subject=f'Novo Checklist para Aprovação: {template.title}', sender=current_app.config['ADMINS'][0], recipients=leader_emails, template='email/new_checklist_notification', instance=instance, approval_url=approval_url)
            flash('Checklist enviado e líder notificado por e-mail!', 'success')
        else:
            flash('Checklist enviado com sucesso! (Aviso: Nenhum líder configurado para este setor.)', 'warning')
        
        return redirect(url_for('main.index'))
    return render_template('fill_checklist.html', template=template, title='Preencher Checklist')

# --- ROTAS DO LÍDER ---
@bp.route('/leader/dashboard')
@login_required
@leader_required
def leader_dashboard():
    managed_sectors_ids = [s.id for s in current_user.sectors]
    checklist_templates_ids = [t.id for t in ChecklistTemplate.query.filter(ChecklistTemplate.sector_id.in_(managed_sectors_ids)).all()]
    pending_checklists = ChecklistInstance.query.filter(ChecklistInstance.template_id.in_(checklist_templates_ids), ChecklistInstance.status == 'Pendente').order_by(ChecklistInstance.submission_date.desc()).all()
    return render_template('leader/leader_dashboard.html', checklists=pending_checklists, title='Painel do Líder')

@bp.route('/leader/checklist/<int:instance_id>/review', methods=['GET', 'POST'])
@login_required
@leader_required
def review_checklist(instance_id):
    instance = ChecklistInstance.query.get_or_404(instance_id)
    if instance.template.sector not in current_user.sectors and current_user.role != 'Administrador':
        abort(403)
    if request.method == 'POST':
        action = request.form.get('action')
        
        # Salva Assinatura do Líder no S3
        s3_leader_signature_url = None
        signature_data_url = request.form.get('signature')
        if signature_data_url:
            header, encoded = signature_data_url.split(",", 1)
            data = base64.b64decode(encoded)
            signature_filename = f"signatures/{uuid.uuid4()}.png"
            s3 = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
            s3.put_object(Body=data, Bucket=os.environ.get('S3_BUCKET_NAME'), Key=signature_filename, ContentType='image/png')
            s3_leader_signature_url = f"https{os.environ.get('S3_BUCKET_NAME')}.s3.amazonaws.com/{signature_filename}"
        
        instance.leader_signature = s3_leader_signature_url
        instance.status = action
        instance.approval_date = datetime.utcnow()
        instance.leader_id = current_user.id
        db.session.commit()
        flash(f'Checklist {action.lower()} com sucesso!', 'success')
        return redirect(url_for('main.leader_dashboard'))
    return render_template('leader/review_checklist.html', instance=instance, title='Revisar Checklist')

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
    sectors = Sector.query.order_by('name').all()
    return render_template('admin/sectors.html', sectors=sectors, title='Gerenciar Setores')

@bp.route('/admin/sector/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_sector():
    form = SectorForm()
    form.leaders.choices = [(u.id, u.username) for u in User.query.filter_by(role='Líder').all()]
    if form.validate_on_submit():
        sector = Sector(name=form.name.data, description=form.description.data)
        selected_leaders = User.query.filter(User.id.in_(form.leaders.data)).all()
        sector.leaders = selected_leaders
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
    form.leaders.choices = [(u.id, u.username) for u in User.query.filter_by(role='Líder').all()]
    if request.method == 'GET':
        form.leaders.data = [leader.id for leader in sector.leaders]
    if form.validate_on_submit():
        sector.name = form.name.data
        sector.description = form.description.data
        sector.leaders.clear()
        selected_leaders = User.query.filter(User.id.in_(form.leaders.data)).all()
        sector.leaders = selected_leaders
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
    form.sector.choices = [(s.id, s.name) for s in Sector.query.order_by('name').all()]
    if form.validate_on_submit():
        template = ChecklistTemplate(title=form.title.data, description=form.description.data, sector_id=form.sector.data)
        db.session.add(template)
        db.session.commit()
        flash('Modelo de checklist criado com sucesso!', 'success')
        return redirect(url_for('main.checklist_detail', template_id=template.id))
    return render_template('admin/checklist_template_form.html', form=form, title='Novo Modelo')

@bp.route('/admin/checklist/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def checklist_detail(template_id):
    template = ChecklistTemplate.query.get_or_404(template_id)
    item_form = ChecklistItemForm()
    if item_form.validate_on_submit():
        new_item = ChecklistItemTemplate(question=item_form.question.data, template_id=template.id)
        db.session.add(new_item)
        db.session.commit()
        flash('Item adicionado com sucesso!', 'success')
        return redirect(url_for('main.checklist_detail', template_id=template.id))
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
    url_to_fill = url_for('main.fill_checklist', template_id=template_id, _external=True)
    qr_img = qrcode.make(url_to_fill)
    buf = io.BytesIO()
    qr_img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@bp.route('/admin/users')
@login_required
@admin_required
def list_users():
    users = User.query.filter(User.id != current_user.id).order_by(User.username).all()
    return render_template('admin/users.html', users=users, title='Gerenciar Usuários')

@bp.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)
    if form.validate_on_submit():
        if user.username != form.username.data and User.query.filter_by(username=form.username.data).first():
            flash('Este nome de usuário já está em uso.', 'danger')
        elif user.email != form.email.data and User.query.filter_by(email=form.email.data).first():
            flash('Este email já está em uso.', 'danger')
        else:
            user.username = form.username.data
            user.email = form.email.data
            user.role = form.role.data
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('main.list_users'))
    return render_template('admin/user_form.html', form=form, user=user, title='Editar Usuário')

@bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('main.list_users'))
    db.session.delete(user)
    db.session.commit()
    flash('Usuário excluído com sucesso.', 'success')
    return redirect(url_for('main.list_users'))

# --- ROTAS DE HISTÓRICO E API ---
@bp.route('/history')
@login_required
@leader_required
def checklist_history():
    query = ChecklistInstance.query
    status = request.args.get('status')
    sector_id = request.args.get('sector_id', type=int)
    if status:
        query = query.filter(ChecklistInstance.status == status)
    if sector_id:
        template_ids = [t.id for t in ChecklistTemplate.query.filter_by(sector_id=sector_id).all()]
        query = query.filter(ChecklistInstance.template_id.in_(template_ids))
    if current_user.role == 'Líder':
        managed_sectors_ids = [s.id for s in current_user.sectors]
        template_ids_leader = [t.id for t in ChecklistTemplate.query.filter(ChecklistTemplate.sector_id.in_(managed_sectors_ids)).all()]
        query = query.filter(ChecklistInstance.template_id.in_(template_ids_leader))
    all_checklists = query.order_by(ChecklistInstance.submission_date.desc()).all()
    all_sectors = Sector.query.order_by('name').all()
    return render_template('history.html', checklists=all_checklists, sectors=all_sectors, selected_status=status, selected_sector_id=sector_id, title='Histórico')

@bp.route('/export/pdf/<int:instance_id>')
@login_required
@leader_required
def export_pdf(instance_id):
    instance = ChecklistInstance.query.get_or_404(instance_id)
    # Com S3, o template pega a URL diretamente do objeto 'instance'
    html_string = render_template('pdf/report.html', instance=instance)
    # WeasyPrint buscará as imagens das URLs do S3
    pdf_bytes = HTML(string=html_string).write_pdf()
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=checklist_{instance.id}.pdf'
    return response

@bp.route('/export/excel')
@login_required
@leader_required
def export_excel():
    query = ChecklistInstance.query
    status = request.args.get('status')
    sector_id = request.args.get('sector_id', type=int)
    if status:
        query = query.filter(ChecklistInstance.status == status)
    if sector_id:
        template_ids = [t.id for t in ChecklistTemplate.query.filter_by(sector_id=sector_id).all()]
        query = query.filter(ChecklistInstance.template_id.in_(template_ids))
    if current_user.role == 'Líder':
        managed_sectors_ids = [s.id for s in current_user.sectors]
        template_ids_leader = [t.id for t in ChecklistTemplate.query.filter(ChecklistTemplate.sector_id.in_(managed_sectors_ids)).all()]
        query = query.filter(ChecklistInstance.template_id.in_(template_ids_leader))
    checklists_to_export = query.order_by(ChecklistInstance.submission_date.desc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório de Checklists"
    headers = ["ID Checklist", "Status", "Data Submissão", "Operador", "Líder Aprovação", "Data Aprovação", "Setor", "Checklist", "ID Item", "Pergunta", "Resposta", "Comentário", "Link Evidência"]
    ws.append(headers)
    for instance in checklists_to_export:
        for response in instance.responses:
            row = [
                instance.id, instance.status, instance.submission_date.strftime('%Y-%m-%d %H:%M:%S'),
                instance.operator.username, instance.leader.username if instance.leader else '',
                instance.approval_date.strftime('%Y-%m-%d %H:%M:%S') if instance.approval_date else '',
                instance.template.sector.name, instance.template.title, response.item_template.id,
                response.item_template.question, response.response, response.comment, response.photo_evidence or ''
            ]
            ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    return send_file(io.BytesIO(excel_bytes), as_attachment=True, download_name='relatorio_checklists.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@bp.route('/api/dashboard_data')
@login_required
@admin_required
def get_dashboard_data():
    compliance_query = db.session.query(Sector.name, (func.sum(case((ChecklistItemResponse.response == 'Sim', 1), else_=0)) * 100.0 / func.count(ChecklistItemResponse.id))).join(ChecklistTemplate, Sector.id == ChecklistTemplate.sector_id).join(ChecklistInstance, ChecklistTemplate.id == ChecklistInstance.template_id).join(ChecklistItemResponse, ChecklistInstance.id == ChecklistItemResponse.instance_id).group_by(Sector.name).all()
    non_compliant_query = db.session.query(ChecklistItemTemplate.question, func.count(ChecklistItemResponse.id).label('count')).join(ChecklistItemResponse, ChecklistItemTemplate.id == ChecklistItemResponse.item_template_id).filter(ChecklistItemResponse.response == 'Não').group_by(ChecklistItemTemplate.question).order_by(func.count(ChecklistItemResponse.id).desc()).limit(5).all()
    compliance_data = {'labels': [row[0] for row in compliance_query], 'values': [round(row[1], 2) for row in compliance_query]}
    non_compliant_data = {'labels': [row[0] for row in non_compliant_query], 'values': [row[1] for row in non_compliant_query]}
    return jsonify({'compliance_by_sector': compliance_data, 'top_non_compliant_items': non_compliant_data})