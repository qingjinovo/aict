"""
医学影像工具模块
提供 HU 值转换、窗宽窗位调整、图像预处理等核心功能
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WindowPreset(Enum):
    """窗宽窗位预设枚举 - 符合放射科诊断标准"""
    LUNG = ("肺窗", 1500, -600)
    MEDIASTINAL = ("纵隔窗", 400, 40)
    BONE = ("骨窗", 2000, 300)
    BRAIN = ("脑窗", 80, 40)
    ABDOMEN = ("腹窗", 400, 50)
    LIVER = ("肝脏窗", 150, 30)
    CUSTOM = ("自定义", 400, 40)

    def __init__(self, name_cn: str, width: int, center: int):
        self.name_cn = name_cn
        self.width = width
        self.center = center


@dataclass
class WindowSettings:
    """窗宽窗位设置"""
    center: int
    width: int
    preset_name: Optional[str] = None

    def get_min_value(self) -> int:
        """获取可见范围最小值"""
        return self.center - self.width // 2

    def get_max_value(self) -> int:
        """获取可见范围最大值"""
        return self.center + self.width // 2

    def to_dict(self) -> dict:
        return {
            "center": self.center,
            "width": self.width,
            "min": self.get_min_value(),
            "max": self.get_max_value(),
            "preset": self.preset_name
        }


class HUConverter:
    """
    Hounsfield Unit (HU) 转换器

    HU值是CT图像的标准化表示方式:
    - 空气: -1000 HU
    - 水: 0 HU
    - 骨骼: +1000 HU 或更高
    - 肺: -500 ~ -900 HU

    转换公式: HU = pixel_value * slope + intercept
    """

    HU_AIR = -1000
    HU_WATER = 0
    HU_BONE_MIN = 400
    HU_FAT = -100
    HU_MUSCLE = 40
    HU_BLOOD = 50

    DEFAULT_INTERCEPT = -1024
    DEFAULT_SLOPE = 1.0

    @staticmethod
    def to_hu(pixel_array: np.ndarray, slope: float = 1.0, intercept: float = -1024) -> np.ndarray:
        """
        将原始像素值转换为 HU 值

        Args:
            pixel_array: 原始像素数组
            slope: DICOM rescale slope (通常为1)
            intercept: DICOM rescale intercept (通常为-1024)

        Returns:
            HU值数组
        """
        try:
            return pixel_array.astype(np.float32) * slope + intercept
        except Exception as e:
            logger.error(f"HU转换失败: {e}")
            raise HUConversionError(f"无法转换像素值到HU: {e}")

    @staticmethod
    def from_hu(hu_array: np.ndarray, slope: float = 1.0, intercept: float = -1024) -> np.ndarray:
        """
        从 HU 值转换回原始像素值

        Args:
            hu_array: HU值数组
            slope: DICOM rescale slope
            intercept: DICOM rescale intercept

        Returns:
            原始像素值数组
        """
        try:
            if slope == 0:
                raise HUConversionError("斜率不能为零")
            return ((hu_array - intercept) / slope).astype(np.int16)
        except Exception as e:
            logger.error(f"从HU转换失败: {e}")
            raise HUConversionError(f"无法从HU转换: {e}")

    @staticmethod
    def get_tissue_range(tissue: str) -> Tuple[int, int]:
        """获取特定组织的HU值范围"""
        ranges = {
            "air": (-1200, -900),
            "lung": (-1000, -400),
            "fat": (-150, -50),
            "water": (-10, 10),
            "muscle": (20, 60),
            "blood": (30, 70),
            "liver": (40, 60),
            "bone": (400, 3000),
            "contrast": (100, 300),
        }
        return ranges.get(tissue.lower(), (0, 0))


class WindowingTool:
    """
    窗宽窗位调整工具

    窗宽窗位是CT图像显示的关键参数:
    - 窗宽 (Window Width): 控制对比度范围
    - 窗位 (Window Center): 控制显示的中心值
    - 可见范围: [center - width/2, center + width/2]
    """

    @staticmethod
    def apply_windowing(
        hu_array: np.ndarray,
        window_center: int,
        window_width: int,
        output_dtype: type = np.uint8
    ) -> np.ndarray:
        """
        应用窗宽窗位到 HU 数组

        Args:
            hu_array: HU值数组
            window_center: 窗位 (WL)
            window_width: 窗宽 (WW)
            output_dtype: 输出数据类型

        Returns:
            归一化后的数组 (0-255)
        """
        if window_width <= 0:
            raise ValueError(f"窗宽必须为正数, 实际值: {window_width}")

        try:
            min_value = window_center - window_width / 2
            max_value = window_center + window_width / 2

            clipped = np.clip(hu_array, min_value, max_value)
            normalized = ((clipped - min_value) / window_width * 255)

            return normalized.astype(output_dtype)

        except Exception as e:
            logger.error(f"窗宽窗位调整失败: {e}")
            raise WindowingError(f"无法应用窗宽窗位: {e}")

    @staticmethod
    def apply_preset(hu_array: np.ndarray, preset: WindowPreset) -> np.ndarray:
        """应用预设窗宽窗位"""
        return WindowingTool.apply_windowing(
            hu_array,
            preset.center,
            preset.width
        )

    @staticmethod
    def get_preset_by_name(name: str) -> Optional[WindowPreset]:
        """根据名称获取预设"""
        name_mapping = {
            "lung": WindowPreset.LUNG,
            "肺窗": WindowPreset.LUNG,
            "mediastinal": WindowPreset.MEDIASTINAL,
            "纵隔窗": WindowPreset.MEDIASTINAL,
            "bone": WindowPreset.BONE,
            "骨窗": WindowPreset.BONE,
            "brain": WindowPreset.BRAIN,
            "脑窗": WindowPreset.BRAIN,
            "abdomen": WindowPreset.ABDOMEN,
            "腹窗": WindowPreset.ABDOMEN,
            "liver": WindowPreset.LIVER,
            "肝脏窗": WindowPreset.LIVER,
        }
        return name_mapping.get(name.lower())

    @staticmethod
    def calculate_optimal_windowing(
        hu_array: np.ndarray,
        target_percentile: Tuple[float, float] = (5, 95)
    ) -> Tuple[int, int]:
        """
        基于图像直方图自动计算最佳窗宽窗位

        Args:
            hu_array: HU值数组
            target_percentile: 目标百分位 (默认5%-95%)

        Returns:
            (最佳窗位, 最佳窗宽)
        """
        try:
            p_low, p_high = target_percentile
            min_hu = np.percentile(hu_array, p_low)
            max_hu = np.percentile(hu_array, p_high)

            center = int((min_hu + max_hu) / 2)
            width = int(max_hu - min_hu)

            return center, max(width, 1)

        except Exception as e:
            logger.warning(f"自动窗宽计算失败，使用默认值: {e}")
            return 40, 400


class ImagePreprocessor:
    """
    医学图像预处理器

    提供标准化预处理流程:
    1. 归一化
    2. 重采样
    3. 标准化
    """

    @staticmethod
    def normalize(
        image: np.ndarray,
        method: str = "minmax"
    ) -> np.ndarray:
        """
        归一化图像

        Args:
            image: 输入图像
            method: 归一化方法 ("minmax", "zscore", "percentile")

        Returns:
            归一化后的图像
        """
        try:
            if method == "minmax":
                img_min = np.min(image)
                img_max = np.max(image)
                if img_max == img_min:
                    return np.zeros_like(image, dtype=np.float32)
                return (image - img_min) / (img_max - img_min)

            elif method == "zscore":
                mean = np.mean(image)
                std = np.std(image)
                if std == 0:
                    return image - mean
                return (image - mean) / std

            elif method == "percentile":
                p2 = np.percentile(image, 2)
                p98 = np.percentile(image, 98)
                if p98 == p2:
                    return np.zeros_like(image, dtype=np.float32)
                normalized = (image - p2) / (p98 - p2)
                return np.clip(normalized, 0, 1)

            else:
                raise ValueError(f"未知的归一化方法: {method}")

        except Exception as e:
            logger.error(f"图像归一化失败: {e}")
            raise PreprocessingError(f"归一化失败: {e}")

    @staticmethod
    def resample(
        image: np.ndarray,
        current_spacing: Tuple[float, float, float],
        target_spacing: Tuple[float, float, float],
        order: int = 1
    ) -> Tuple[np.ndarray, Tuple[float, float, float]]:
        """
        重采样图像到目标分辨率

        Args:
            image: 3D图像数组
            current_spacing: 当前体素间距 (mm)
            target_spacing: 目标体素间距 (mm)
            order: 插值阶数 (0: 最近邻, 1: 双线性, 3: 三次样条)

        Returns:
            (重采样后的图像, 新的形状)
        """
        try:
            from scipy.ndimage import zoom

            spacing_ratio = np.array(current_spacing) / np.array(target_spacing)
            new_shape = np.round(np.array(image.shape) * spacing_ratio).astype(int)

            resampled = zoom(image, spacing_ratio, order=order)

            return resampled, tuple(new_shape)

        except ImportError:
            logger.warning("scipy未安装，使用最近邻插值")
            raise PreprocessingError("需要scipy库支持重采样")
        except Exception as e:
            logger.error(f"图像重采样失败: {e}")
            raise PreprocessingError(f"重采样失败: {e}")

    @staticmethod
    def resize_2d(
        image: np.ndarray,
        target_size: Tuple[int, int],
        method: str = "bilinear"
    ) -> np.ndarray:
        """
        调整2D图像大小

        Args:
            image: 2D图像
            target_size: 目标尺寸 (height, width)
            method: 插值方法

        Returns:
            调整后的图像
        """
        try:
            from cv2 import resize

            interp_map = {
                "nearest": 0,
                "bilinear": 1,
                "bicubic": 2,
                "lanczos": 4
            }

            interp = interp_map.get(method.lower(), 1)
            return resize(image, target_size, interpolation=interp)

        except ImportError:
            logger.warning("OpenCV未安装，使用scipy")
            from scipy.ndimage import zoom
            h_ratio = target_size[0] / image.shape[0]
            w_ratio = target_size[1] / image.shape[1]
            return zoom(image, (h_ratio, w_ratio), order=1)
        except Exception as e:
            raise PreprocessingError(f"2D图像缩放失败: {e}")


class StatisticsCalculator:
    """
    图像统计计算器

    计算 ROI 区域的各种统计指标
    """

    @staticmethod
    def calculate_roi_stats(
        image: np.ndarray,
        mask: np.ndarray
    ) -> dict:
        """
        计算 ROI 区域的统计指标

        Args:
            image: HU值图像
            mask: 二值掩码 (True/False 或 0/1)

        Returns:
            统计指标字典
        """
        try:
            if mask.shape != image.shape:
                raise ValueError("掩码与图像形状不匹配")

            roi_values = image[mask]

            if len(roi_values) == 0:
                return {
                    "count": 0,
                    "mean": 0,
                    "std": 0,
                    "min": 0,
                    "max": 0,
                    "median": 0,
                    "percentile_25": 0,
                    "percentile_75": 0
                }

            return {
                "count": int(len(roi_values)),
                "mean": float(np.mean(roi_values)),
                "std": float(np.std(roi_values)),
                "min": float(np.min(roi_values)),
                "max": float(np.max(roi_values)),
                "median": float(np.median(roi_values)),
                "percentile_25": float(np.percentile(roi_values, 25)),
                "percentile_75": float(np.percentile(roi_values, 75)),
                "sum": float(np.sum(roi_values))
            }

        except Exception as e:
            logger.error(f"ROI统计计算失败: {e}")
            raise StatisticsError(f"无法计算统计指标: {e}")

    @staticmethod
    def calculate_area(
        mask: np.ndarray,
        pixel_spacing: Tuple[float, float]
    ) -> float:
        """
        计算2D区域面积

        Args:
            mask: 二值掩码
            pixel_spacing: 像素间距 (mm/pixel)

        Returns:
            面积 (mm²)
        """
        try:
            pixel_count = np.sum(mask)
            area_per_pixel = pixel_spacing[0] * pixel_spacing[1]
            return float(pixel_count * area_per_pixel)

        except Exception as e:
            logger.error(f"面积计算失败: {e}")
            raise StatisticsError(f"无法计算面积: {e}")

    @staticmethod
    def calculate_volume(
        mask: np.ndarray,
        slice_thickness: float,
        pixel_spacing: Tuple[float, float]
    ) -> float:
        """
        计算3D区域体积

        Args:
            mask: 3D二值掩码
            slice_thickness: 层厚 (mm)
            pixel_spacing: 像素间距 (mm/pixel)

        Returns:
            体积 (mm³)
        """
        try:
            voxel_count = np.sum(mask)
            voxel_volume = slice_thickness * pixel_spacing[0] * pixel_spacing[1]
            return float(voxel_count * voxel_volume)

        except Exception as e:
            logger.error(f"体积计算失败: {e}")
            raise StatisticsError(f"无法计算体积: {e}")


class HUConversionError(Exception):
    """HU值转换错误"""
    pass


class WindowingError(Exception):
    """窗宽窗位调整错误"""
    pass


class PreprocessingError(Exception):
    """图像预处理错误"""
    pass


class StatisticsError(Exception):
    """统计计算错误"""
    pass
