"""
NIfTI 医学影像解析服务
支持 .nii 和 .nii.gz 格式的CT图像加载、解析和预处理
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
import gzip
import struct
from enum import Enum

logger = logging.getLogger(__name__)


class NIfTIException(Exception):
    """NIfTI相关异常基类"""
    pass


class NIfTIFormatError(NIfTIException):
    """格式错误"""
    pass


class NIfTILoadError(NIfTIException):
    """加载错误"""
    pass


class DataType(Enum):
    """NIfTI数据类型枚举"""
    NONE = 0
    BINARY = 1
    UINT8 = 2
    INT16 = 4
    INT32 = 8
    FLOAT32 = 16
    COMPLEX64 = 32
    FLOAT64 = 64
    RGB24 = 128
    INT8 = 256
    UINT16 = 512
    UINT32 = 768
    INT64 = 1024
    UINT64 = 1280
    FLOAT128 = 1536
    COMPLEX128 = 1792
    COMPLEX256 = 2048
    RGBA32 = 2304


@dataclass
class NIfTIHeader:
    """
    NIfTI 头信息数据结构

    包含图像维数、像素间距、数据类型等关键元信息
    """
    sizeof_hdr: int = 0
    data_type: str = ""
    db_name: str = ""
    extents: int = 0
    session_error: int = 0
    regular: str = ""

    dim_info: int = 0
    dim: List[int] = field(default_factory=lambda: [0] * 8)

    intent_p1: float = 0.0
    intent_p2: float = 0.0
    intent_p3: float = 0.0
    intent_code: int = 0

    datatype: int = 16
    bitpix: int = 32
    slice_start: int = 0

    pixel_dims: List[float] = field(default_factory=lambda: [0.0] * 8)
    vox_offset: float = 0.0

    slope: float = 1.0
    inter: float = 0.0

    slice_duration: float = 0.0
    toffset: float = 0.0

    slice_code: int = 0
    xyzt_units: int = 3

    cal_max: float = 0.0
    cal_min: float = 0.0
    slice_code: int = 0
    xyzt_units: int = 3
    cal_max: float = 0.0
    cal_min: float = 0.0
    slice_duration: float = 0.0
    toffset: float = 0.0
    glmax: int = 0
    glmin: int = 0

    descrip: str = ""
    aux_file: str = ""

    qform_code: int = 0
    sform_code: int = 0

    quatern: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    qoffset: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    srow_x: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    srow_y: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    srow_z: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    intent_name: str = ""
    magic: str = ""

    @property
    def is_gzipped(self) -> bool:
        """检查是否为gzip压缩格式"""
        return self.magic in ['ni1', 'n+1']

    @property
    def voxel_dims(self) -> Tuple[float, float, float]:
        """获取体素尺寸 (x, y, z)"""
        return (
            float(self.pixel_dims[1]),
            float(self.pixel_dims[2]),
            float(self.pixel_dims[3])
        )

    @property
    def shape(self) -> Tuple[int, int, int]:
        """获取图像形状 (x, y, z)"""
        return (
            int(self.dim[1]),
            int(self.dim[2]),
            int(self.dim[3])
        )

    @property
    def number_of_slices(self) -> int:
        """获取切片数量"""
        return int(self.dim[3])

    @property
    def bytes_per_voxel(self) -> int:
        """获取每像素字节数"""
        return int(self.bitpix // 8)

    @property
    def total_voxels(self) -> int:
        """获取总体素数"""
        shape = self.shape
        return shape[0] * shape[1] * shape[2]

    @property
    def data_size(self) -> int:
        """获取数据大小（字节）"""
        return self.total_voxels * self.bytes_per_voxel


@dataclass
class CTImageData:
    """
    CT图像数据容器

    封装NIfTI图像数据及其元信息
    """
    header: NIfTIHeader
    data: np.ndarray

    patient_id: Optional[str] = None
    study_date: Optional[str] = None
    series_description: Optional[str] = None

    def __post_init__(self):
        """验证数据一致性"""
        if self.data.shape != self.header.shape:
            raise NIfTIFormatError(
                f"数据形状 {self.data.shape} 与头信息 {self.header.shape} 不匹配"
            )

    @property
    def shape(self) -> Tuple[int, int, int]:
        """图像形状"""
        return self.data.shape

    @property
    def spacing(self) -> Tuple[float, float, float]:
        """体素间距 (mm)"""
        return self.header.voxel_dims

    @property
    def dtype(self) -> np.dtype:
        """数据类型"""
        return self.data.dtype

    def get_slice(self, index: int) -> np.ndarray:
        """
        获取指定切片

        Args:
            index: 切片索引 (0-based)

        Returns:
            2D切片数组
        """
        if index < 0 or index >= self.header.number_of_slices:
            raise IndexError(f"切片索引超出范围: {index}")
        return self.data[:, :, index]

    def get_slices_range(
        self,
        start: int,
        end: int
    ) -> np.ndarray:
        """
        获取切片范围

        Args:
            start: 起始索引
            end: 结束索引

        Returns:
            3D数组
        """
        return self.data[:, :, start:end]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "shape": self.shape,
            "spacing": self.spacing,
            "dtype": str(self.data.dtype),
            "number_of_slices": self.header.number_of_slices,
            "patient_id": self.patient_id,
            "study_date": self.study_date,
            "series_description": self.series_description,
            "header": {
                "dim": self.header.dim,
                "pixel_dims": self.header.pixel_dims,
                "voxel_offset": self.header.vox_offset,
                "slope": self.header.slope,
                "inter": self.header.inter,
            }
        }


class NIfTILoader:
    """
    NIfTI 格式加载器

    支持标准NIfTI (.nii) 和压缩NIfTI (.nii.gz) 格式
    """

    NIFTI_MAGIC = b'ni1\x00'
    NIFTI_MAGIC2 = b'n+1\x00'

    HEADER_SIZE = 352
    _EXTENSION_SIZE = 4

    DTYPE_MAP = {
        DataType.UINT8: np.uint8,
        DataType.INT16: np.int16,
        DataType.INT32: np.int32,
        DataType.FLOAT32: np.float32,
        DataType.FLOAT64: np.float64,
        DataType.INT8: np.int8,
        DataType.UINT16: np.uint16,
        DataType.UINT32: np.uint32,
        DataType.INT64: np.int64,
        DataType.UINT64: np.uint64,
    }

    REVERSE_DTYPE_MAP = {v: k for k, v in DTYPE_MAP.items()}

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def load(self, file_path: str) -> CTImageData:
        """
        加载NIfTI文件

        Args:
            file_path: 文件路径 (.nii 或 .nii.gz)

        Returns:
            CTImageData对象

        Raises:
            NIfTILoadError: 加载失败
            NIfTIFormatError: 格式错误
        """
        path = Path(file_path)

        if not path.exists():
            raise NIfTILoadError(f"文件不存在: {file_path}")

        try:
            if path.suffix == '.gz':
                return self._load_gzipped(path)
            else:
                return self._load_standard(path)

        except NIfTIException:
            raise
        except Exception as e:
            raise NIfTILoadError(f"加载文件失败: {e}")

    def _load_gzipped(self, path: Path) -> CTImageData:
        """加载gzip压缩的NIfTI文件"""
        self.logger.info(f"加载gzip压缩文件: {path}")

        with gzip.open(path, 'rb') as f:
            header_bytes = f.read(self.HEADER_SIZE)

            if len(header_bytes) < self.HEADER_SIZE:
                raise NIfTIFormatError(f"头信息不完整: 读取 {len(header_bytes)} 字节")

            header = self._parse_header(header_bytes)

            f.seek(int(header.vox_offset))
            data = self._read_data(f, header)

        return CTImageData(header=header, data=data)

    def _load_standard(self, path: Path) -> CTImageData:
        """加载标准NIfTI文件"""
        self.logger.info(f"加载标准NIfTI文件: {path}")

        with open(path, 'rb') as f:
            header_bytes = f.read(self.HEADER_SIZE)

            if len(header_bytes) < self.HEADER_SIZE:
                raise NIfTIFormatError(f"头信息不完整: 读取 {len(header_bytes)} 字节")

            header = self._parse_header(header_bytes)

            f.seek(int(header.vox_offset))
            data = self._read_data(f, header)

        return CTImageData(header=header, data=data)

    def _parse_header(self, header_bytes: bytes) -> NIfTIHeader:
        """
        解析NIfTI头信息

        Args:
            header_bytes: 头信息字节数据

        Returns:
            NIfTIHeader对象
        """
        if len(header_bytes) < self.HEADER_SIZE:
            raise NIfTIFormatError("头信息字节长度不足")

        header = NIfTIHeader()

        header.sizeof_hdr = int.from_bytes(
            header_bytes[0:4], byteorder='little'
        )
        header.dim = list(struct.unpack(
            '<8h', header_bytes[40:56]
        ))
        header.pixel_dims = list(struct.unpack(
            '<8f', header_bytes[56:88]
        ))

        header.datatype = int.from_bytes(
            header_bytes[70:72], byteorder='little'
        )
        header.bitpix = int.from_bytes(
            header_bytes[72:76], byteorder='little'
        )
        header.vox_offset = struct.unpack('<f', header_bytes[108:112])[0]

        header.slope = struct.unpack('<f', header_bytes[124:128])[0]
        header.inter = struct.unpack('<f', header_bytes[128:132])[0]

        header.descrip = header_bytes[148:228].split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
        header.magic = header_bytes[344:348].decode('utf-8', errors='ignore')

        header.xyzt_units = int(header_bytes[304])

        return header

    def _read_data(self, file_handle, header: NIfTIHeader) -> np.ndarray:
        """
        从文件读取图像数据

        Args:
            file_handle: 文件句柄
            header: 解析后的头信息

        Returns:
            NumPy数组
        """
        dtype = self.DTYPE_MAP.get(
            DataType(header.datatype),
            np.float32
        )

        shape = tuple(int(d) for d in header.dim[1:4] if d > 0)

        expected_size = np.prod(shape) * (header.bitpix // 8)
        data_bytes = file_handle.read(int(expected_size))

        if len(data_bytes) < expected_size:
            raise NIfTIFormatError(
                f"数据不完整: 期望 {expected_size} 字节, 实际 {len(data_bytes)} 字节"
            )

        data = np.frombuffer(data_bytes, dtype=dtype).reshape(shape)

        if header.slope != 0 and header.slope != 1:
            data = data * header.slope + header.inter

        return data

    def save(
        self,
        ct_data: CTImageData,
        file_path: str,
        gzipped: bool = False
    ) -> None:
        """
        保存为NIfTI格式

        Args:
            ct_data: CTImageData对象
            file_path: 输出文件路径
            gzipped: 是否压缩
        """
        try:
            header_bytes = self._create_header(ct_data)

            if gzipped:
                with gzip.open(file_path, 'wb') as f:
                    f.write(header_bytes)
                    f.write(ct_data.data.tobytes())
            else:
                with open(file_path, 'wb') as f:
                    f.write(header_bytes)
                    f.write(ct_data.data.tobytes())

            self.logger.info(f"保存NIfTI文件成功: {file_path}")

        except Exception as e:
            raise NIfTILoadError(f"保存文件失败: {e}")

    def _create_header(self, ct_data: CTImageData) -> bytes:
        """创建NIfTI头信息字节"""
        header = bytearray(self.HEADER_SIZE)

        header[0:4] = (348).to_bytes(4, byteorder='little')

        dim = [len(ct_data.shape)] + list(ct_data.shape) + [1] * (7 - len(ct_data.shape))
        header[40:56] = struct.pack('<8h', *dim)

        pixel_dims = [0.0] + list(ct_data.spacing) + [0.0] * (7 - len(ct_data.spacing))
        header[56:88] = struct.pack('<8f', *pixel_dims)

        dtype_enum = self.REVERSE_DTYPE_MAP.get(ct_data.dtype, DataType.FLOAT32)
        header[70:72] = dtype_enum.value.to_bytes(2, byteorder='little')

        header[72:76] = (ct_data.dtype(0).itemsize * 8).to_bytes(4, byteorder='little')

        header[108:112] = struct.pack('<f', float(self.HEADER_SIZE + self._EXTENSION_SIZE))

        header[344:348] = self.NIFTI_MAGIC

        return bytes(header)


class NIfTIGenerator:
    """
    NIfTI 测试数据生成器

    用于生成模拟CT图像数据进行测试
    """

    @staticmethod
    def create_synthetic_ct(
        shape: Tuple[int, int, int] = (128, 128, 64),
        spacing: Tuple[float, float, float] = (1.0, 1.0, 2.5),
        num_spheres: int = 3
    ) -> CTImageData:
        """
        创建合成CT数据

        Args:
            shape: 图像形状 (x, y, z)
            spacing: 体素间距 (mm)
            num_spheres: 球形区域数量

        Returns:
            CTImageData对象
        """
        x, y, z = shape
        data = np.full(shape, -1000, dtype=np.float32)

        center_x, center_y = x // 2, y // 2

        for i in range(z):
            for px in range(x):
                for py in range(y):
                    dist = np.sqrt((px - center_x)**2 + (py - center_y)**2)
                    if dist < x // 4:
                        data[px, py, i] = -200

        header = NIfTIHeader()
        header.dim = [3, x, y, z, 1, 1, 1, 1]
        header.pixel_dims = [0.0] + list(spacing) + [0.0] * 4
        header.datatype = DataType.FLOAT32.value
        header.bitpix = 32
        header.vox_offset = float(NIfTILoader.HEADER_SIZE + NIfTILoader._EXTENSION_SIZE)
        header.slope = 1.0
        header.inter = -1024.0
        header.magic = 'ni1\x00'

        return CTImageData(
            header=header,
            data=data
        )
