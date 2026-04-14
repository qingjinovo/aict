# 后端系统 Bug 报告

**项目**: SAM-Med3D 医学影像诊断平台
**测试日期**: 2026-04-14
**测试人员**: AI Assistant
**测试环境**: Windows + Python 3.13

---

## 执行摘要

| 类别 | 数量 |
|------|------|
| 严重 (Critical) | 1 |
| 高 (High) | 2 |
| 中 (Medium) | 2 |
| 低 (Low) | 1 |

---

## 问题清单

### 问题 1: 标注 API 蓝图未注册 [严重]

**严重性**: HIGH
**状态**: 已修复

**描述**:
`annotation_bp` 蓝图已创建但未在 `app.py` 中注册，导致所有 `/api/annotation/*` 端点返回 404。

**影响范围**:
- `/api/annotation/sets`
- `/api/annotation/sets/<id>`
- `/api/annotation/sets/<id>/annotations`
- 所有标注 CRUD 操作

**修复步骤**:
```python
# app.py 中添加
from routes.annotation_api import annotation_bp

# 在 register_blueprint 部分添加
app.register_blueprint(annotation_bp)
```

**验证**:
```bash
curl http://localhost:5000/api/annotation/sets
# 应返回 200 或空列表，而不是 404
```

---

### 问题 2: SAM3D API 缺少 torch 依赖 [高]

**严重性**: MEDIUM
**状态**: 已知限制

**描述**:
SAM3D API (`sam3d_service.py`) 导入了 `torch`、`torchio` 等深度学习库，但这些库未安装在默认 Python 环境中。

**影响范围**:
- `/api/sam3d/health`
- `/api/sam3d/model-info`
- `/api/sam3d/infer`
- `/api/sam3d/infer-simple`

**错误信息**:
```
ModuleNotFoundError: No module named 'torch'
```

**解决方案**:
SAM3D 模型需要在 `sammed3d` conda 环境中运行，该环境包含所有必需的深度学习依赖。

**Workaround**:
```bash
# 使用 sammed3d 环境
conda activate sammed3d
python app.py
```

---

### 问题 3: 缺少 JWT Token 刷新机制 [中]

**严重性**: MEDIUM
**状态**: 待实现

**描述**:
系统生成的 JWT Token 没有设置过期时间，虽然 `auth_service.py` 中有 `exp` 字段，但生成时使用了默认值。

**影响范围**:
- Token 长期有效可能导致安全风险

**建议修复**:
在 `generate_token` 函数中确保正确设置过期时间：
```python
def generate_token(user_id, role, expires_in=24):
    # expires_in 默认 24 小时
    # 确保 JWT 中的 exp 字段正确设置
```

---

### 问题 4: 标注集 ID 字段不匹配 [中]

**严重性**: MEDIUM
**状态**: 待验证

**描述**:
前端 API 客户端 (`api.js`) 使用 `annotationSetId`，而后端使用 `set_id`，可能导致数据映射问题。

**前端 (api.js)**:
```javascript
async createSet(data) {
    return API.post('/api/annotation/sets', data);
}
```

**后端 (annotation_api.py)**:
```python
annotation_set_id = data.get('set_id') or generate_id()
```

**建议**:
统一字段命名，建议使用 `annotation_set_id`。

---

### 问题 5: CORS 配置在生产环境可能过于宽松 [低]

**严重性**: LOW
**状态**: 待优化

**描述**:
开发环境配置 `CORS_ORIGINS = '*'` 允许所有来源，在生产环境中可能存在安全风险。

**当前配置**:
```python
# config.py
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')  # 生产环境应设置具体域名
```

**建议**:
```python
# 生产环境
CORS_ORIGINS = 'https://your-domain.com'
```

---

### 问题 6: 文件上传大小限制硬编码 [低]

**严重性**: LOW
**状态**: 已知

**描述**:
文件上传大小限制在 `config.py` 中硬编码为 100MB。

```python
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
```

**建议**:
允许通过环境变量配置：
```python
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_SIZE', 100 * 1024 * 1024))
```

---

## 测试结果详情

### API 端点注册测试

| 端点 | 状态 |
|------|------|
| `/api/auth/login` | ✅ PASS |
| `/api/auth/logout` | ✅ PASS |
| `/api/auth/me` | ✅ PASS |
| `/api/auth/verify` | ✅ PASS |
| `/api/ct-images` | ⚠️ GET 方法未单独注册 |
| `/api/annotation/sets` | ✅ PASS (修复后) |
| `/api/sam3d/*` | ✅ PASS |

### 认证流程测试

| 测试项 | 状态 |
|--------|------|
| 医生登录成功 | ✅ PASS |
| Token 验证成功 | ✅ PASS |
| 获取当前用户成功 | ✅ PASS |
| 患者登录成功 | ✅ PASS |
| 错误密码拒绝 | ✅ PASS |
| 缺少字段拒绝 | ✅ PASS |

### 数据库操作测试

| 测试项 | 状态 |
|--------|------|
| 用户创建 | ✅ PASS |
| 用户查询 | ✅ PASS |
| 用户更新 | ✅ PASS |
| 标注集创建 | ✅ PASS |
| 标注创建 | ✅ PASS |
| 事务回滚 | ✅ PASS |

### 安全机制测试

| 测试项 | 状态 |
|--------|------|
| CORS 头存在 | ✅ PASS |
| 敏感信息未暴露 | ✅ PASS |
| 过期 Token 拒绝 | ✅ PASS |
| SQL 注入拒绝 | ✅ PASS |

---

## 后续行动

| 优先级 | 行动项 | 负责人 |
|--------|--------|--------|
| P1 | 确认 annotation_bp 注册修复生效 | Dev |
| P2 | 在 sammed3d 环境中测试 SAM3D API | Dev |
| P3 | 实现 Token 自动刷新机制 | Dev |
| P4 | 统一前后端字段命名 | Dev |
| P5 | 生产环境 CORS 配置 | Ops |

---

## 测试命令

```bash
# 运行完整测试
cd d:\Study\Project\JSJDS\demo\ctai_backend
python tests/test_comprehensive.py

# 测试标注 API
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login_type":"doctor","employee_id":"D001","password":"doctor123"}'

# 使用返回的 token 测试标注 API
curl -X GET http://localhost:5000/api/annotation/sets \
  -H "Authorization: Bearer <token>"
```

---

## 附录: 测试脚本

完整的测试脚本位于: `tests/test_comprehensive.py`

```bash
# 运行特定测试
python -m pytest tests/test_comprehensive.py -v
```
