# SAM-Med3D 医学影像诊断平台 - 技术规格说明书

## 1. 项目概述

### 1.1 项目简介

SAM-Med3D 是一个基于 Flask 的医学 CT 影像诊断平台，集成了 SAM-Med3D AI 模型进行自动化医学影像分割，支持患者上传 CT 图像、医生标注诊断、医患沟通等功能。

### 1.2 主要功能

| 模块 | 功能 |
|------|------|
| 患者端 | CT 图像上传、报告查看、AI 咨询、满意度反馈 |
| 医生端 | 图像标注、AI 模型调用、报告确认、消息回复 |
| CT 处理 | NIfTI 解析、HU 值转换、窗宽窗位调整、多平面重建 |
| AI 模型 | SAM-Med3D 分割推理、批量处理、结果导出 |
| 标注系统 | 多类型标注、DICOM-SR 兼容、JSON/NIfTI 导出 |
| 实时通信 | 进度推送、消息通知、标注同步 |

### 1.3 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    前端 (HTML/CSS/JS)                │
├─────────────────────────────────────────────────────┤
│                   Flask 应用层                        │
│  ┌──────────┬──────────┬──────────┬──────────┐     │
│  │ 认证路由  │ 医生路由  │ 患者路由  │  API路由  │     │
│  └──────────┴──────────┴──────────┴──────────┘     │
├─────────────────────────────────────────────────────┤
│                   业务逻辑层                          │
│  ┌──────────────┬──────────────┬──────────────┐    │
│  │ NIfTI服务    │ 标注服务     │ SAM3D服务    │    │
│  │ HU转换      │ 文件上传     │ SocketIO     │    │
│  └──────────────┴──────────────┴──────────────┘    │
├─────────────────────────────────────────────────────┤
│                   数据模型层                          │
│  ┌──────────┬──────────┬──────────┬──────────┐     │
│  │  User    │ CTImage  │Annotation│ Progress │     │
│  └──────────┴──────────┴──────────┴──────────┘     │
├─────────────────────────────────────────────────────┤
│              SAM-Med3D (Conda: sammed3d)            │
│         PyTorch + TorchIO + SimpleITK               │
└─────────────────────────────────────────────────────┘
```

## 2. 数据模型

### 2.1 用户模型 (User)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(50) | 用户名 |
| email | String(100) | 邮箱 |
| password_hash | String(255) | 密码哈希 |
| role | String(20) | 角色 (doctor/patient/admin) |
| phone | String(20) | 手机号 |
| full_name | String(100) | 姓名 |
| department | String(100) | 科室 (医生) |
| employee_id | String(50) | 工号 (医生) |
| created_at | DateTime | 创建时间 |

### 2.2 CT 图像模型 (CTImage)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(50) | 主键 (UUID) |
| patient_id | Integer | 患者 ID |
| filename | String(255) | 文件名 |
| file_path | String(500) | 文件路径 |
| file_size | Integer | 文件大小 |
| check_part | String(100) | 检查部位 |
| upload_time | DateTime | 上传时间 |
| processing_status | String(20) | 处理状态 |
| result_path | String(500) | AI 结果路径 |
| doctor_id | Integer | 医生 ID |
| annotation_set_id | String(50) | 标注集 ID |

### 2.3 标注模型 (Annotation)

详见 [CT_INTEGRATION.md](./CT_INTEGRATION.md#2-数据模型)

## 3. API 规格

### 3.1 认证 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/login` | GET/POST | 登录 |
| `/logout` | GET | 登出 |

### 3.2 患者 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/patient/dashboard` | GET | 仪表盘 |
| `/patient/upload` | GET/POST | 上传图像 |
| `/patient/report/<id>` | GET | 查看报告 |
| `/patient/ai-chat` | GET | AI 咨询 |
| `/patient/feedback/<id>` | GET/POST | 满意度反馈 |

### 3.3 医生 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/doctor/dashboard` | GET | 仪表盘 |
| `/doctor/processing/<id>` | GET | AI 处理中 |
| `/doctor/annotate/<id>` | GET | 标注工具 |
| `/doctor/confirm/<id>` | GET/POST | 确认报告 |

### 3.4 REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ct-images` | POST | 上传图像 |
| `/api/ct-images/<id>` | GET | 获取图像信息 |
| `/api/ct-images/<id>/progress` | GET | 获取进度 |
| `/api/messages` | GET/POST | 消息 |

