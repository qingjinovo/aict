import os
import json
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.user import User
from models.ct_image import CTImage
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
        ProgressService.complete_processing(image_id)
    else:
        mock_result = ModelIntegrationService.generate_mock_result(image_id)
        ct_image.status = 'ai_completed'
        ct_image.ai_model_version = mock_result['result'].get('model_version')
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

@api_bp.route('/ct-images/<int:image_id>/annotation', methods=['POST'])
@login_required
def save_annotation(image_id):
    ct_image = CTImage.query.get_or_404(image_id)

    if ct_image.doctor_id and ct_image.doctor_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    annotation_filename = request.form.get('annotation_filename')
    drawing_data = request.form.get('drawing_data')
    dims_str = request.form.get('dims')
    saved_at = request.form.get('saved_at')

    if not annotation_filename:
        return jsonify({'success': False, 'error': 'annotation_filename is required'}), 400

    annotation_dir = os.path.join(os.path.dirname(ct_image.file_path), 'annotations')
    annotation_dir = os.path.abspath(annotation_dir)
    os.makedirs(annotation_dir, exist_ok=True)

    annotation_file_path = os.path.join(annotation_dir, annotation_filename)

    logging.info(f"save_annotation called with drawing_data type: {type(drawing_data)}, length: {len(drawing_data) if drawing_data else 0}")
    logging.info(f"dims_str received: {dims_str}, type: {type(dims_str)}, is None: {dims_str is None}, is empty: {dims_str == '' if dims_str else True}")

    dims = None
    if dims_str:
        try:
            raw_dims = json.loads(dims_str)
            if raw_dims and len(raw_dims) >= 3:
                if len(raw_dims) == 3:
                    dims = raw_dims
                else:
                    dims = [raw_dims[-1], raw_dims[-2], raw_dims[-3]]
                logging.info(f"dims parsed successfully: {dims} (from raw: {raw_dims})")
            else:
                logging.warning(f"Invalid dims format: {raw_dims}")
        except json.JSONDecodeError as e:
            logging.warning(f"Invalid JSON in dims: {e}")
            dims = None
    else:
        logging.warning("dims_str is None or empty, dims will not be available")

    save_success = False
    try:
        import numpy as np
        import SimpleITK as sitk

        annotation_file = request.files.get('annotation_file')
        if annotation_file and annotation_file.filename:
            logging.info(f"Received annotation file upload: {annotation_file.filename}")
            annotation_file.save(annotation_file_path)
            logging.info(f"Annotation file saved directly: {annotation_file_path}")
            save_success = True
        elif drawing_data:
            logging.info(f"drawing_data received, first 100 chars: {str(drawing_data)[:100]}")

            try:
                mask_data = json.loads(drawing_data)
            except json.JSONDecodeError as e:
                logging.warning(f"Invalid JSON in drawing_data: {e}")
                mask_data = None

            logging.info(f"mask_data type after parse: {type(mask_data)}, is list: {isinstance(mask_data, list)}, is None: {mask_data is None}")

            if mask_data and isinstance(mask_data, (list, tuple)):
                mask_array = np.array(mask_data, dtype=np.uint8)
                logging.info(f"mask_array shape before reshape: {mask_array.shape}, size: {mask_array.size}")

                if dims and len(dims) == 3:
                    expected_size = dims[0] * dims[1] * dims[2]
                    logging.info(f"Attempting to reshape to dims: {dims}, expected size: {expected_size}")
                    if mask_array.size == expected_size:
                        mask_array = mask_array.reshape(dims)
                        logging.info(f"mask_array reshaped successfully to: {mask_array.shape}")
                    else:
                        logging.warning(f"mask_array size {mask_array.size} does not match expected {expected_size} from dims {dims}")
                        mask_data = None
                else:
                    logging.warning(f"dims not available or invalid: {dims}, cannot reshape mask_array")
                    mask_data = None
            else:
                logging.warning(f"drawing_data is not a valid array: {type(mask_data)}")
                mask_data = None

            logging.info(f"Before save check: mask_data is None: {mask_data is None}, ct_image.file_path exists: {ct_image.file_path and os.path.exists(ct_image.file_path)}")

            if mask_data is not None and ct_image.file_path and os.path.exists(ct_image.file_path):
                ref_image = sitk.ReadImage(ct_image.file_path)
                ref_array = sitk.GetArrayFromImage(ref_image)
                logging.info(f"Reference image shape: {ref_array.shape}")

                if mask_array.shape != ref_array.shape:
                    logging.warning(f"mask_array shape {mask_array.shape} does not match reference image shape {ref_array.shape}")
                    if dims and len(dims) == 3 and dims == tuple(ref_array.shape):
                        logging.info("Shapes match via dims, proceeding")
                    else:
                        logging.error("Cannot save annotation: shape mismatch and dims don't resolve it")
                        mask_data = None

                if mask_data is not None:
                    mask_image = sitk.GetImageFromArray(mask_array)
                    mask_image.CopyInformation(ref_image)
                    sitk.WriteImage(mask_image, annotation_file_path)
                    logging.info(f"Annotation NIfTI file saved successfully: {annotation_file_path}")
                    save_success = True
            elif mask_data is not None:
                logging.info(f"Saving annotation without reference image (no ct_image.file_path)")
                mask_image = sitk.GetImageFromArray(mask_array)
                sitk.WriteImage(mask_image, annotation_file_path)
                logging.info(f"Annotation NIfTI file saved (no reference): {annotation_file_path}")
                save_success = True
            else:
                logging.warning(f"Could not save annotation NIfTI file, mask_data was set to None")
        else:
            logging.warning(f"No annotation file or drawing_data received, skipping NIfTI file save")
    except Exception as e:
        logging.warning(f"Failed to save annotation NIfTI file: {e}")
        import traceback
        logging.warning(traceback.format_exc())

    ct_image.annotation_file_path = annotation_file_path
    ct_image.status = 'doctor_annotating'
    db.session.commit()

    ProgressService.create_progress_record(
        ct_image_id=image_id,
        stage='annotation_saved',
        message=f'医生保存标注: {annotation_filename}'
    )

    annotation_record = {
        'ct_image_id': image_id,
        'annotation_filename': annotation_filename,
        'annotation_file_path': annotation_file_path,
        'drawing_data': drawing_data,
        'saved_at': saved_at,
        'saved_by': current_user.id,
        'doctor_name': current_user.full_name
    }

    return jsonify({
        'success': True,
        'message': 'Annotation saved successfully',
        'annotation': annotation_record
    })

