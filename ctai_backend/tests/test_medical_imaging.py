"""
医学影像标注系统 - 单元测试

测试覆盖范围:
1. HU值转换和窗宽窗位工具
2. NIfTI数据解析
3. 标注数据模型
4. 标注服务
"""

import unittest
import numpy as np
import tempfile
import json
import os
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.medical_image_utils import (
    HUConverter, WindowingTool, WindowPreset,
    WindowSettings, ImagePreprocessor, StatisticsCalculator,
    HUConversionError, WindowingError, PreprocessingError
)

from services.nifti_service import (
    NIfTILoader, NIfTIHeader, CTImageData,
    NIfTIFormatError, DataType
)

from models.annotation import (
    Annotation, AnnotationSet, AnnotationType, AnnotationCategory,
    SeverityLevel, WorkflowStatus, GraphicData, Measurement,
    HUStatistics, VisualAttributes, Point2D, Point3D,
    AnnotationCreator, VISUAL_PRESETS
)

from services.annotation_service import (
    AnnotationService,
    AnnotationServiceError,
    AnnotationNotFoundError,
    AnnotationValidationError
)


class TestHUConverter(unittest.TestCase):
    """测试 HU 值转换器"""

    def test_to_hu_basic(self):
        """测试基本HU转换"""
        pixel_values = np.array([0, 100, 200, 300, 400])
        hu_values = HUConverter.to_hu(pixel_values, slope=1.0, intercept=-1024)
        expected = np.array([-1024, -924, -824, -724, -624])
        np.testing.assert_array_almost_equal(hu_values, expected)

    def test_to_hu_custom_slope_intercept(self):
        """测试自定义斜率和截距"""
        pixel_values = np.array([100, 200, 300])
        hu_values = HUConverter.to_hu(pixel_values, slope=2.0, intercept=-500)
        expected = np.array([-300, -100, 100])
        np.testing.assert_array_almost_equal(hu_values, expected)

    def test_from_hu(self):
        """测试从HU值转换回像素值"""
        hu_values = np.array([-1024, -924, -824])
        pixel_values = HUConverter.from_hu(hu_values, slope=1.0, intercept=-1024)
        expected = np.array([0, 100, 200])
        np.testing.assert_array_almost_equal(pixel_values, expected)

    def test_get_tissue_range(self):
        """测试组织HU范围查询"""
        lung_range = HUConverter.get_tissue_range("lung")
        self.assertEqual(lung_range, (-1000, -400))

        bone_range = HUConverter.get_tissue_range("bone")
        self.assertEqual(bone_range, (400, 3000))


class TestWindowingTool(unittest.TestCase):
    """测试窗宽窗位工具"""

    def test_apply_windowing_basic(self):
        """测试基本窗宽窗位应用"""
        hu_array = np.array([-1000, -500, 0, 500, 1000], dtype=np.float32)
        result = WindowingTool.apply_windowing(hu_array, window_center=0, window_width=1000)
        expected_min = -500
        expected_max = 500
        self.assertGreaterEqual(result.min(), 0)
        self.assertLessEqual(result.max(), 255)

    def test_apply_preset_lung(self):
        """测试肺窗预设"""
        hu_array = np.full((10, 10), -800, dtype=np.float32)
        result = WindowingTool.apply_preset(hu_array, WindowPreset.LUNG)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.shape, (10, 10))

    def test_apply_windowing_invalid_width(self):
        """测试无效窗宽处理"""
        hu_array = np.array([0, 100, 200], dtype=np.float32)
        with self.assertRaises(ValueError):
            WindowingTool.apply_windowing(hu_array, window_center=0, window_width=0)

    def test_calculate_optimal_windowing(self):
        """测试自动窗宽窗位计算"""
        hu_array = np.random.randn(100, 100) * 200 + 0
        center, width = WindowingTool.calculate_optimal_windowing(hu_array)
        self.assertIsInstance(center, int)
        self.assertIsInstance(width, int)
        self.assertGreater(width, 0)