### 3.5 标注 API

详见 [CT_INTEGRATION.md](./CT_INTEGRATION.md#2-api-端点规范)

### 3.6 SAM3D 模型 API

详见 [CT_INTEGRATION.md](./CT_INTEGRATION.md#sam3d-模型-api)

## 4. 前端组件

### 4.1 CT 查看器组件

| 组件 | 文件 | 说明 |
|------|------|------|
| 主视图 | ctViewer.js | CT 主视图组件 |
| 标注工具 | annotationTool.js | 标注绘制 |
| NIfTI 加载器 | niftiLoader.js | NIfTI 解析 |
| 窗宽窗位 | windowingTool.js | HU 转换 |
| 状态管理 | ctStore.js | Zustand 风格状态 |
| API 客户端 | apiClient.js | 后端通信 |
| NIfTI 掩码导出 | niftiMaskExporter.js | 导出分割掩码 |

### 4.2 响应式设计

- PC 端 (>= 1024px): 完整布局，侧边栏展开
- 平板端 (768px - 1023px): 简化布局，侧边栏收起
- 移动端 (< 768px): 堆叠布局，底部导航

## 5. 环境配置

### 5.1 Conda 环境

**环境名称:** `sammed3d`

**用途:** 运行 SAM-Med3D 深度学习模型推理（需要 GPU 支持）

**激活方式:**
```bash
conda activate sammed3d
```

### 5.2 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAM3D_MODEL_PATH` | 模型检查点路径 | `D:/Study/Project/JSJDS/demo/Model/best-epoch224-loss0.7188.pth` |
| `SAM3D_CODE_PATH` | SAM-Med3D 代码路径 | `D:/Study/Github/SAM-Med3D` |

## 6. 部署架构

### 6.1 开发环境

```
Flask (Debug) + SQLite + 原生 JS
```

### 6.2 生产环境

```
Nginx (反向代理) + Gunicorn/Eventlet + MySQL/PostgreSQL + Redis
```

### 6.3 启动方式

**Windows:**
```bash
run_with_sammed3d.bat
```

**Linux/macOS:**
```bash
conda activate sammed3d
python app.py
```

## 7. 测试规格

### 7.1 单元测试

| 测试文件 | 测试内容 |
|----------|----------|
| test_medical_imaging.py | HU 转换、窗宽窗位、NIfTI 解析、标注模型 |

### 7.2 测试账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 医生 | D001 | doctor123 |
| 患者 | 13900000001 | 任意验证码 |

## 8. 实现状态

| 模块 | 状态 | 说明 |
|------|------|------|
| Flask 应用框架 | ✅ 完成 | 完整的 MVC 架构 |
| 用户认证 | ✅ 完成 | 登录/登出/角色区分 |
| 患者端功能 | ✅ 完成 | 上传/查看报告/反馈 |
| 医生端功能 | ✅ 完成 | 标注/确认/消息 |
| NIfTI 解析 | ✅ 完成 | .nii/.nii.gz 支持 |
| HU 转换 | ✅ 完成 | 完整 HU 公式支持 |
| 窗宽窗位 | ✅ 完成 | 6 种预设 + 自定义 |
| 标注系统 | ✅ 完成 | CRUD + 导出 |
| SAM3D 模型集成 | ✅ 完成 | 推理服务 + API |
| 响应式设计 | ✅ 完成 | PC/平板/移动端适配 |
| 端到端测试 | ⏳ 待验证 | 需要实际 CT 数据 |

## 9. 后续优化计划

### 9.1 短期优化

1. 添加更多标注类型支持
2. 实现标注导入功能
3. 添加推理进度回调
4. 优化移动端用户体验

### 9.2 长期规划

1. 添加异步推理队列 (Celery/Redis)
2. WebSocket 实时进度推送
3. DICOM 格式完整支持
4. 云端部署支持
5. 多语言国际化

## 10. 文档索引

| 文档 | 说明 |
|------|------|
| [README.md](./README.md) | 项目主文档，快速开始 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 详细部署指南 |
| [SPEC.md](./SPEC.md) | 本文档，技术规格 |
| [CT_INTEGRATION.md](./CT_INTEGRATION.md) | CT 功能集成文档 |
