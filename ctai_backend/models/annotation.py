"""
医学影像标注数据模型
支持 DICOM-SR 兼容的结构化标注存储
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
from datetime import datetime
import json
import uuid


class AnnotationType(Enum):
    """标注类型枚举 - 符合RADLEX/DENSE标准"""
    POINT = "point"
    LINE = "line"
    ANGLE = "angle"
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    BRUSH = "brush"
    ARROW = "arrow"


class AnnotationCategory(Enum):
    """标注类别枚举"""
    ANATOMY = "anatomy"
    LESION = "lesion"
    FINDING = "finding"
    AI_RESULT = "ai_result"
    MEASUREMENT = "measurement"


class SeverityLevel(Enum):
    """严重程度枚举"""
    NORMAL = "normal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowStatus(Enum):
    """工作流状态"""
    PRELIMINARY = "preliminary"
    CONFIRMED = "confirmed"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class Point2D:
    """2D坐标点"""
    x: float
    y: float

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict) -> 'Point2D':
        return cls(x=float(data['x']), y=float(data['y']))

    def distance_to(self, other: 'Point2D') -> float:
        """计算到另一点的欧几里得距离"""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass
class Point3D:
    """3D空间坐标点"""
    x: float
    y: float
    z: float
    slice_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"x": self.x, "y": self.y, "z": self.z}
        if self.slice_index is not None:
            result["slice_index"] = self.slice_index
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> 'Point3D':
        return cls(
            x=float(data['x']),
            y=float(data['y']),
            z=float(data['z']),
            slice_index=data.get('slice_index')
        )


@dataclass
class Measurement:
    """测量数据"""
    measurement_type: str
    value: float
    unit: str
    secondary_value: Optional[float] = None
    additional_params: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": self.measurement_type,
            "value": self.value,
            "unit": self.unit
        }
        if self.secondary_value is not None:
            result["secondary_value"] = self.secondary_value
        if self.additional_params:
            result.update(self.additional_params)
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> 'Measurement':
        return cls(
            measurement_type=data['type'],
            value=float(data['value']),
            unit=data['unit'],
            secondary_value=data.get('secondary_value'),
            additional_params={k: v for k, v in data.items()
                             if k not in ['type', 'value', 'unit', 'secondary_value']}
        )


@dataclass
class HUStatistics:
    """HU值统计"""
    mean: float = 0.0
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0
    median: float = 0.0
    percentile_25: float = 0.0
    percentile_75: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
            "median": self.median,
            "percentile_25": self.percentile_25,
            "percentile_75": self.percentile_75
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'HUStatistics':
        return cls(
            mean=float(data.get('mean', 0)),
            std=float(data.get('std', 0)),
            min=float(data.get('min', 0)),
            max=float(data.get('max', 0)),
            median=float(data.get('median', 0)),
            percentile_25=float(data.get('percentile_25', 0)),
            percentile_75=float(data.get('percentile_75', 0))
        )


@dataclass
class VisualAttributes:
    """可视化属性"""
    fill_color: Tuple[int, int, int, int] = (255, 230, 109, 100)
    stroke_color: Tuple[int, int, int, int] = (255, 230, 109, 255)
    stroke_width: int = 2
    visible: bool = True
    opacity: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_color": list(self.fill_color),
            "stroke_color": list(self.stroke_color),
            "stroke_width": self.stroke_width,
            "visible": self.visible,
            "opacity": self.opacity
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'VisualAttributes':
        return cls(
            fill_color=tuple(data.get('fill_color', [255, 230, 109, 100])),
            stroke_color=tuple(data.get('stroke_color', [255, 230, 109, 255])),
            stroke_width=int(data.get('stroke_width', 2)),
            visible=bool(data.get('visible', True)),
            opacity=float(data.get('opacity', 0.5))
        )


@dataclass
class GraphicData:
    """图形数据 - 支持多种标注类型"""
    annotation_type: AnnotationType
    points: List[Point2D] = field(default_factory=list)
    slice_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.annotation_type.value,
            "points": [p.to_dict() for p in self.points],
            "slice_index": self.slice_index
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GraphicData':
        return cls(
            annotation_type=AnnotationType(data['type']),
            points=[Point2D.from_dict(p) for p in data.get('points', [])],
            slice_index=data.get('slice_index')
        )

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """获取边界框 (min_x, min_y, max_x, max_y)"""
        if not self.points:
            return (0, 0, 0, 0)

        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def calculate_area(self) -> float:
        """计算多边形面积 (Shoelace公式)"""
        if self.annotation_type != AnnotationType.POLYGON or len(self.points) < 3:
            return 0.0

        n = len(self.points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.points[i].x * self.points[j].y
            area -= self.points[j].x * self.points[i].y

        return abs(area) / 2.0

    def calculate_perimeter(self) -> float:
        """计算周长"""
        if len(self.points) < 2:
            return 0.0

        perimeter = 0.0
        for i in range(len(self.points)):
            j = (i + 1) % len(self.points)
            perimeter += self.points[i].distance_to(self.points[j])

        return perimeter


@dataclass
class AnnotationCreator:
    """标注创建者信息"""
    user_id: str
    name: str
    role: str = "RADIOLOGIST"
    department: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role
        }
        if self.department:
            result["department"] = self.department
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> 'AnnotationCreator':
        return cls(
            user_id=data['user_id'],
            name=data['name'],
            role=data.get('role', 'RADIOLOGIST'),
            department=data.get('department')
        )


@dataclass
class Annotation:
    """
    标注数据完整模型

    支持点、线、多边形、矩形、椭圆等多种标注类型
    兼容 DICOM SR 标准格式
    """
    annotation_id: str = field(default_factory=lambda: f"anno_{uuid.uuid4().hex[:12]}")
    graphic_type: AnnotationType = AnnotationType.POLYGON
    category: AnnotationCategory = AnnotationCategory.FINDING

    label: str = ""
    description: str = ""

    graphic_data: Optional[GraphicData] = None

    measurement: Optional[Measurement] = None
    hu_statistics: Optional[HUStatistics] = None

    visual_attributes: VisualAttributes = field(default_factory=VisualAttributes)
    severity: SeverityLevel = SeverityLevel.NORMAL

    workflow_status: WorkflowStatus = WorkflowStatus.PRELIMINARY

    creator: Optional[AnnotationCreator] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    modified_at: Optional[str] = None
    modified_by: Optional[str] = None

    ct_image_id: Optional[str] = None
    series_instance_uid: Optional[str] = None
    sop_instance_uid: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "annotation_id": self.annotation_id,
            "graphic_type": self.graphic_type.value,
            "category": self.category.value,
            "label": self.label,
            "description": self.description,
            "severity": self.severity.value,
            "workflow_status": self.workflow_status.value,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "ct_image_id": self.ct_image_id
        }

        if self.graphic_data:
            result["graphic_data"] = self.graphic_data.to_dict()
        if self.measurement:
            result["measurement"] = self.measurement.to_dict()
        if self.hu_statistics:
            result["hu_statistics"] = self.hu_statistics.to_dict()
        if self.visual_attributes:
            result["visual_attributes"] = self.visual_attributes.to_dict()
        if self.creator:
            result["creator"] = self.creator.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: Dict) -> 'Annotation':
        """从字典创建标注对象"""
        annotation = cls(
            annotation_id=data.get('annotation_id', f"anno_{uuid.uuid4().hex[:12]}"),
            graphic_type=AnnotationType(data.get('graphic_type', 'polygon')),
            category=AnnotationCategory(data.get('category', 'finding')),
            label=data.get('label', ''),
            description=data.get('description', ''),
            severity=SeverityLevel(data.get('severity', 'normal')),
            workflow_status=WorkflowStatus(data.get('workflow_status', 'preliminary')),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            modified_at=data.get('modified_at'),
            ct_image_id=data.get('ct_image_id')
        )

        if 'graphic_data' in data and data['graphic_data']:
            annotation.graphic_data = GraphicData.from_dict(data['graphic_data'])
        if 'measurement' in data and data['measurement']:
            annotation.measurement = Measurement.from_dict(data['measurement'])
        if 'hu_statistics' in data and data['hu_statistics']:
            annotation.hu_statistics = HUStatistics.from_dict(data['hu_statistics'])
        if 'visual_attributes' in data and data['visual_attributes']:
            annotation.visual_attributes = VisualAttributes.from_dict(data['visual_attributes'])
        if 'creator' in data and data['creator']:
            annotation.creator = AnnotationCreator.from_dict(data['creator'])

        return annotation

    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'Annotation':
        """从JSON字符串反序列化"""
        return cls.from_dict(json.loads(json_str))

    def update_modified(self, user_id: str) -> None:
        """更新修改时间和修改者"""
        self.modified_at = datetime.utcnow().isoformat()
        self.modified_by = user_id
        if self.workflow_status == WorkflowStatus.CONFIRMED:
            self.workflow_status = WorkflowStatus.MODIFIED

    def confirm(self) -> None:
        """确认标注"""
        self.workflow_status = WorkflowStatus.CONFIRMED
        self.modified_at = datetime.utcnow().isoformat()

    def delete(self) -> None:
        """删除标注"""
        self.workflow_status = WorkflowStatus.DELETED
        self.modified_at = datetime.utcnow().isoformat()


@dataclass
class AnnotationSet:
    """
    标注集合

    包含一组相关的标注，用于管理标注集
    """
    annotation_set_id: str = field(default_factory=lambda: f"set_{uuid.uuid4().hex[:12]}")
    study_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None

    annotations: List[Annotation] = field(default_factory=list)

    created_by: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    modified_at: Optional[str] = None

    name: str = ""
    description: str = ""
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "annotation_set_id": self.annotation_set_id,
            "study_instance_uid": self.study_instance_uid,
            "series_instance_uid": self.series_instance_uid,
            "annotations": [a.to_dict() for a in self.annotations],
            "created_by": self.created_by,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "annotation_count": len(self.annotations)
        }

    def add_annotation(self, annotation: Annotation) -> None:
        """添加标注"""
        self.annotations.append(annotation)
        self.modified_at = datetime.utcnow().isoformat()

    def remove_annotation(self, annotation_id: str) -> bool:
        """移除标注"""
        for i, anno in enumerate(self.annotations):
            if anno.annotation_id == annotation_id:
                self.annotations.pop(i)
                self.modified_at = datetime.utcnow().isoformat()
                return True
        return False

    def get_annotation(self, annotation_id: str) -> Optional[Annotation]:
        """获取指定标注"""
        for anno in self.annotations:
            if anno.annotation_id == annotation_id:
                return anno
        return None

    def get_annotations_by_slice(self, slice_index: int) -> List[Annotation]:
        """获取指定切片的标注"""
        result = []
        for anno in self.annotations:
            if anno.graphic_data and anno.graphic_data.slice_index == slice_index:
                result.append(anno)
        return result

    def get_annotations_by_category(self, category: AnnotationCategory) -> List[Annotation]:
        """获取指定类别的标注"""
        return [a for a in self.annotations if a.category == category]

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'AnnotationSet':
        data = json.loads(json_str)
        annotations = [Annotation.from_dict(a) for a in data.get('annotations', [])]
        return cls(
            annotation_set_id=data.get('annotation_set_id', f"set_{uuid.uuid4().hex[:12]}"),
            study_instance_uid=data.get('study_instance_uid'),
            series_instance_uid=data.get('series_instance_uid'),
            annotations=annotations,
            created_by=data.get('created_by'),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            modified_at=data.get('modified_at'),
            name=data.get('name', ''),
            description=data.get('description', ''),
            version=data.get('version', 1)
        )


VISUAL_PRESETS = {
    "lung_nodule": {
        "fill_color": (255, 230, 109, 100),
        "stroke_color": (255, 230, 109, 255),
        "stroke_width": 2
    },
    "mediastinal": {
        "fill_color": (78, 205, 196, 80),
        "stroke_color": (78, 205, 196, 255),
        "stroke_width": 2
    },
    "bone": {
        "fill_color": (248, 249, 250, 100),
        "stroke_color": (200, 200, 200, 255),
        "stroke_width": 2
    },
    "ai_suspicious": {
        "fill_color": (255, 71, 87, 100),
        "stroke_color": (255, 71, 87, 255),
        "stroke_width": 3
    },
    "vessel": {
        "fill_color": (69, 183, 209, 100),
        "stroke_color": (69, 183, 209, 255),
        "stroke_width": 2
    }
}
