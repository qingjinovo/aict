from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.user import User
from models.ct_image import CTImage, Annotation
from extensions import db
from services.notification_service import NotificationService, ProgressService, MessageService
from services.file_upload_service import FileUploadService
from services.model_integration_service import ModelIntegrationService

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/ct-images', methods=['POST'])
@login_required
def upload_ct_image():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    body_part = request.form.get('body_part', '')
    description = request.form.get('description', '')

    file_info = FileUploadService.save_file(file)
    if not file_info:
        return jsonify({'success': False, 'error': 'Invalid file format'}), 400

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

    ProgressService.create_progress_record(ct_image.id, 'uploaded', 'CT图像上传成功')

    return jsonify({'success': True, 'ct_image': ct_image.to_dict()}), 201

@api_bp.route('/ct-images/<int:image_id>', methods=['GET'])
@login_required
def get_ct_image(image_id):
    ct_image = CTImage.query.get_or_404(image_id)
    return jsonify({'success': True, 'ct_image': ct_image.to_dict()})

@api_bp.route('/ct-images/<int:image_id>/status', methods=['PUT'])
@login_required
def update_ct_image_status(image_id):
    ct_image = CTImage.query.get_or_404(image_id)
    data = request.get_json()

    new_status = data.get('status')
    if not new_status:
        return jsonify({'success': False, 'error': 'Status is required'}), 400

    valid_statuses = [
        'uploaded', 'notifying', 'doctor_reviewing', 'ai_processing',
        'ai_completed', 'doctor_annotating', 'pending_confirmation', 'completed'
    ]
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'error': f'Invalid status. Must be one of: {valid_statuses}'}), 400

    old_status = ct_image.status
    ct_image.status = new_status
    db.session.commit()

    ProgressService.create_progress_record(
        ct_image_id=image_id,
        stage=new_status,
        message=f'状态更新: {old_status} -> {new_status}'
    )

    if new_status == 'ai_processing':
        NotificationService.create_notification(
            user_id=ct_image.patient_id,
            title='AI 分析开始',
            content=f'您的 CT 检查已开始 AI 分析，请稍候',
            notification_type='ai_processing_started',
            related_ct_image_id=image_id
        )
    elif new_status == 'ai_completed':
        NotificationService.create_notification(
            user_id=ct_image.doctor_id,
            title='AI 分析完成',
            content=f'CT 检查 #{image_id} 的 AI 分析已完成，请医生审核',
            notification_type='ai_processing_completed',
            related_ct_image_id=image_id
        )

    return jsonify({
        'success': True,
        'ct_image': ct_image.to_dict(),
        'status_change': {'from': old_status, 'to': new_status}
    })

@api_bp.route('/ct-images/<int:image_id>/progress', methods=['GET'])
@login_required
def get_progress(image_id):
    progress_info = ProgressService.get_ct_progress(image_id)
    return jsonify({'success': True, 'progress': progress_info})

@api_bp.route('/ct-images/<int:image_id>/annotations', methods=['GET', 'POST'])
@login_required
def handle_annotations(image_id):
    if request.method == 'GET':
        annotations = Annotation.query.filter_by(ct_image_id=image_id).all()
        return jsonify({
            'success': True,
            'annotations': [a.to_dict() for a in annotations]
        })

    data = request.get_json()
    annotation = Annotation(
        ct_image_id=image_id,
        doctor_id=current_user.id,
        annotation_type=data.get('annotation_type'),
        slice_number=data.get('slice_number'),
        coordinates_x=data.get('coordinates', {}).get('x'),
        coordinates_y=data.get('coordinates', {}).get('y'),
        coordinates_z=data.get('coordinates', {}).get('z'),
        radius=data.get('radius'),
        label=data.get('label'),
        severity=data.get('severity'),
        notes=data.get('notes'),
        is_abnormal=data.get('is_abnormal', False),
        ai_generated=data.get('ai_generated', False)
    )
    db.session.add(annotation)
    db.session.commit()

    return jsonify({'success': True, 'annotation': annotation.to_dict()}), 201