@api_bp.route('/ct-images/<int:image_id>/annotation', methods=['GET'])
@login_required
def get_annotation(image_id):
    ct_image = CTImage.query.get_or_404(image_id)

    return jsonify({
        'success': True,
        'annotation': {
            'ct_image_id': image_id,
            'annotation_file_path': ct_image.annotation_file_path,
            'has_annotation': bool(ct_image.annotation_file_path)
        }
    })

@api_bp.route('/ct-images/<int:image_id>/annotation-file', methods=['POST'])
@login_required
def save_annotation_file(image_id):
    ct_image = CTImage.query.get_or_404(image_id)
    data = request.get_json()

    annotation_filename = data.get('annotation_filename')
    if not annotation_filename:
        return jsonify({'success': False, 'error': 'annotation_filename is required'}), 400

    annotation_dir = os.path.join(os.path.dirname(ct_image.file_path), 'annotations')
    annotation_dir = os.path.abspath(annotation_dir)
    os.makedirs(annotation_dir, exist_ok=True)

    annotation_file_path = os.path.join(annotation_dir, annotation_filename)

    ct_image.annotation_file_path = annotation_file_path
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Annotation file path saved',
        'annotation_file_path': annotation_file_path
    })

def require_auth(f):
    """自定义认证装饰器，返回JSON错误而不是重定向"""
    from functools import wraps
    from flask import request, jsonify
    from flask_login import current_user

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/ct-images/<int:image_id>/ai-annotate', methods=['POST'])
@require_auth
def run_ai_annotation(image_id):
    """触发AI标注流程"""
    import logging
    logger = logging.getLogger(__name__)

    ct_image = CTImage.query.get_or_404(image_id)

    if ct_image.doctor_id and ct_image.doctor_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    logger.info(f"Starting AI annotation for ct_image {image_id}")
    logger.info(f"CT image path: {ct_image.file_path}")
    logger.info(f"Annotation path: {ct_image.annotation_file_path}")

    from services.sam3d_service import get_sam3d_service

    service = get_sam3d_service()
    logger.info("get_sam3d_service() returned")

    use_gt_annotation = False
    if ct_image.annotation_file_path and os.path.exists(ct_image.annotation_file_path):
        logger.info("Annotation file exists, will use it as ground truth")
        use_gt_annotation = True
    else:
        logger.warning("Annotation file does not exist, will use center-point inference")
        if not ct_image.annotation_file_path:
            logger.warning("No annotation_file_path in database")
        else:
            logger.warning(f"File does not exist at: {ct_image.annotation_file_path}")

    try:
        logger.info("About to call service.infer() or infer_simple()")
        try:
            if use_gt_annotation:
                result = service.infer(
                    img_path=ct_image.file_path,
                    gt_path=ct_image.annotation_file_path,
                    num_clicks=1
                )
            else:
                logger.info("Using infer_simple (center point mode)")
                result = service.infer_simple(
                    img_path=ct_image.file_path
                )
        except Exception as infer_e:
            logger.error(f"service.infer() threw exception: {infer_e}")
            raise
        logger.info(f"Inference result type: {type(result)}")
        logger.info(f"Inference result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
        logger.info(f"Inference result: {result}")

        if result.get('success') and result.get('output_path'):
            ct_image.ai_annotation_file_path = result['output_path']
            ct_image.status = 'ai_annotated'
            db.session.commit()

            ProgressService.create_progress_record(
                ct_image_id=image_id,
                stage='ai_annotation_completed',
                message='AI标注完成'
            )

            return jsonify({
                'success': True,
                'message': 'AI标注完成',
                'ai_annotation_path': result['output_path']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'AI标注失败')
            }), 500

    except Exception as e:
        import traceback
        print(f'[API] AI annotation error: {e}')
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/ct-images/<int:image_id>/ai-annotate/status', methods=['GET'])
@login_required
def get_ai_annotation_status(image_id):
    """获取AI标注状态"""
    ct_image = CTImage.query.get_or_404(image_id)

    return jsonify({
        'success': True,
        'has_ai_annotation': bool(ct_image.ai_annotation_file_path),
        'ai_annotation_path': ct_image.ai_annotation_file_path,
        'status': ct_image.status
    })
