"""
医学影像标注 API 路由
提供标注的CRUD操作接口
"""

from flask import Blueprint, request, jsonify, g
from functools import wraps
import logging
from typing import Dict, Any

from services.annotation_service import (
    AnnotationService,
    AnnotationServiceError,
    AnnotationNotFoundError,
    AnnotationValidationError
)
from models.annotation import (
    AnnotationType, AnnotationCategory, SeverityLevel
)

logger = logging.getLogger(__name__)

annotation_bp = Blueprint('annotation', __name__, url_prefix='/api/annotation')

_annotation_service: AnnotationService = None


def get_annotation_service() -> AnnotationService:
    """获取标注服务单例"""
    global _annotation_service
    if _annotation_service is None:
        _annotation_service = AnnotationService()
    return _annotation_service


def handle_errors(f):
    """统一的错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AnnotationNotFoundError as e:
            logger.warning(f"资源未找到: {e}")
            return jsonify({"error": "NOT_FOUND", "message": str(e)}), 404
        except AnnotationValidationError as e:
            logger.warning(f"验证失败: {e}")
            return jsonify({"error": "VALIDATION_ERROR", "message": str(e)}), 400
        except AnnotationServiceError as e:
            logger.error(f"服务错误: {e}")
            return jsonify({"error": "SERVICE_ERROR", "message": str(e)}), 500
        except Exception as e:
            logger.exception(f"未知错误: {e}")
            return jsonify({"error": "INTERNAL_ERROR", "message": "服务器内部错误"}), 500
    return decorated_function


@annotation_bp.route('/sets', methods=['GET'])
@handle_errors
def list_annotation_sets():
    """
    获取所有标注集列表

    Returns:
        标注集ID列表
    """
    service = get_annotation_service()
    set_ids = service.get_all_annotation_sets()
    return jsonify({
        "success": True,
        "data": set_ids,
        "count": len(set_ids)
    })


@annotation_bp.route('/sets/<set_id>', methods=['GET'])
@handle_errors
def get_annotation_set(set_id: str):
    """
    获取指定标注集

    Args:
        set_id: 标注集ID

    Returns:
        标注集详情
    """
    service = get_annotation_service()
    annotation_set = service.get_annotation_set(set_id)

    if not annotation_set:
        raise AnnotationNotFoundError(f"标注集不存在: {set_id}")

    return jsonify({
        "success": True,
        "data": annotation_set.to_dict()
    })


@annotation_bp.route('/sets', methods=['POST'])
@handle_errors
def create_annotation_set():
    """
    创建新标注集

    Request Body:
        {
            "set_id": "optional_custom_id",
            "ct_image_id": "image_001",
            "series_uid": "series_xxx",
            "name": "标注集名称",
            "description": "描述"
        }

    Returns:
        创建的标注集
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "VALIDATION_ERROR", "message": "请求体不能为空"}), 400

    service = get_annotation_service()
    set_id = data.get('set_id', f"set_{set_id}")

    annotation_set = service.get_or_create_annotation_set(
        annotation_set_id=set_id,
        ct_image_id=data.get('ct_image_id'),
        series_uid=data.get('series_uid')
    )
    annotation_set.name = data.get('name', '')
    annotation_set.description = data.get('description', '')

    return jsonify({
        "success": True,
        "data": annotation_set.to_dict()
    }), 201


@annotation_bp.route('/sets/<set_id>', methods=['DELETE'])
@handle_errors
def delete_annotation_set(set_id: str):
    """
    删除标注集

    Args:
        set_id: 标注集ID

    Returns:
        删除结果
    """
    service = get_annotation_service()
    success = service.delete_annotation_set(set_id)

    return jsonify({
        "success": success,
        "message": f"标注集 {set_id} 已删除"
    })


@annotation_bp.route('/sets/<set_id>/annotations', methods=['POST'])
@handle_errors
def create_annotation(set_id: str):
    """
    创建新标注

    Args:
        set_id: 标注集ID

    Request Body:
        {
            "type": "polygon",
            "points": [{"x": 100, "y": 200}, ...],
            "label": "肺部结节",
            "category": "lesion",
            "severity": "medium",
            "slice_index": 50,
            "creator": {"user_id": "D001", "name": "医生"}
        }

    Returns:
        创建的标注
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "VALIDATION_ERROR", "message": "请求体不能为空"}), 400

    required_fields = ['type', 'points']
    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": "VALIDATION_ERROR",
                "message": f"缺少必需字段: {field}"
            }), 400

    service = get_annotation_service()

    annotation = service.create_annotation(
        ct_image_id=data.get('ct_image_id'),
        annotation_type=AnnotationType(data['type']),
        points=data['points'],
        label=data.get('label', ''),
        category=AnnotationCategory(data.get('category', 'finding')),
        severity=SeverityLevel(data.get('severity', 'normal')),
        creator=data.get('creator'),
        slice_index=data.get('slice_index'),
        measurement=data.get('measurement'),
        hu_stats=data.get('hu_statistics'),
        visual_preset=data.get('visual_preset')
    )

    annotation_set = service.add_annotation_to_set(
        annotation_set_id=set_id,
        annotation=annotation,
        ct_image_id=data.get('ct_image_id'),
        series_uid=data.get('series_uid')
    )

    return jsonify({
        "success": True,
        "data": annotation.to_dict(),
        "set": annotation_set.to_dict()
    }), 201


@annotation_bp.route('/sets/<set_id>/annotations/<anno_id>', methods=['GET'])
@handle_errors
def get_annotation(set_id: str, anno_id: str):
    """
    获取指定标注

    Args:
        set_id: 标注集ID
        anno_id: 标注ID

    Returns:
        标注详情
    """
    service = get_annotation_service()
    annotation_set = service.get_annotation_set(set_id)

    if not annotation_set:
        raise AnnotationNotFoundError(f"标注集不存在: {set_id}")

    annotation = annotation_set.get_annotation(anno_id)
    if not annotation:
        raise AnnotationNotFoundError(f"标注不存在: {anno_id}")

    return jsonify({
        "success": True,
        "data": annotation.to_dict()
    })


@annotation_bp.route('/sets/<set_id>/annotations/<anno_id>', methods=['PUT'])
@handle_errors
def update_annotation(set_id: str, anno_id: str):
    """
    更新标注

    Args:
        set_id: 标注集ID
        anno_id: 标注ID

    Request Body:
        {
            "label": "新标签",
            "points": [...],
            "severity": "high",
            "workflow_status": "confirmed"
        }

    Returns:
        更新后的标注
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "VALIDATION_ERROR", "message": "请求体不能为空"}), 400

    service = get_annotation_service()
    annotation = service.update_annotation(
        annotation_set_id=set_id,
        annotation_id=anno_id,
        updates=data
    )

    return jsonify({
        "success": True,
        "data": annotation.to_dict()
    })