@api_bp.route('/annotations/<int:annotation_id>', methods=['PUT', 'DELETE'])
@login_required
def modify_annotation(annotation_id):
    annotation = Annotation.query.get_or_404(annotation_id)

    if annotation.doctor_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    if request.method == 'PUT':
        data = request.get_json()
        annotation.annotation_type = data.get('annotation_type', annotation.annotation_type)
        annotation.slice_number = data.get('slice_number', annotation.slice_number)
        annotation.coordinates_x = data.get('coordinates', {}).get('x', annotation.coordinates_x)
        annotation.coordinates_y = data.get('coordinates', {}).get('y', annotation.coordinates_y)
        annotation.coordinates_z = data.get('coordinates', {}).get('z', annotation.coordinates_z)
        annotation.radius = data.get('radius', annotation.radius)
        annotation.label = data.get('label', annotation.label)
        annotation.severity = data.get('severity', annotation.severity)
        annotation.notes = data.get('notes', annotation.notes)
        annotation.is_abnormal = data.get('is_abnormal', annotation.is_abnormal)
        db.session.commit()
        return jsonify({'success': True, 'annotation': annotation.to_dict()})

    db.session.delete(annotation)
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/ct-images/<int:image_id>/call-model', methods=['POST'])
@login_required
def call_model(image_id):
    ct_image = CTImage.query.get_or_404(image_id)

    if ct_image.doctor_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    result = ModelIntegrationService.call_model_inference(ct_image.file_path)

    if result['success']:
        ct_image.status = 'ai_completed'
        ct_image.ai_model_version = result['result'].get('model_version')
        ct_image.processing_completed_at = db.func.now()
        db.session.commit()

        for pred in result['result'].get('predictions', []):
            annotation = Annotation(
                ct_image_id=image_id,
                doctor_id=current_user.id,
                annotation_type='ai_prediction',
                slice_number=pred.get('slice_number'),
                coordinates_x=pred.get('coordinates', {}).get('x'),
                coordinates_y=pred.get('coordinates', {}).get('y'),
                coordinates_z=pred.get('coordinates', {}).get('z'),
                radius=pred.get('radius'),
                label=pred.get('label'),
                severity=pred.get('severity'),
                is_abnormal=True,
                ai_generated=True
            )
            db.session.add(annotation)

        db.session.commit()
        ProgressService.complete_processing(image_id)
    else:
        mock_result = ModelIntegrationService.generate_mock_result(image_id)
        ct_image.status = 'ai_completed'
        ct_image.ai_model_version = mock_result['result'].get('model_version')

        for pred in mock_result['result'].get('predictions', []):
            annotation = Annotation(
                ct_image_id=image_id,
                doctor_id=current_user.id,
                annotation_type='ai_prediction',
                slice_number=pred.get('slice_number'),
                coordinates_x=pred.get('coordinates', {}).get('x'),
                coordinates_y=pred.get('coordinates', {}).get('y'),
                coordinates_z=pred.get('coordinates', {}).get('z'),
                radius=pred.get('radius'),
                label=pred.get('label'),
                severity=pred.get('severity'),
                is_abnormal=True,
                ai_generated=True
            )
            db.session.add(annotation)

        db.session.commit()
        ProgressService.complete_processing(image_id)

        return jsonify({
            'success': True,
            'is_mock': True,
            'message': 'Model service unavailable, using mock results',
            'result': mock_result
        })

    return jsonify({'success': True, 'result': result['result']})

@api_bp.route('/messages', methods=['GET', 'POST'])
@login_required
def handle_messages():
    ct_image_id = request.args.get('ct_image_id')

    if request.method == 'POST':
        data = request.get_json()
        message = MessageService.create_message(
            ct_image_id=data['ct_image_id'],
            sender_id=current_user.id,
            receiver_id=data['receiver_id'],
            content=data['content']
        )
        return jsonify({'success': True, 'message': message.to_dict()}), 201

    if ct_image_id:
        messages = MessageService.get_ct_messages(int(ct_image_id))
    else:
        messages = Message.query.filter(
            (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
        ).all()

    return jsonify({'success': True, 'messages': [m.to_dict() for m in messages]})

@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    notifications = NotificationService.get_user_notifications(current_user.id, unread_only)
    unread_count = NotificationService.get_unread_count(current_user.id)

    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': unread_count
    })

@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    success = NotificationService.mark_as_read(notification_id)
    return jsonify({'success': success})

@api_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    NotificationService.mark_all_as_read(current_user.id)
    return jsonify({'success': True})

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({'success': True, 'user': user.to_dict()})

@api_bp.route('/model/info', methods=['GET'])
@login_required
def get_model_info():
    info = ModelIntegrationService.get_model_info()
    return jsonify({'success': True, 'model_info': info})
