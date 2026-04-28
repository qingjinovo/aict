from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from models.user import User
from models.ct_image import CTImage
from models.progress import ProgressRecord, Message, Notification
from extensions import db
from services.notification_service import NotificationService, ProgressService, MessageService
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
        CTImage.doctor_id == current_user.id,
        CTImage.status.in_(['uploaded', 'notifying', 'doctor_reviewing', 'ai_processing', 'ai_completed', 'doctor_annotating', 'ai_annotated', 'pending_confirmation'])
    ).order_by(CTImage.created_at.desc()).all()

    completed_reports = CTImage.query.filter_by(
        doctor_id=current_user.id,
        status='completed'
    ).order_by(CTImage.updated_at.desc()).limit(10).all()

    messages = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.created_at.desc()).limit(5).all()
    unread_count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()

    unread_notifications = NotificationService.get_user_notifications(current_user.id, unread_only=True)

    return render_template('doctor/dashboard.html',
                         pending_reports=pending_reports,
                         completed_reports=completed_reports,
                         messages=messages,
                         unread_count=unread_count,
                         unread_notifications=unread_notifications)

@doctor_bp.route('/doctor/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))
    if request.method == 'POST':
        if 'ct_file' not in request.files:
            flash('请选择CT图像文件', 'error')
            return redirect(url_for('doctor.upload'))

        file = request.files['ct_file']
        if file.filename == '':
            flash('请选择CT图像文件', 'error')
            return redirect(url_for('doctor.upload'))

        body_part = request.form.get('body_part', '')
        patient_name = request.form.get('patient_name', '')
        description = request.form.get('description', '')

        if not body_part:
            flash('请选择检查部位', 'error')
            return redirect(url_for('doctor.upload'))

        allowed_extensions = {'.png', '.jpg', '.jpeg', '.dcm', '.nifti', '.nii', '.gz'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            flash('不支持的文件格式', 'error')
            return redirect(url_for('doctor.upload'))

        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads', 'ct_images')
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{current_user.id}_{file.filename}"
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        ct_image = CTImage(
            patient_id=current_user.id,
            file_path=file_path,
            uploaded_by=current_user.id,
            status='pending',
            imaging_type=f'CT - {body_part}',
            description=description
        )
        db.session.add(ct_image)
        db.session.commit()

        flash('CT图像上传成功', 'success')
        return redirect(url_for('doctor.dashboard'))

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
    progress_info = ProgressService.get_ct_progress(report_id)
    messages = Message.query.filter_by(ct_image_id=report_id).order_by(Message.created_at.asc()).all()

    return render_template('doctor/annotate.html',
                         ct_image=ct_image,
                         progress_info=progress_info,
                         messages=messages)

@doctor_bp.route('/doctor/confirm/<int:report_id>', methods=['GET', 'POST'])
@login_required
def confirm(report_id):
    if not current_user.is_doctor():
        return redirect(url_for('auth.role_selection'))

    ct_image = CTImage.query.get_or_404(report_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'ai_annotate':
            if not ct_image.annotation_file_path:
                flash('请先保存标注', 'warning')
                return redirect(url_for('doctor.confirm', report_id=report_id))

            from services.sam3d_service import get_sam3d_service
            service = get_sam3d_service()

            try:
                result = service.infer(
                    img_path=ct_image.file_path,
                    gt_path=ct_image.annotation_file_path,
                    num_clicks=1
                )

                if result.get('success') and result.get('output_path'):
                    ct_image.ai_annotation_file_path = result['output_path']
                    ct_image.status = 'ai_annotated'
                    db.session.commit()

                    ProgressService.create_progress_record(
                        ct_image_id=report_id,
                        stage='ai_annotation_completed',
                        message='AI标注完成'
                    )

                    flash('AI标注完成，请查看AI标注结果后撰写报告', 'success')
                else:
                    flash(f'AI标注失败: {result.get("error", "未知错误")}', 'error')
            except Exception as e:
                import logging
                logging.exception('AI annotation error')
                flash(f'AI标注出错: {str(e)}', 'error')

            return redirect(url_for('doctor.confirm', report_id=report_id))

        elif action == 'submit_report':
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

    progress_info = ProgressService.get_ct_progress(report_id)
    return render_template('doctor/confirm.html',
                         ct_image=ct_image,
                         progress_info=progress_info)

@doctor_bp.route('/doctor/message/<int:message_id>', methods=['GET', 'POST'])
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

    if request.method == 'POST':
        reply = request.form.get('reply', '')
        if reply and message.sender_id:
            MessageService.create_message(
                ct_image_id=ct_image.id,
                sender_id=current_user.id,
                receiver_id=message.sender_id,
                content=reply
            )
            flash('回复已发送', 'success')
            return redirect(url_for('doctor.message_detail', message_id=message_id))

    all_messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == message.sender_id)) |
        ((Message.sender_id == message.sender_id) & (Message.receiver_id == current_user.id))
    ).filter(Message.ct_image_id == ct_image.id).order_by(Message.created_at.asc()).all()

    return render_template('doctor/message_detail.html',
                         message=message,
                         ct_image=ct_image,
                         patient=patient,
                         messages=all_messages)

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
