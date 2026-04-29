from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models.user import User
from models.ct_image import CTImage
from models.progress import Message, Notification
from extensions import db
from services.notification_service import NotificationService, ProgressService, MessageService
from services.file_upload_service import FileUploadService

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/patient/dashboard')
@login_required
def dashboard():
    if not current_user.is_patient():
        flash('只有患者可以访问此页面', 'error')
        return redirect(url_for('auth.role_selection'))

    reports = CTImage.query.filter_by(patient_id=current_user.id).order_by(CTImage.created_at.desc()).all()
    unread_notifications = NotificationService.get_user_notifications(current_user.id, unread_only=True)

    latest_report = reports[0] if reports else None
    history_reports = reports[1:] if len(reports) > 1 else []

    return render_template('patient/dashboard.html',
                         latest_report=latest_report,
                         history_reports=history_reports,
                         unread_notifications=unread_notifications)

@patient_bp.route('/patient/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if not current_user.is_patient():
        return redirect(url_for('auth.role_selection'))

    if request.method == 'POST':
        errors = []

        if 'ct_file' not in request.files:
            flash('请选择要上传的文件', 'error')
            return redirect(request.url)

        file = request.files['ct_file']
        body_part = request.form.get('body_part', '')
        description = request.form.get('description', '')

        if file.filename == '':
            flash('请选择要上传的文件', 'error')
            return redirect(request.url)

        if not body_part:
            flash('请选择检查部位', 'error')
            return redirect(request.url)

        if not FileUploadService.allowed_file(file.filename):
            flash('不支持的文件格式，请上传 NIfTI、DICOM、PNG 或 JPG 格式文件', 'error')
            return redirect(request.url)

        try:
            file_info = FileUploadService.save_file(file)

            if not file_info:
                flash('文件上传失败，请检查文件格式和大小', 'error')
                return redirect(request.url)

            ct_image = CTImage(
                patient_id=current_user.id,
                file_name=file_info['filename'],
                original_filename=file.filename,
                file_path=file_info['filepath'],
                file_size=file_info['file_size'],
                file_type=file_info['file_type'],
                body_part=body_part,
                description=description,
                status='uploaded'
            )
            db.session.add(ct_image)
            db.session.commit()

            ProgressService.create_progress_record(
                ct_image_id=ct_image.id,
                stage='uploaded',
                message='CT图像上传成功'
            )

            doctor = User.query.filter_by(role='doctor').first()
            if doctor:
                ct_image.doctor_id = doctor.id
                db.session.commit()

                ProgressService.create_progress_record(
                    ct_image_id=ct_image.id,
                    stage='notifying',
                    message='正在通知医生'
                )

                NotificationService.create_notification(
                    user_id=doctor.id,
                    title='新CT图像待处理',
                    content=f'患者 {current_user.full_name} 上传了新的CT图像（{body_part}），请及时处理',
                    notification_type='new_upload',
                    related_ct_image_id=ct_image.id
                )

                flash('CT图像上传成功，已通知医生', 'success')
            else:
                flash('CT图像上传成功，但暂无可用医生', 'warning')

        except Exception as e:
            db.session.rollback()
            flash(f'上传过程中发生错误: {str(e)}', 'error')

        return redirect(url_for('patient.dashboard'))

    return render_template('patient/upload.html')

@patient_bp.route('/patient/report/<int:report_id>')
@login_required
def report(report_id):
    if not current_user.is_patient():
        return redirect(url_for('auth.role_selection'))

    ct_image = CTImage.query.get_or_404(report_id)

    if ct_image.patient_id != current_user.id:
        flash('您无权查看此报告', 'error')
        return redirect(url_for('patient.dashboard'))

    progress_info = ProgressService.get_ct_progress(report_id)
    messages = Message.query.filter_by(ct_image_id=report_id).order_by(Message.created_at.asc()).all()

    return render_template('patient/report.html',
                         ct_image=ct_image,
                         progress_info=progress_info,
                         messages=messages)

@patient_bp.route('/patient/question-menu')
@login_required
def question_menu():
    if not current_user.is_patient():
        return redirect(url_for('auth.role_selection'))

    reports = CTImage.query.filter_by(patient_id=current_user.id).order_by(CTImage.created_at.desc()).all()

    return render_template('patient/question_menu.html', reports=reports)

@patient_bp.route('/patient/ai-chat')
@login_required
def ai_chat():
    if not current_user.is_patient():
        return redirect(url_for('auth.role_selection'))

    reports = CTImage.query.filter_by(patient_id=current_user.id).order_by(CTImage.created_at.desc()).all()

    return render_template('patient/ai_chat.html', reports=reports)

@patient_bp.route('/patient/message/<int:report_id>', methods=['GET', 'POST'])
@login_required
def message(report_id):
    if not current_user.is_patient():
        return redirect(url_for('auth.role_selection'))

    ct_image = CTImage.query.get_or_404(report_id)

    if ct_image.patient_id != current_user.id:
        flash('您无权查看此报告', 'error')
        return redirect(url_for('patient.dashboard'))

    if request.method == 'POST':
        content = request.form.get('content', '')
        if content and ct_image.doctor_id:
            MessageService.create_message(
                ct_image_id=report_id,
                sender_id=current_user.id,
                receiver_id=ct_image.doctor_id,
                content=content
            )
            flash('消息已发送', 'success')

    messages = Message.query.filter_by(ct_image_id=report_id).order_by(Message.created_at.asc()).all()
    doctor = User.query.get(ct_image.doctor_id) if ct_image.doctor_id else None

    return render_template('patient/message.html',
                         ct_image=ct_image,
                         messages=messages,
                         doctor=doctor)

@patient_bp.route('/patient/contact-doctor')
@login_required
def contact_doctor():
    if not current_user.is_patient():
        return redirect(url_for('auth.role_selection'))

    doctors = User.query.filter_by(role='doctor', is_active=True).all()

    return render_template('patient/contact_doctor.html', doctors=doctors)

@patient_bp.route('/patient/feedback/<int:report_id>', methods=['GET', 'POST'])
@login_required
def feedback(report_id):
    if not current_user.is_patient():
        return redirect(url_for('auth.role_selection'))

    ct_image = CTImage.query.get_or_404(report_id)

    if ct_image.patient_id != current_user.id:
        flash('您无权查看此报告', 'error')
        return redirect(url_for('patient.dashboard'))

    if request.method == 'POST':
        rating = request.form.get('rating', 5)
        feedback_content = request.form.get('feedback', '')

        NotificationService.create_notification(
            user_id=ct_image.doctor_id,
            title='患者反馈',
            content=f'患者对报告 #{report_id} 提供了反馈：{feedback_content[:50]}...',
            notification_type='feedback',
            related_ct_image_id=report_id
        )

        flash('感谢您的反馈', 'success')
        return redirect(url_for('patient.dashboard'))

    return render_template('patient/feedback.html', ct_image=ct_image)