class TestStatisticsCalculator(unittest.TestCase):
    """测试统计计算器"""

    def test_calculate_roi_stats(self):
        """测试ROI统计计算"""
        image = np.random.randn(100, 100) * 50 + 0
        mask = np.zeros((100, 100), dtype=bool)
        mask[25:75, 25:75] = True

        stats = StatisticsCalculator.calculate_roi_stats(image, mask)

        self.assertGreater(stats['count'], 0)
        self.assertIn('mean', stats)
        self.assertIn('std', stats)
        self.assertIn('min', stats)
        self.assertIn('max', stats)

    def test_calculate_area(self):
        """测试面积计算"""
        mask = np.zeros((100, 100), dtype=bool)
        mask[10:50, 10:50] = True

        area = StatisticsCalculator.calculate_area(mask, pixel_spacing=(0.5, 0.5))
        expected_area = 40 * 40 * 0.5 * 0.5
        self.assertAlmostEqual(area, expected_area, places=2)

    def test_calculate_volume(self):
        """测试体积计算"""
        mask = np.zeros((50, 50, 20), dtype=bool)
        mask[10:40, 10:40, 5:15] = True

        volume = StatisticsCalculator.calculate_volume(
            mask,
            slice_thickness=2.5,
            pixel_spacing=(0.5, 0.5)
        )

        self.assertGreater(volume, 0)

    def test_calculate_roi_stats_empty_mask(self):
        """测试空掩码处理"""
        image = np.random.randn(100, 100)
        mask = np.zeros((100, 100), dtype=bool)

        stats = StatisticsCalculator.calculate_roi_stats(image, mask)

        self.assertEqual(stats['count'], 0)


class TestNIfTIHeader(unittest.TestCase):
    """测试 NIfTI 头信息"""

    def test_voxel_dims_property(self):
        """测试体素尺寸属性"""
        header = NIfTIHeader()
        header.pixel_dims = [0.0, 0.5, 0.5, 2.5, 0.0, 0.0, 0.0, 0.0]

        dims = header.voxel_dims
        self.assertEqual(dims, (0.5, 0.5, 2.5))

    def test_shape_property(self):
        """测试图像形状属性"""
        header = NIfTIHeader()
        header.dim = [3, 128, 128, 64, 1, 1, 1, 1]

        shape = header.shape
        self.assertEqual(shape, (128, 128, 64))

    def test_number_of_slices(self):
        """测试切片数量"""
        header = NIfTIHeader()
        header.dim = [3, 256, 256, 100, 1, 1, 1, 1]

        self.assertEqual(header.number_of_slices, 100)


class TestCTImageData(unittest.TestCase):
    """测试 CT 图像数据"""

    def test_get_slice(self):
        """测试获取切片"""
        header = NIfTIHeader()
        header.dim = [3, 64, 64, 32, 1, 1, 1, 1]
        header.pixel_dims = [0.0, 1.0, 1.0, 2.5, 0.0, 0.0, 0.0, 0.0]
        header.vox_offset = 352.0
        header.slope = 1.0
        header.inter = -1024.0
        header.datatype = DataType.FLOAT32.value
        header.bitpix = 32
        header.magic = 'ni1\x00'

        data = np.random.randn(64, 64, 32).astype(np.float32)
        ct_data = CTImageData(header=header, data=data)

        slice_0 = ct_data.get_slice(0)
        self.assertEqual(slice_0.shape, (64, 64))

    def test_shape_mismatch_raises_error(self):
        """测试形状不匹配时抛出错误"""
        header = NIfTIHeader()
        header.dim = [3, 64, 64, 32, 1, 1, 1, 1]

        data = np.random.randn(32, 32, 32)

        with self.assertRaises(NIfTIFormatError):
            CTImageData(header=header, data=data)


class TestPoint2D(unittest.TestCase):
    """测试2D坐标点"""

    def test_distance_to(self):
        """测试距离计算"""
        p1 = Point2D(x=0, y=0)
        p2 = Point2D(x=3, y=4)

        distance = p1.distance_to(p2)
        self.assertAlmostEqual(distance, 5.0, places=5)

    def test_to_from_dict(self):
        """测试字典转换"""
        point = Point2D(x=10.5, y=20.3)
        data = point.to_dict()

        restored = Point2D.from_dict(data)
        self.assertEqual(restored.x, point.x)
        self.assertEqual(restored.y, point.y)


