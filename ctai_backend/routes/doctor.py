from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from models.user import User
from models.ct_image import CTImage, Annotation
from models.progress import ProgressRecord, Message, Notification
from extensions import db
from services.notification_service import NotificationService, ProgressService
from services.file_upload_service import FileUploadService
import os

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/doctor/dashboard')
@login_required
def dashboard():
    if not current_user.is_doctor():
        flash('只有医生可以访问此页面', 'error')
        return redirect(url_for('auth.role_selection'))

    pending_reports = CTImage.query.filter(
        CTImage.status.in_(['uploaded', 'notifying', 'doctor_reviewing', 'ai_processing', 'ai_completed', 'doctor_annotating', 'pending_confirmation'])
    ).order_by(CTImage.created_at.desc()).all()

    completed_reports = CTImage.query.filter_by(status='completed').order_by(CTImage.updated_at.desc()).limit(10).all()

    messages = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.created_at.desc()).limit(5).all()
    unread_count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()

    unread_notifications = NotificationService.get_user_notifications(current_user.id, unread_only=True)

    return render_template('doctor/dashboard.html',
                         pending_reports=pending_reports,
                         completed_reports=completed_reports,
                         messages=messages,
                         unread_count=unread_count,
                         unread_notifications=unread_notifications)

@doctor_bp.route('/doctor/upload')
@login_required
def upload():
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))
    return render_template('doctor/upload.html')

@doctor_bp.route('/doctor/processing/<int:report_id>')
@login_required
def processing(report_id):
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))

    ct_image = CTImage.query.get_or_404(report_id)
    progress_info = ProgressService.get_ct_progress(report_id)

    return render_template('doctor/processing.html',
                         ct_image=ct_image,
                         progress_info=progress_info)

@doctor_bp.route('/doctor/annotate/<int:report_id>')
@login_required
def annotate(report_id):
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))

    ct_image = CTImage.query.get_or_404(report_id)
    annotations = Annotation.query.filter_by(ct_image_id=report_id).all()
    progress_info = ProgressService.get_ct_progress(report_id)
    messages = Message.query.filter_by(ct_image_id=report_id).order_by(Message.created_at.asc()).all()

    return render_template('doctor/annotate.html',
                         ct_image=ct_image,
                         annotations=annotations,
                         progress_info=progress_info,
                         messages=messages)

@doctor_bp.route('/doctor/confirm/<int:report_id>', methods=['GET', 'POST'])
@login_required
def confirm(report_id):
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))

    ct_image = CTImage.query.get_or_404(report_id)
    annotations = Annotation.query.filter_by(ct_image_id=report_id).all()

    if request.method == 'POST':
        ct_image.final_report = request.form.get('final_report', '')
        ct_image.final_diagnosis = request.form.get('final_diagnosis', '')
        ct_image.status = 'completed'
        ct_image.confirmed_by_doctor_id = current_user.id
        ct_image.confirmed_at = db.func.now()

        ProgressService.complete_processing(report_id)

        NotificationService.create_notification(
            user_id=ct_image.patient_id,
            title='报告已完成',
            content=f'您的CT检查报告已完成，医生已给出最终诊断',
            notification_type='report_completed',
            related_ct_image_id=report_id
        )

        flash('报告已确认提交', 'success')
        return redirect(url_for('doctor.dashboard'))

    return render_template('doctor/confirm.html',
                         ct_image=ct_image,
                         annotations=annotations)

@doctor_bp.route('/doctor/message/<int:message_id>')
@login_required
def message_detail(message_id):
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))

    message = Message.query.get_or_404(message_id)
    message.is_read = True
    message.read_at = db.func.now()
    db.session.commit()

    ct_image = message.ct_image
    patient = ct_image.patient if ct_image else None

    return render_template('doctor/message_detail.html',
                         message=message,
                         ct_image=ct_image,
                         patient=patient)

@doctor_bp.route('/doctor/messages')
@login_required
def messages():
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))

    all_messages = Message.query.filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()

    conversations = {}
    for msg in all_messages:
        other_id = msg.sender_id if msg.receiver_id == current_user.id else msg.receiver_id
        if other_id not in conversations:
            conversations[other_id] = {
                'user': User.query.get(other_id),
                'last_message': msg,
                'unread': 0
            }
        if msg.receiver_id == current_user.id and not msg.is_read:
            conversations[other_id]['unread'] += 1

    return render_template('doctor/messages.html', conversations=conversations)
