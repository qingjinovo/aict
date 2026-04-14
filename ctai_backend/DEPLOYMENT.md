# SAM-Med3D 医学影像诊断平台 - 部署指南

## 目录

1. [系统概述](#系统概述)
2. [环境要求](#环境要求)
3. [项目结构](#项目结构)
4. [本地部署](#本地部署)
5. [配置说明](#配置说明)
6. [运行测试](#运行测试)
7. [SAM3D 模型集成](#sam3d-模型集成)
8. [API文档](#api文档)

## 系统概述

SAM-Med3D 是一个医学影像诊断平台，支持：

- 患者 CT 图像上传
- AI 辅助图像分割（SAM-Med3D 模型）
- 医生标注与诊断
- 医患消息沟通
- 实时进度跟踪
- NIfTI 格式支持与 HU 值转换
- DICOM-SR 兼容标注导出

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.9+ | 主应用运行环境 |
| Conda | 4.0+ | SAM-Med3D 模型环境 |
| SQLite | 3.0+ | 默认数据库 |
| Node.js | 16+ | 可选，前端开发 |
| GPU | CUDA 11.8+ | 可选，模型推理加速 |

## 项目结构

```
ctai_backend/
├── app.py                      # Flask 主应用入口
├── config.py                   # 配置文件
├── extensions.py               # Flask 扩展初始化
├── requirements.txt            # Python 依赖
├── environment.yml             # Conda 环境配置 (sammed3d)
├── run_with_sammed3d.bat       # Windows 启动脚本
│
├── models/                     # 数据模型
│   ├── __init__.py
│   ├── user.py                 # 用户模型
│   ├── ct_image.py             # CT 图像模型
│   ├── annotation.py           # 标注模型
│   └── progress.py             # 进度/消息模型
│
├── routes/                     # 路由控制器
│   ├── __init__.py
│   ├── auth.py                 # 认证路由
│   ├── doctor.py               # 医生端路由
│   ├── patient.py              # 患者端路由
│   ├── api.py                  # REST API
│   ├── annotation_api.py       # 标注 API
│   └── sam3d_api.py           # SAM3D 模型 API
│
├── services/                   # 业务逻辑服务
│   ├── __init__.py
│   ├── nifti_service.py        # NIfTI 解析服务
│   ├── annotation_service.py   # 标注服务
│   ├── sam3d_service.py        # SAM3D 模型推理服务
│   ├── file_upload_service.py  # 文件上传服务
│   ├── notification_service.py # 通知服务
│   └── socketio_events.py     # WebSocket 事件
│
├── utils/                      # 工具函数
│   ├── __init__.py
│   └── medical_image_utils.py  # HU 转换、窗宽窗位
│
├── static/                     # 静态资源
│   ├── css/
│   │   ├── base.css            # 基础样式
│   │   └── ct/
│   │       └── ct-viewer.css   # CT 查看器样式
│   ├── js/
│   │   └── ct/
│   │       ├── ctViewer.js          # CT 主视图组件
│   │       ├── annotationTool.js     # 标注工具
│   │       ├── apiClient.js          # API 客户端
│   │       ├── ctStore.js            # 状态管理
│   │       ├── niftiLoader.js        # NIfTI 加载器
│   │       ├── niftiMaskExporter.js  # NIfTI 掩码导出
│   │       └── windowingTool.js      # 窗宽窗位工具
│   └── uploads/
│       └── ct_images/           # 上传文件目录
│
├── templates/                  # HTML 模板
│   ├── base.html               # 基础模板
│   ├── login.html              # 登录页面
│   ├── role_selection.html     # 角色选择
│   ├── doctor/                 # 医生端模板
│   │   ├── dashboard.html
│   │   ├── annotate.html       # 标注页面
│   │   ├── confirm.html        # 确认报告
│   │   ├── processing.html      # AI 处理中
│   │   ├── upload.html
│   │   └── message_detail.html
│   └── patient/                # 患者端模板
│       ├── dashboard.html
│       ├── report.html         # 报告页面
│       ├── upload.html
│       ├── ai_chat.html
│       ├── message.html
│       ├── contact_doctor.html
│       ├── feedback.html
│       └── question_menu.html
│
├── tests/                      # 测试文件
│   ├── __init__.py
│   └── test_medical_imaging.py # 单元测试
│
└── data/                       # 数据目录
    └── ctai.db                 # SQLite 数据库
```

## 本地部署

### 步骤 1: 克隆或复制项目

```bash
cd ctai_backend
```

### 步骤 2: 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate

# Linux/macOS:
source venv/bin/activate
```

### 步骤 3: 安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 4: 初始化数据库

首次运行会自动创建 SQLite 数据库，并添加测试用户：

- 医生账号: 工号 `D001`，密码 `doctor123`
- 患者账号: 手机号 `13900000001`（首次登录自动创建）

### 步骤 5: 运行应用

```bash
python app.py
```

应用将在 `http://localhost:5000` 启动。

### SAM3D 模型环境（可选）

如需使用 AI 分割功能：

```bash
# 使用提供的启动脚本（Windows）
run_with_sammed3d.bat

# 或手动激活 conda 环境
conda activate sammed3d
python app.py
```

## 配置说明

### 环境变量（可选）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SECRET_KEY` | Flask 密钥 | 内置默认值 |
| `DATABASE_URL` | 数据库 URL | SQLite 本地文件 |
| `JWT_SECRET_KEY` | JWT 密钥 | 内置默认值 |
| `SAM3D_MODEL_PATH` | SAM3D 模型路径 | `D:/Study/Project/JSJDS/demo/Model/best-epoch224-loss0.7188.pth` |
| `SAM3D_CODE_PATH` | SAM3D 代码路径 | `D:/Study/Github/SAM-Med3D` |

### 配置文件

编辑 `config.py` 修改以下设置：

```python
class Config:
    # 上传文件大小限制 (100MB)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    # 支持的文件格式
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'dcm', 'nifti', 'nii', 'gz'}
```

## 运行测试

### 单元测试

```bash
python tests/test_medical_imaging.py
```

### 登录测试

1. 打开浏览器访问 `http://localhost:5000`
2. 选择角色（医生/患者）
3. 使用测试账号登录

### 完整流程测试

1. **患者上传 CT 图像**
   - 使用患者账号登录
   - 点击"上传 CT 图像"
   - 选择文件并填写检查部位
   - 提交上传

2. **医生处理**
   - 使用医生账号登录
   - 在仪表盘看到新上传的图像
   - 点击"编辑"进入标注页面
   - 调用 AI 模型进行分析
   - 审核并确认报告

3. **患者查看**
   - 患者登录后可在仪表盘看到最新报告
   - 点击报告查看详情
   - 可通过消息功能联系医生

## SAM3D 模型集成

### 环境配置

**Conda 环境:** `sammed3d`

**激活方式:**
```bash
conda activate sammed3d
```

### 接口说明

模型服务需要实现以下 API 端点：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/sam3d/health` | GET | 健康检查 |
| `/api/sam3d/model-info` | GET | 获取模型信息 |
| `/api/sam3d/infer` | POST | 执行推理 |
| `/api/sam3d/infer-simple` | POST | 简化推理 |
| `/api/sam3d/batch-infer` | POST | 批量推理 |
| `/api/sam3d/setup` | POST | 初始化模型 |

### 请求格式

```json
POST /api/sam3d/infer
{
    "image_path": "/path/to/image.nii.gz",
    "gt_path": "/path/to/gt.nii.gz",
    "output_path": "/path/to/output.nii.gz",
    "num_clicks": 1,
    "crop_size": 128,
    "target_spacing": [1.5, 1.5, 1.5]
}
```

### 响应格式

```json
{
    "success": true,
    "output_path": "/path/to/output.nii.gz",
    "num_categories": 3,
    "processing_time": 12.5,
    "model_version": "SAM-Med3D"
}
```

### 简化推理

无需标注文件，使用图像中心点作为提示：

```json
POST /api/sam3d/infer-simple
{
    "image_path": "/path/to/image.nii.gz",
    "center_point": [64, 64, 64]
}
```

## API 文档

### 认证相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 角色选择页面 |
| `/login` | GET/POST | 登录 |
| `/logout` | GET | 登出 |

### 患者端

| 端点 | 方法 | 说明 |
|------|------|------|
| `/patient/dashboard` | GET | 患者仪表盘 |
| `/patient/upload` | GET/POST | 上传 CT 图像 |
| `/patient/report/<id>` | GET | 查看报告 |
| `/patient/question-menu` | GET | 问题菜单 |
| `/patient/ai-chat` | GET | AI 咨询 |
| `/patient/message/<id>` | GET/POST | 联系医生 |
| `/patient/contact-doctor` | GET | 联系我们 |
| `/patient/feedback/<id>` | GET/POST | 满意度反馈 |

### 医生端

| 端点 | 方法 | 说明 |
|------|------|------|
| `/doctor/dashboard` | GET | 医生仪表盘 |
| `/doctor/upload` | GET | 上传 CT（医生） |
| `/doctor/processing/<id>` | GET | AI 处理中 |
| `/doctor/annotate/<id>` | GET | 标注工具 |
| `/doctor/confirm/<id>` | GET/POST | 确认报告 |
| `/doctor/message/<id>` | GET | 消息详情 |

### REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ct-images` | POST | 上传 CT 图像 |
| `/api/ct-images/<id>` | GET | 获取 CT 图像信息 |
| `/api/ct-images/<id>/progress` | GET | 获取处理进度 |
| `/api/ct-images/<id>/annotations` | GET/POST | 获取/添加标注 |
| `/api/annotations/<id>` | PUT/DELETE | 修改/删除标注 |
| `/api/ct-images/<id>/call-model` | POST | 调用 AI 模型 |
| `/api/messages` | GET/POST | 获取/发送消息 |
| `/api/notifications` | GET | 获取通知 |
| `/api/model/info` | GET | 获取模型信息 |

### 标注 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/annotation/sets` | GET | 获取所有标注集 |
| `/api/annotation/sets/<id>` | GET | 获取标注集详情 |
| `/api/annotation/sets` | POST | 创建标注集 |
| `/api/annotation/sets/<id>` | DELETE | 删除标注集 |
| `/api/annotation/sets/<id>/annotations` | POST | 创建标注 |
| `/api/annotation/sets/<id>/annotations/<aid>` | PUT | 更新标注 |
| `/api/annotation/sets/<id>/annotations/<aid>` | DELETE | 删除标注 |
| `/api/annotation/sets/<id>/annotations/<aid>/confirm` | POST | 确认标注 |
| `/api/annotation/sets/<id>/slices/<n>` | GET | 按切片获取标注 |
| `/api/annotation/sets/<id>/export` | GET | 导出标注 |

### SAM3D 模型 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/sam3d/health` | GET | 健康检查 |
| `/api/sam3d/model-info` | GET | 获取模型信息 |
| `/api/sam3d/infer` | POST | 执行推理 |
| `/api/sam3d/infer-simple` | POST | 简化推理 |
| `/api/sam3d/batch-infer` | POST | 批量推理 |
| `/api/sam3d/setup` | POST | 初始化模型 |

## WebSocket 事件

平台使用 Socket.IO 实现实时功能：

| 事件名 | 方向 | 说明 |
|--------|------|------|
| `connect/disconnect` | 客户端-服务端 | 连接管理 |
| `join_ct_room` | 客户端-服务端 | 加入 CT 房间 |
| `leave_ct_room` | 客户端-服务端 | 离开 CT 房间 |
| `send_message` | 双向 | 发送消息 |
| `new_message` | 服务端-客户端 | 新消息 |
| `progress_update` | 客户端-服务端 | 更新进度 |
| `progress_changed` | 服务端-客户端 | 进度变化 |
| `annotation_added/modified/deleted` | 双向 | 标注变更 |
| `call_model` | 客户端-服务端 | 调用模型 |
| `model_call_complete` | 服务端-客户端 | 模型完成 |

## 扩展部署

### 使用 MySQL/PostgreSQL

```python
# config.py
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://user:pass@localhost/ctai'
# 或
SQLALCHEMY_DATABASE_URI = 'postgresql://user:pass@localhost/ctai'
```

### 使用 Gunicorn

```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 app:app
```

### Nginx 反向代理

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## 故障排除

### 数据库错误

```bash
# 删除旧数据库重新初始化
rm data/ctai.db
python app.py
```

### 端口被占用

```bash
# 修改端口 (app.py)
app.run(host='0.0.0.0', port=5001, debug=True)
```

### 上传失败

检查 `static/uploads/ct_images` 目录权限

### SAM3D 模型加载失败

1. 确认 `sammed3d` conda 环境已激活
2. 确认模型文件路径正确
3. 检查 CUDA/GPU 是否可用

## 文档索引

| 文档 | 说明 |
|------|------|
| [README.md](./README.md) | 项目主文档 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 本文档，部署指南 |
| [SPEC.md](./SPEC.md) | 技术规格说明书 |
| [CT_INTEGRATION.md](./CT_INTEGRATION.md) | CT 功能集成文档 |