class TestAnnotation(unittest.TestCase):
    """测试标注数据模型"""

    def test_create_annotation(self):
        """测试创建标注"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.POLYGON,
            label="肺部结节"
        )

        self.assertIsNotNone(annotation.annotation_id)
        self.assertEqual(annotation.graphic_type, AnnotationType.POLYGON)
        self.assertEqual(annotation.label, "肺部结节")

    def test_to_dict(self):
        """测试转换为字典"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.POINT,
            label="测试点"
        )

        data = annotation.to_dict()

        self.assertIn('annotation_id', data)
        self.assertIn('graphic_type', data)
        self.assertEqual(data['label'], "测试点")

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            'annotation_id': 'anno_test_001',
            'graphic_type': 'polygon',
            'label': '测试标注',
            'category': 'lesion',
            'severity': 'medium',
            'ct_image_id': 'img_001'
        }

        annotation = Annotation.from_dict(data)

        self.assertEqual(annotation.annotation_id, 'anno_test_001')
        self.assertEqual(annotation.graphic_type, AnnotationType.POLYGON)
        self.assertEqual(annotation.severity, SeverityLevel.MEDIUM)

    def test_update_modified(self):
        """测试修改时间更新"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.LINE
        )

        original_created = annotation.created_at
        annotation.update_modified(user_id="D001")

        self.assertIsNotNone(annotation.modified_at)
        self.assertEqual(annotation.modified_by, "D001")

    def test_confirm(self):
        """测试确认标注"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.POLYGON
        )

        annotation.confirm()

        self.assertEqual(annotation.workflow_status, WorkflowStatus.CONFIRMED)

    def test_json_serialization(self):
        """测试JSON序列化"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.RECTANGLE,
            label="测试矩形"
        )

        json_str = annotation.to_json()
        restored = Annotation.from_json(json_str)

        self.assertEqual(restored.annotation_id, annotation.annotation_id)
        self.assertEqual(restored.label, annotation.label)


class TestAnnotationSet(unittest.TestCase):
    """测试标注集合"""

    def setUp(self):
        self.annotation_set = AnnotationSet(
            annotation_set_id="set_001",
            name="测试标注集"
        )

    def test_add_annotation(self):
        """测试添加标注"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.POLYGON
        )

        self.annotation_set.add_annotation(annotation)

        self.assertEqual(len(self.annotation_set.annotations), 1)

    def test_remove_annotation(self):
        """测试移除标注"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.POLYGON
        )
        self.annotation_set.add_annotation(annotation)
        anno_id = annotation.annotation_id

        result = self.annotation_set.remove_annotation(anno_id)

        self.assertTrue(result)
        self.assertEqual(len(self.annotation_set.annotations), 0)

    def test_get_annotation(self):
        """测试获取指定标注"""
        annotation = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.ELLIPSE
        )
        self.annotation_set.add_annotation(annotation)

        found = self.annotation_set.get_annotation(annotation.annotation_id)

        self.assertIsNotNone(found)
        self.assertEqual(found.annotation_id, annotation.annotation_id)

    def test_get_annotations_by_slice(self):
        """测试按切片获取标注"""
        anno1 = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.POINT,
            graphic_data=GraphicData(
                annotation_type=AnnotationType.POINT,
                points=[Point2D(x=10, y=20)],
                slice_index=50
            )
        )
        anno2 = Annotation(
            ct_image_id="img_001",
            graphic_type=AnnotationType.POINT,
            graphic_data=GraphicData(
                annotation_type=AnnotationType.POINT,
                points=[Point2D(x=30, y=40)],
                slice_index=60
            )
        )

        self.annotation_set.add_annotation(anno1)
        self.annotation_set.add_annotation(anno2)

        slice_50 = self.annotation_set.get_annotations_by_slice(50)
        self.assertEqual(len(slice_50), 1)


class TestAnnotationService(unittest.TestCase):
    """测试标注服务"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.service = AnnotationService(storage_path=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_annotation(self):
        """测试创建标注"""
        annotation = self.service.create_annotation(
            ct_image_id="img_001",
            annotation_type=AnnotationType.POLYGON,
            points=[
                {"x": 100, "y": 100},
                {"x": 150, "y": 100},
                {"x": 150, "y": 150},
                {"x": 100, "y": 150}
            ],
            label="肺部结节",
            category=AnnotationCategory.LESION,
            severity=SeverityLevel.MEDIUM
        )

        self.assertIsNotNone(annotation.annotation_id)
        self.assertEqual(annotation.label, "肺部结节")

    def test_create_annotation_invalid_points(self):
        """测试无效点数量"""
        with self.assertRaises(AnnotationServiceError):
            self.service.create_annotation(
                ct_image_id="img_001",
                annotation_type=AnnotationType.POLYGON,
                points=[{"x": 100, "y": 100}],
                label="无效多边形"
            )

    def test_add_to_annotation_set(self):
        """测试添加标注到标注集"""
        annotation = self.service.create_annotation(
            ct_image_id="img_001",
            annotation_type=AnnotationType.POINT,
            points=[{"x": 50, "y": 50}],
            label="测试点"
        )

        annotation_set = self.service.add_annotation_to_set(
            annotation_set_id="set_001",
            annotation=annotation
        )

        self.assertEqual(len(annotation_set.annotations), 1)

    def test_get_annotation_set(self):
        """测试获取标注集"""
        annotation = self.service.create_annotation(
            ct_image_id="img_001",
            annotation_type=AnnotationType.LINE,
            points=[{"x": 0, "y": 0}, {"x": 100, "y": 100}],
            label="测试线"
        )

        self.service.add_annotation_to_set("set_002", annotation)
        retrieved = self.service.get_annotation_set("set_002")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.annotation_set_id, "set_002")

    def test_update_annotation(self):
        """测试更新标注"""
        annotation = self.service.create_annotation(
            ct_image_id="img_001",
            annotation_type=AnnotationType.RECTANGLE,
            points=[{"x": 10, "y": 10}, {"x": 50, "y": 50}],
            label="原始标签"
        )

        self.service.add_annotation_to_set("set_003", annotation)

        updated = self.service.update_annotation(
            annotation_set_id="set_003",
            annotation_id=annotation.annotation_id,
            updates={"label": "更新后的标签"}
        )

        self.assertEqual(updated.label, "更新后的标签")

    def test_delete_annotation(self):
        """测试删除标注"""
        annotation = self.service.create_annotation(
            ct_image_id="img_001",
            annotation_type=AnnotationType.POLYGON,
            points=[
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 100}
            ],
            label="待删除"
        )

        self.service.add_annotation_to_set("set_004", annotation)
        self.service.delete_annotation("set_004", annotation.annotation_id)

        annotation_set = self.service.get_annotation_set("set_004")
        deleted_anno = annotation_set.get_annotation(annotation.annotation_id)

        self.assertEqual(deleted_anno.workflow_status, WorkflowStatus.DELETED)

    def test_export_import_json(self):
        """测试JSON导出导入"""
        annotation = self.service.create_annotation(
            ct_image_id="img_export",
            annotation_type=AnnotationType.ELLIPSE,
            points=[{"x": 20, "y": 20}, {"x": 80, "y": 80}],
            label="导出测试"
        )

        self.service.add_annotation_to_set("set_export", annotation)

        json_path = os.path.join(self.temp_dir, "export_test.json")
        self.service.export_to_json(self.service.get_annotation_set("set_export"), json_path)

        imported = self.service.import_from_json(json_path)

        self.assertEqual(imported.annotation_set_id, "set_export")
        self.assertEqual(len(imported.annotations), 1)


