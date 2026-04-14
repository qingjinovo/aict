"""
医学影像标注服务
提供标注的创建、更新、查询和导出功能
"""

import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from models.annotation import (
    Annotation, AnnotationSet, AnnotationType, AnnotationCategory,
    SeverityLevel, WorkflowStatus, GraphicData, Measurement,
    HUStatistics, VisualAttributes, Point2D, Point3D,
    AnnotationCreator, VISUAL_PRESETS
)
from utils.medical_image_utils import StatisticsCalculator, HUConverter

logger = logging.getLogger(__name__)


class AnnotationServiceError(Exception):
    """标注服务异常基类"""
    pass


class AnnotationNotFoundError(AnnotationServiceError):
    """标注未找到"""
    pass


class AnnotationValidationError(AnnotationServiceError):
    """标注验证失败"""
    pass


class AnnotationService:
    """
    标注服务

    提供标注的完整生命周期管理
    """

    def __init__(self, storage_path: str = "./data/annotations"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._annotation_cache: Dict[str, AnnotationSet] = {}
        logger.info(f"标注服务初始化完成, 存储路径: {self.storage_path}")

    def create_annotation(
        self,
        ct_image_id: str,
        annotation_type: AnnotationType,
        points: List[Dict[str, float]],
        label: str = "",
        category: AnnotationCategory = AnnotationCategory.FINDING,
        severity: SeverityLevel = SeverityLevel.NORMAL,
        creator: Optional[Dict] = None,
        slice_index: Optional[int] = None,
        measurement: Optional[Dict] = None,
        hu_stats: Optional[Dict] = None,
        visual_preset: Optional[str] = None,
        **kwargs
    ) -> Annotation:
        """
        创建新标注

        Args:
            ct_image_id: CT图像ID
            annotation_type: 标注类型
            points: 标注点坐标列表 [{"x": 1.0, "y": 2.0}, ...]
            label: 标注标签
            category: 标注类别
            severity: 严重程度
            creator: 创建者信息
            slice_index: 切片索引
            measurement: 测量数据
            hu_stats: HU统计
            visual_preset: 可视化预设名称

        Returns:
            创建的Annotation对象
        """
        try:
            self._validate_points(annotation_type, points)

            graphic_data = GraphicData(
                annotation_type=annotation_type,
                points=[Point2D(x=p['x'], y=p['y']) for p in points],
                slice_index=slice_index
            )

            visual_attrs = VisualAttributes()
            if visual_preset and visual_preset in VISUAL_PRESETS:
                preset = VISUAL_PRESETS[visual_preset]
                visual_attrs = VisualAttributes(
                    fill_color=tuple(preset['fill_color']),
                    stroke_color=tuple(preset['stroke_color']),
                    stroke_width=preset['stroke_width']
                )

            annotation = Annotation(
                ct_image_id=ct_image_id,
                graphic_type=annotation_type,
                category=category,
                label=label or self._generate_label(annotation_type),
                graphic_data=graphic_data,
                severity=severity,
                visual_attributes=visual_attrs,
                workflow_status=WorkflowStatus.PRELIMINARY
            )

            if measurement:
                annotation.measurement = Measurement(
                    measurement_type=measurement.get('type', 'area'),
                    value=measurement.get('value', 0),
                    unit=measurement.get('unit', 'mm²')
                )

            if hu_stats:
                annotation.hu_statistics = HUStatistics(
                    mean=hu_stats.get('mean', 0),
                    std=hu_stats.get('std', 0),
                    min=hu_stats.get('min', 0),
                    max=hu_stats.get('max', 0),
                    median=hu_stats.get('median', 0)
                )

            if creator:
                annotation.creator = AnnotationCreator(
                    user_id=creator.get('user_id', ''),
                    name=creator.get('name', ''),
                    role=creator.get('role', 'RADIOLOGIST'),
                    department=creator.get('department')
                )

            logger.info(f"创建标注成功: {annotation.annotation_id}, 类型: {annotation_type.value}")
            return annotation

        except Exception as e:
            logger.error(f"创建标注失败: {e}")
            raise AnnotationServiceError(f"无法创建标注: {e}")

    def add_annotation_to_set(
        self,
        annotation_set_id: str,
        annotation: Annotation,
        ct_image_id: Optional[str] = None,
        series_uid: Optional[str] = None
    ) -> AnnotationSet:
        """
        添加标注到标注集

        Args:
            annotation_set_id: 标注集ID
            annotation: 标注对象
            ct_image_id: CT图像ID
            series_uid: 系列UID

        Returns:
            更新后的AnnotationSet
        """
        annotation_set = self.get_or_create_annotation_set(
            annotation_set_id, ct_image_id, series_uid
        )

        annotation_set.add_annotation(annotation)
        self._annotation_cache[annotation_set_id] = annotation_set

        self._save_annotation_set(annotation_set)
        logger.info(f"标注 {annotation.annotation_id} 已添加到标注集 {annotation_set_id}")

        return annotation_set

    def get_or_create_annotation_set(
        self,
        annotation_set_id: str,
        ct_image_id: Optional[str] = None,
        series_uid: Optional[str] = None
    ) -> AnnotationSet:
        """获取或创建标注集"""
        if annotation_set_id in self._annotation_cache:
            return self._annotation_cache[annotation_set_id]

        file_path = self.storage_path / f"{annotation_set_id}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                annotation_set = AnnotationSet.from_json(json.dumps(data))
                self._annotation_cache[annotation_set_id] = annotation_set
                return annotation_set
            except Exception as e:
                logger.warning(f"读取标注集失败, 创建新的: {e}")

        annotation_set = AnnotationSet(
            annotation_set_id=annotation_set_id,
            series_instance_uid=series_uid,
            created_at=datetime.utcnow().isoformat()
        )
        self._annotation_cache[annotation_set_id] = annotation_set

        return annotation_set

    def get_annotation_set(self, annotation_set_id: str) -> Optional[AnnotationSet]:
        """获取标注集"""
        if annotation_set_id in self._annotation_cache:
            return self._annotation_cache[annotation_set_id]

        file_path = self.storage_path / f"{annotation_set_id}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                annotation_set = AnnotationSet.from_json(json.dumps(data))
                self._annotation_cache[annotation_set_id] = annotation_set
                return annotation_set
            except Exception as e:
                logger.error(f"读取标注集失败: {e}")

        return None

    def update_annotation(
        self,
        annotation_set_id: str,
        annotation_id: str,
        updates: Dict[str, Any]
    ) -> Annotation:
        """
        更新标注

        Args:
            annotation_set_id: 标注集ID
            annotation_id: 标注ID
            updates: 更新字段

        Returns:
            更新后的Annotation
        """
        annotation_set = self.get_annotation_set(annotation_set_id)
        if not annotation_set:
            raise AnnotationNotFoundError(f"标注集不存在: {annotation_set_id}")

        annotation = annotation_set.get_annotation(annotation_id)
        if not annotation:
            raise AnnotationNotFoundError(f"标注不存在: {annotation_id}")

        if 'label' in updates:
            annotation.label = updates['label']
        if 'description' in updates:
            annotation.description = updates['description']
        if 'severity' in updates:
            annotation.severity = SeverityLevel(updates['severity'])
        if 'points' in updates:
            self._validate_points(annotation.graphic_type, updates['points'])
            annotation.graphic_data.points = [
                Point2D(x=p['x'], y=p['y']) for p in updates['points']
            ]
        if 'workflow_status' in updates:
            annotation.workflow_status = WorkflowStatus(updates['workflow_status'])

        if updates.get('modified_by'):
            annotation.update_modified(updates['modified_by'])
        else:
            annotation.modified_at = datetime.utcnow().isoformat()

        annotation_set.modified_at = datetime.utcnow().isoformat()
        self._save_annotation_set(annotation_set)

        logger.info(f"标注已更新: {annotation_id}")
        return annotation

    def delete_annotation(
        self,
        annotation_set_id: str,
        annotation_id: str
    ) -> bool:
        """
        删除标注 (软删除)

        Returns:
            是否成功
        """
        annotation_set = self.get_annotation_set(annotation_set_id)
        if not annotation_set:
            raise AnnotationNotFoundError(f"标注集不存在: {annotation_set_id}")

        annotation = annotation_set.get_annotation(annotation_id)
        if not annotation:
            raise AnnotationNotFoundError(f"标注不存在: {annotation_id}")

        annotation.delete()
        annotation_set.modified_at = datetime.utcnow().isoformat()

        self._save_annotation_set(annotation_set)
        logger.info(f"标注已删除: {annotation_id}")

        return True

    def confirm_annotation(
        self,
        annotation_set_id: str,
        annotation_id: str
    ) -> Annotation:
        """确认标注"""
        annotation_set = self.get_annotation_set(annotation_set_id)
        if not annotation_set:
            raise AnnotationNotFoundError(f"标注集不存在: {annotation_set_id}")

        annotation = annotation_set.get_annotation(annotation_id)
        if not annotation:
            raise AnnotationNotFoundError(f"标注不存在: {annotation_id}")

        annotation.confirm()
        annotation_set.modified_at = datetime.utcnow().isoformat()

        self._save_annotation_set(annotation_set)
        logger.info(f"标注已确认: {annotation_id}")

        return annotation

    def get_annotations_by_slice(
        self,
        annotation_set_id: str,
        slice_index: int
    ) -> List[Annotation]:
        """获取指定切片的标注"""
        annotation_set = self.get_annotation_set(annotation_set_id)
        if not annotation_set:
            return []

        return annotation_set.get_annotations_by_slice(slice_index)

    def calculate_measurement(
        self,
        annotation: Annotation,
        pixel_spacing: Tuple[float, float],
        slice_thickness: Optional[float] = None
    ) -> Measurement:
        """
        计算标注的测量值

        Args:
            annotation: 标注对象
            pixel_spacing: 像素间距 (x, y) mm
            slice_thickness: 层厚 mm

        Returns:
            Measurement对象
        """
        if not annotation.graphic_data:
            raise AnnotationValidationError("标注缺少图形数据")

        graphic_type = annotation.graphic_type
        points = annotation.graphic_data.points

        if graphic_type == AnnotationType.LINE and len(points) >= 2:
            pixel_distance = points[0].distance_to(points[1])
            mm_distance = pixel_distance * ((pixel_spacing[0] + pixel_spacing[1]) / 2)

            return Measurement(
                measurement_type="distance",
                value=round(mm_distance, 2),
                unit="mm"
            )

        elif graphic_type == AnnotationType.POLYGON:
            area_pixels = graphic_type.calculate_area(pygson_data=annotation.graphic_data)
            mm_per_pixel = (pixel_spacing[0] * pixel_spacing[1]) ** 0.5
            area_mm2 = area_pixels * mm_per_pixel ** 2

            measurement = Measurement(
                measurement_type="area",
                value=round(area_mm2, 2),
                unit="mm²"
            )

            if len(points) >= 2:
                xs = [p.x for p in points]
                ys = [p.y for p in points]
                long_axis = max(xs) - min(xs)
                short_axis = max(ys) - min(ys)
                measurement.secondary_value = round(long_axis * mm_per_pixel, 2)
                measurement.additional_params = {
                    "long_axis_mm": round(long_axis * pixel_spacing[0], 2),
                    "short_axis_mm": round(short_axis * pixel_spacing[1], 2)
                }

            return measurement

        elif graphic_type == AnnotationType.RECTANGLE and len(points) >= 2:
            width = abs(points[1].x - points[0].x) * pixel_spacing[0]
            height = abs(points[1].y - points[0].y) * pixel_spacing[1]
            area_mm2 = width * height

            return Measurement(
                measurement_type="rectangle_area",
                value=round(area_mm2, 2),
                unit="mm²",
                secondary_value=round(max(width, height), 2)
            )

        elif graphic_type == AnnotationType.ELLIPSE and len(points) >= 2:
            rx = abs(points[1].x - points[0].x) / 2 * pixel_spacing[0]
            ry = abs(points[1].y - points[0].y) / 2 * pixel_spacing[1]
            area_mm2 = 3.14159 * rx * ry

            return Measurement(
                measurement_type="ellipse_area",
                value=round(area_mm2, 2),
                unit="mm²",
                secondary_value=round(max(rx, ry) * 2, 2)
            )

        raise AnnotationValidationError(f"不支持的标注类型: {graphic_type}")

    def export_to_dicom_sr(
        self,
        annotation_set: AnnotationSet,
        output_path: str
    ) -> str:
        """
        导出为DICOM SR格式

        Args:
            annotation_set: 标注集
            output_path: 输出路径

        Returns:
            导出的文件路径
        """
        try:
            dicom_sr_content = self._generate_dicom_sr(annotation_set)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(dicom_sr_content)

            logger.info(f"DICOM SR导出成功: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"DICOM SR导出失败: {e}")
            raise AnnotationServiceError(f"导出失败: {e}")

    def export_to_json(
        self,
        annotation_set: AnnotationSet,
        output_path: Optional[str] = None
    ) -> str:
        """
        导出为JSON格式

        Args:
            annotation_set: 标注集
            output_path: 输出路径 (可选)

        Returns:
            JSON字符串或文件路径
        """
        json_str = annotation_set.to_json()

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
            return output_path

        return json_str

    def import_from_json(self, json_path: str) -> AnnotationSet:
        """
        从JSON导入标注集

        Args:
            json_path: JSON文件路径

        Returns:
            AnnotationSet对象
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            annotation_set = AnnotationSet.from_json(json.dumps(data))
            self._annotation_cache[annotation_set.annotation_set_id] = annotation_set

            logger.info(f"从JSON导入标注集成功: {annotation_set.annotation_set_id}")
            return annotation_set

        except Exception as e:
            logger.error(f"JSON导入失败: {e}")
            raise AnnotationServiceError(f"导入失败: {e}")

    def _validate_points(
        self,
        annotation_type: AnnotationType,
        points: List[Dict[str, float]]
    ) -> None:
        """验证标注点"""
        if not points:
            raise AnnotationValidationError("标注点不能为空")

        min_points = {
            AnnotationType.POINT: 1,
            AnnotationType.LINE: 2,
            AnnotationType.ANGLE: 3,
            AnnotationType.RECTANGLE: 2,
            AnnotationType.ELLIPSE: 2,
            AnnotationType.POLYGON: 3,
            AnnotationType.BRUSH: 1,
            AnnotationType.ARROW: 2
        }

        required = min_points.get(annotation_type, 1)
        if len(points) < required:
            raise AnnotationValidationError(
                f"{annotation_type.value} 类型至少需要 {required} 个点"
            )

        for p in points:
            if 'x' not in p or 'y' not in p:
                raise AnnotationValidationError("每个点必须包含 x 和 y 坐标")

    def _generate_label(self, annotation_type: AnnotationType) -> str:
        """生成默认标签"""
        labels = {
            AnnotationType.POINT: "点标记",
            AnnotationType.LINE: "线段测量",
            AnnotationType.ANGLE: "角度测量",
            AnnotationType.RECTANGLE: "矩形区域",
            AnnotationType.ELLIPSE: "椭圆区域",
            AnnotationType.POLYGON: "多边形区域",
            AnnotationType.BRUSH: "涂抹区域",
            AnnotationType.ARROW: "箭头指示"
        }
        return labels.get(annotation_type, "未分类标注")

    def _save_annotation_set(self, annotation_set: AnnotationSet) -> None:
        """保存标注集到文件"""
        file_path = self.storage_path / f"{annotation_set.annotation_set_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(annotation_set.to_json())

    def _generate_dicom_sr(self, annotation_set: AnnotationSet) -> str:
        """生成DICOM SR格式内容"""
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<DicomSR>
    <Patient>
        <PatientID>{annotation_set.study_instance_uid or 'UNKNOWN'}</PatientID>
    </Patient>
    <Study>
        <StudyInstanceUID>{annotation_set.study_instance_uid or 'UNKNOWN'}</StudyInstanceUID>
    </Study>
    <Series>
        <SeriesInstanceUID>{annotation_set.series_instance_uid or 'UNKNOWN'}</SeriesInstanceUID>
    </Series>
    <AnnotationSet>
        <SetID>{annotation_set.annotation_set_id}</SetID>
        <SetNumber>{annotation_set.version}</SetNumber>
        <Annotations>
"""

        for anno in annotation_set.annotations:
            content += f"""            <Annotation>
                <Identifier>{anno.annotation_id}</Identifier>
                <GraphicType>{anno.graphic_type.value}</GraphicType>
                <Label>{anno.label}</Label>
                <Category>{anno.category.value}</Category>
                <Severity>{anno.severity.value}</Severity>
                <Status>{anno.workflow_status.value}</Status>
"""

            if anno.measurement:
                content += f"""                <Measurement>
                    <Type>{anno.measurement.measurement_type}</Type>
                    <Value>{anno.measurement.value}</Value>
                    <Unit>{anno.measurement.unit}</Unit>
                </Measurement>
"""

            if anno.graphic_data:
                content += """                <GraphicData>
"""
                for pt in anno.graphic_data.points:
                    content += f"""                    <Point x="{pt.x}" y="{pt.y}"/>
"""
                content += """                </GraphicData>
"""

            content += """            </Annotation>
"""

        content += """        </Annotations>
    </AnnotationSet>
</DicomSR>
"""
        return content

    def get_all_annotation_sets(self) -> List[str]:
        """获取所有标注集ID"""
        return [p.stem for p in self.storage_path.glob("*.json")]

    def delete_annotation_set(self, annotation_set_id: str) -> bool:
        """删除标注集"""
        file_path = self.storage_path / f"{annotation_set_id}.json"
        if file_path.exists():
            file_path.unlink()

        if annotation_set_id in self._annotation_cache:
            del self._annotation_cache[annotation_set_id]

        logger.info(f"标注集已删除: {annotation_set_id}")
        return True