@annotation_bp.route('/sets/<set_id>/annotations/<anno_id>', methods=['DELETE'])
@handle_errors
def delete_annotation(set_id: str, anno_id: str):
    """
    删除标注 (软删除)

    Args:
        set_id: 标注集ID
        anno_id: 标注ID

    Returns:
        删除结果
    """
    service = get_annotation_service()
    success = service.delete_annotation(set_id, anno_id)

    return jsonify({
        "success": success,
        "message": f"标注 {anno_id} 已删除"
    })


@annotation_bp.route('/sets/<set_id>/annotations/<anno_id>/confirm', methods=['POST'])
@handle_errors
def confirm_annotation(set_id: str, anno_id: str):
    """
    确认标注

    Args:
        set_id: 标注集ID
        anno_id: 标注ID

    Returns:
        确认后的标注
    """
    service = get_annotation_service()
    annotation = service.confirm_annotation(set_id, anno_id)

    return jsonify({
        "success": True,
        "data": annotation.to_dict()
    })


@annotation_bp.route('/sets/<set_id>/slices/<int:slice_index>', methods=['GET'])
@handle_errors
def get_annotations_by_slice(set_id: str, slice_index: int):
    """
    获取指定切片的标注

    Args:
        set_id: 标注集ID
        slice_index: 切片索引

    Returns:
        标注列表
    """
    service = get_annotation_service()
    annotations = service.get_annotations_by_slice(set_id, slice_index)

    return jsonify({
        "success": True,
        "data": [a.to_dict() for a in annotations],
        "count": len(annotations)
    })


@annotation_bp.route('/sets/<set_id>/export', methods=['GET'])
@handle_errors
def export_annotation_set(set_id: str):
    """
    导出标注集

    Query Params:
        format: json | dicom_sr (默认json)

    Returns:
        导出文件或JSON
    """
    export_format = request.args.get('format', 'json')
    service = get_annotation_service()
    annotation_set = service.get_annotation_set(set_id)

    if not annotation_set:
        raise AnnotationNotFoundError(f"标注集不存在: {set_id}")

    if export_format == 'dicom_sr':
        output_path = f"./data/exports/{set_id}_dicom_sr.xml"
        path = service.export_to_dicom_sr(annotation_set, output_path)
        return jsonify({
            "success": True,
            "message": "导出成功",
            "path": path
        })
    else:
        json_str = service.export_to_json(annotation_set)
        return jsonify({
            "success": True,
            "data": json.loads(json_str)
        })


@annotation_bp.route('/sets/<set_id>/import', methods=['POST'])
@handle_errors
def import_annotation_set(set_id: str):
    """
    导入标注集

    Request Body:
        JSON格式的标注数据

    Returns:
        导入结果
    """
    service = get_annotation_service()

    temp_path = f"./data/temp_import_{set_id}.json"

    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(request.get_json())

        annotation_set = service.import_from_json(temp_path)

        return jsonify({
            "success": True,
            "data": annotation_set.to_dict()
        }), 201

    finally:
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)


@annotation_bp.route('/measurement/calculate', methods=['POST'])
@handle_errors
def calculate_measurement():
    """
    计算标注测量值

    Request Body:
        {
            "annotation": {...},
            "pixel_spacing": [0.5, 0.5],
            "slice_thickness": 2.5
        }

    Returns:
        测量结果
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "VALIDATION_ERROR", "message": "请求体不能为空"}), 400

    from models.annotation import Annotation
    annotation = Annotation.from_dict(data['annotation'])
    pixel_spacing = tuple(data.get('pixel_spacing', [1.0, 1.0]))
    slice_thickness = data.get('slice_thickness')

    service = get_annotation_service()

    try:
        measurement = service.calculate_measurement(
            annotation, pixel_spacing, slice_thickness
        )

        return jsonify({
            "success": True,
            "data": measurement.to_dict()
        })

    except AnnotationValidationError as e:
        return jsonify({
            "error": "VALIDATION_ERROR",
            "message": str(e)
        }), 400


@annotation_bp.route('/presets', methods=['GET'])
@handle_errors
def get_visual_presets():
    """
    获取可视化预设

    Returns:
        预设列表
    """
    from models.annotation import VISUAL_PRESETS

    return jsonify({
        "success": True,
        "data": VISUAL_PRESETS
    })


@annotation_bp.route('/types', methods=['GET'])
@handle_errors
def get_annotation_types():
    """
    获取标注类型列表

    Returns:
        类型枚举列表
    """
    types = [
        {"value": t.value, "name": t.name}
        for t in AnnotationType
    ]

    return jsonify({
        "success": True,
        "data": types
    })


import json as json_lib