class TestVisualPresets(unittest.TestCase):
    """测试可视化预设"""

    def test_presets_exist(self):
        """测试预设存在"""
        self.assertIn("lung_nodule", VISUAL_PRESETS)
        self.assertIn("bone", VISUAL_PRESETS)
        self.assertIn("ai_suspicious", VISUAL_PRESETS)

    def test_preset_structure(self):
        """测试预设结构"""
        for name, preset in VISUAL_PRESETS.items():
            self.assertIn("fill_color", preset)
            self.assertIn("stroke_color", preset)
            self.assertIn("stroke_width", preset)
            self.assertEqual(len(preset["fill_color"]), 4)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestHUConverter))
    suite.addTests(loader.loadTestsFromTestCase(TestWindowingTool))
    suite.addTests(loader.loadTestsFromTestCase(TestStatisticsCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestNIfTIHeader))
    suite.addTests(loader.loadTestsFromTestCase(TestCTImageData))
    suite.addTests(loader.loadTestsFromTestCase(TestPoint2D))
    suite.addTests(loader.loadTestsFromTestCase(TestAnnotation))
    suite.addTests(loader.loadTestsFromTestCase(TestAnnotationSet))
    suite.addTests(loader.loadTestsFromTestCase(TestAnnotationService))
    suite.addTests(loader.loadTestsFromTestCase(TestVisualPresets))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
