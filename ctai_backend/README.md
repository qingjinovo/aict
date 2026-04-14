# SAM-Med3D 医学影像诊断平台

基于 Flask 的医学 CT 影像诊断系统，集成 SAM-Med3D AI 模型，支持患者上传 CT 图像、医生标注诊断、AI 辅助分析。

## 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| **患者端** | CT 图像上传、报告查看、AI 咨询、医患沟通 |
| **医生端** | 图像标注、AI 模型调用、报告确认、消息回复 |
| **CT 图像处理** | NIfTI 格式支持、HU 值转换、窗宽窗位调整 |
| **AI 分割** | SAM-Med3D 模型集成、自动化分割推理 |
| **标注系统** | DICOM-SR 兼容、多类型标注、JSON/NIfTI 导出 |

### 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | Flask 3.0 |
| 数据库 | SQLite / MySQL / PostgreSQL |
| 前端 | 原生 HTML/CSS/JavaScript |
| 医学影像 | TorchIO, SimpleITK, nibabel |
| AI 模型 | SAM-Med3D (PyTorch) |
| 实时通信 | Flask-SocketIO |
| 环境管理 | Conda |

## 快速开始

### 环境要求

- Python 3.9+
- Conda (用于 SAM-Med3D 模型环境)
- Windows/Linux/macOS

### 安装步骤

#### 1. 克隆项目

```bash
cd ctai_backend
```

#### 2. 创建 Python 虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 初始化数据库

首次运行应用时会自动创建数据库并添加测试账号。

#### 5. 启动应用

```bash
python app.py
```

访问 `http://localhost:5000`

### SAM-Med3D 模型环境

如需使用 AI 分割功能，需要配置 SAM-Med3D conda 环境：

```bash
# 使用提供的环境配置文件
conda env create -f environment.yml

# 或激活现有环境
conda activate sammed3d

# 使用启动脚本（Windows）
run_with_sammed3d.bat
```

## 测试账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 医生 | 工号 `D001` | `doctor123` |
| 患者 | 手机号 `13900000001` | 任意验证码 |

## 项目结构

```
ctai_backend/
├── app.py                     # Flask 应用入口
├── config.py                  # 配置管理
├── extensions.py              # Flask 扩展初始化
├── requirements.txt            # Python 依赖
├── environment.yml            # Conda 环境配置
├── run_with_sammed3d.bat      # 模型环境启动脚本
│
├── models/                    # 数据模型
│   ├── user.py               # 用户模型
│   ├── ct_image.py           # CT 图像模型
│   ├── annotation.py         # 标注模型
│   └── progress.py            # 进度/消息模型
│
├── routes/                    # 路由
│   ├── auth.py               # 认证路由
│   ├── doctor.py             # 医生端路由
│   ├── patient.py            # 患者端路由
│   ├── api.py                # REST API
│   ├── annotation_api.py     # 标注 API
│   └── sam3d_api.py          # SAM3D 模型 API
│
├── services/                  # 业务逻辑
│   ├── nifti_service.py      # NIfTI 解析
│   ├── annotation_service.py  # 标注服务
│   ├── sam3d_service.py      # SAM3D 模型服务
│   └── ...
│
├── utils/                     # 工具函数
│   └── medical_image_utils.py # HU 转换、窗宽窗位
│
├── static/                    # 静态资源
│   ├── css/
│   │   ├── base.css          # 基础样式
│   │   └── ct/
│   │       └── ct-viewer.css # CT 查看器样式
│   ├── js/
│   │   └── ct/
│   │       ├── ctViewer.js    # CT 主视图组件
│   │       ├── annotationTool.js  # 标注工具
│   │       ├── niftiLoader.js     # NIfTI 加载器
│   │       └── ...
│   └── uploads/ct_images/     # 上传文件目录
│
└── templates/                 # HTML 模板
    ├── base.html
    ├── login.html
    ├── role_selection.html
    ├── doctor/
    │   ├── dashboard.html
    │   ├── annotate.html      # 标注页面
    │   └── ...
    └── patient/
        ├── dashboard.html
        ├── report.html        # 报告页面
        └── ...
```

## API 文档

### 标注 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/annotation/sets` | GET | 获取所有标注集 |
| `/api/annotation/sets/<id>` | GET | 获取标注集详情 |
| `/api/annotation/sets` | POST | 创建标注集 |
| `/api/annotation/sets/<id>/annotations` | POST | 创建标注 |
| `/api/annotation/sets/<id>/annotations/<aid>` | PUT | 更新标注 |
| `/api/annotation/sets/<id>/annotations/<aid>` | DELETE | 删除标注 |
| `/api/annotation/sets/<id>/export` | GET | 导出标注 |

### SAM3D 模型 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/sam3d/health` | GET | 健康检查 |
| `/api/sam3d/model-info` | GET | 获取模型信息 |
| `/api/sam3d/infer` | POST | 执行推理 |
| `/api/sam3d/infer-simple` | POST | 简化推理 |
| `/api/sam3d/batch-infer` | POST | 批量推理 |

详细 API 文档见 [CT_INTEGRATION.md](./CT_INTEGRATION.md) 和 [SPEC.md](./SPEC.md)。

## CT 图像处理

### HU 值与窗宽窗位

CT 图像使用 Hounsfield Unit (HU) 表示密度值：

| 组织 | HU 值范围 |
|------|-----------|
| 空气 | -1200 ~ -900 |
| 肺 | -1000 ~ -400 |
| 水 | -10 ~ 10 |
| 肌肉 | 20 ~ 60 |
| 骨骼 | 400 ~ 3000 |

预设窗宽窗位：

| 预设 | 窗宽 | 窗位 | 适用 |
|------|------|------|------|
| 肺窗 | 1500 | -600 | 肺部病变 |
| 纵隔窗 | 400 | 40 | 纵隔结构 |
| 骨窗 | 2000 | 300 | 骨骼 |
| 脑窗 | 80 | 40 | 脑组织 |

### NIfTI 格式

支持标准 `.nii` 和压缩 `.nii.gz` 格式的 CT 图像。

## 运行测试

### 单元测试

```bash
python tests/test_medical_imaging.py
```

### API 测试

```bash
# 健康检查
curl http://localhost:5000/api/sam3d/health

# 简化推理
curl -X POST http://localhost:5000/api/sam3d/infer-simple \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/image.nii.gz"}'
```

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | Flask 密钥 | 内置默认值 |
| `DATABASE_URL` | 数据库连接 | SQLite 本地文件 |
| `SAM3D_MODEL_PATH` | 模型文件路径 | `D:/Study/Project/JSJDS/demo/Model/best-epoch224-loss0.7188.pth` |
| `SAM3D_CODE_PATH` | SAM-Med3D 代码路径 | `D:/Study/Github/SAM-Med3D` |

### 上传配置

```python
# config.py
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {'nii', 'gz', 'nifti', 'dcm'}
```

## 部署

### 生产环境

1. 使用 Gunicorn + Eventlet：

```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 app:app
```

2. 配置反向代理（Nginx）

### Windows 服务

使用 `run_with_sammed3d.bat` 启动脚本可自动激活 conda 环境并运行应用。

## 文档

| 文档 | 说明 |
|------|------|
| [README.md](./README.md) | 项目主文档 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 部署指南 |
| [SPEC.md](./SPEC.md) | SAM3D 模型集成规格 |
| [CT_INTEGRATION.md](./CT_INTEGRATION.md) | CT 功能集成文档 |

## 许可证

本项目仅供研究和学习使用。
