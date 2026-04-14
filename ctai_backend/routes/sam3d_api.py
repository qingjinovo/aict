"""
SAM-Med3D 模型推理 API 路由
提供模型推理的 REST API 接口
"""

import os
import logging
from flask import Blueprint, request, jsonify
from functools import wraps
import traceback

logger = logging.getLogger(__name__)

sam3d_bp = Blueprint('sam3d', __name__, url_prefix='/api/sam3d')

_sam3d_service = None


def get_sam3d_service():
    """获取 SAM3D 服务实例"""
    global _sam3d_service
    if _sam3d_service is None:
        from services.sam3d_service import SAM3DInferenceService
        _sam3d_service = SAM3DInferenceService()
        _sam3d_service.setup()
    return _sam3d_service


def handle_errors(f):
    """统一的错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.exception(f"API错误: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
    return decorated_function


@sam3d_bp.route('/health', methods=['GET'])
def health_check():
    """
    健康检查

    Returns:
        服务状态
    """
    service = get_sam3d_service()
    return jsonify({
        "status": "ok",
        "model_loaded": service.model is not None,
        "device": str(service.device) if service.device else "not initialized"
    })


@sam3d_bp.route('/model-info', methods=['GET'])
def get_model_info():
    """
    获取模型信息

    Returns:
        模型信息
    """
    service = get_sam3d_service()

    return jsonify({
        "success": True,
        "model_info": {
            "model_name": "SAM-Med3D",
            "model_loaded": service.model is not None,
            "checkpoint_path": service.checkpoint_path,
            "device": str(service.device) if service.device else None,
            "capabilities": [
                "volumetric_medical_segmentation",
                "promptable_segmentation",
                "multi-organ_segmentation"
            ]
        }
    })


@sam3d_bp.route('/infer', methods=['POST'])
@handle_errors
def run_inference():
    """
    执行模型推理

    Request JSON:
    {
        "image_path": "/path/to/image.nii.gz",    # 必需
        "gt_path": "/path/to/gt.nii.gz",          # 可选
        "output_path": "/path/to/output.nii.gz",  # 可选
        "num_clicks": 1,                          # 可选，默认1
        "crop_size": 128,                         # 可选，默认128
        "target_spacing": [1.5, 1.5, 1.5]        # 可选
    }

    Returns:
        推理结果
    """
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "请求体不能为空"
        }), 400

    image_path = data.get('image_path')
    if not image_path:
        return jsonify({
            "success": False,
            "error": "缺少必需字段: image_path"
        }), 400

    if not os.path.exists(image_path):
        return jsonify({
            "success": False,
            "error": f"图像文件不存在: {image_path}"
        }), 400

    gt_path = data.get('gt_path')
    output_path = data.get('output_path')
    num_clicks = data.get('num_clicks', 1)
    crop_size = data.get('crop_size', 128)
    target_spacing = tuple(data.get('target_spacing', [1.5, 1.5, 1.5]))

    service = get_sam3d_service()

    result = service.infer(
        img_path=image_path,
        gt_path=gt_path,
        output_path=output_path,
        num_clicks=num_clicks,
        crop_size=crop_size,
        target_spacing=target_spacing
    )

    return jsonify(result)


@sam3d_bp.route('/infer-simple', methods=['POST'])
@handle_errors
def run_inference_simple():
    """
    执行简化推理（无需标注文件）

    Request JSON:
    {
        "image_path": "/path/to/image.nii.gz",    # 必需
        "output_path": "/path/to/output.nii.gz", # 可选
        "center_point": [z, y, x]               # 可选
    }

    Returns:
        推理结果
    """
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "请求体不能为空"
        }), 400

    image_path = data.get('image_path')
    if not image_path:
        return jsonify({
            "success": False,
            "error": "缺少必需字段: image_path"
        }), 400

    if not os.path.exists(image_path):
        return jsonify({
            "success": False,
            "error": f"图像文件不存在: {image_path}"
        }), 400

    output_path = data.get('output_path')
    center_point = data.get('center_point')

    service = get_sam3d_service()

    result = service.infer_simple(
        img_path=image_path,
        output_path=output_path,
        center_point=center_point
    )

    return jsonify(result)


@sam3d_bp.route('/batch-infer', methods=['POST'])
@handle_errors
def run_batch_inference():
    """
    批量推理

    Request JSON:
    {
        "tasks": [
            {
                "image_path": "/path/to/image1.nii.gz",
                "gt_path": "/path/to/gt1.nii.gz",    # 可选
                "output_path": "/path/to/output1.nii.gz"  # 可选
            },
            ...
        ]
    }

    Returns:
        批量推理结果
    """
    data = request.get_json()

    if not data or 'tasks' not in data:
        return jsonify({
            "success": False,
            "error": "缺少 tasks 字段"
        }), 400

    tasks = data['tasks']
    results = []

    service = get_sam3d_service()

    for i, task in enumerate(tasks):
        image_path = task.get('image_path')
        if not image_path or not os.path.exists(image_path):
            results.append({
                "index": i,
                "success": False,
                "error": f"图像文件不存在: {image_path}"
            })
            continue

        gt_path = task.get('gt_path')
        output_path = task.get('output_path')

        result = service.infer(
            img_path=image_path,
            gt_path=gt_path,
            output_path=output_path
        )
        result['index'] = i
        results.append(result)

    success_count = sum(1 for r in results if r.get('success', False))

    return jsonify({
        "success": True,
        "total": len(tasks),
        "success_count": success_count,
        "failed_count": len(tasks) - success_count,
        "results": results
    })


@sam3d_bp.route('/setup', methods=['POST'])
@handle_errors
def setup_model():
    """
    初始化/重置模型

    Request JSON (optional):
    {
        "checkpoint_path": "/path/to/checkpoint.pth"
    }

    Returns:
        设置结果
    """
    global _sam3d_service

    data = request.get_json() or {}

    checkpoint_path = data.get('checkpoint_path')

    from services.sam3d_service import SAM3DInferenceService
    _sam3d_service = SAM3DInferenceService(checkpoint_path=checkpoint_path)
    success = _sam3d_service.setup()

    return jsonify({
        "success": success,
        "model_loaded": _sam3d_service.model is not None,
        "device": str(_sam3d_service.device) if _sam3d_service.device else None,
        "checkpoint_path": _sam3d_service.checkpoint_path
    })
