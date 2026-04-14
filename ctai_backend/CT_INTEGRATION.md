# CT 医学影像功能集成文档

## 1. 概述

本文档描述了 CT 医学影像功能与前端应用的集成方案，包括 API 端点规范、数据流设计、状态管理架构和 UI 组件要求。

### 1.1 集成范围

- NIfTI 格式 (.nii, .nii.gz) CT 图像加载与解析
- HU 值转换与窗宽窗位调整
- 多平面重建 ( MPR ) - 轴位、冠状位、矢状位
- 医学影像标注与管理
- DICOM-SR 格式导入/导出

### 1.2 技术栈

| 层级 | 技术选型 |
|------|----------|
| 前端框架 | 原生 JavaScript + HTML5 Canvas |
| 图像渲染 | Cornerstone.js 3.x |
| 状态管理 | Zustand |
| 后端框架 | Flask 3.0 |
| API 风格 | RESTful JSON |

---

## 2. API 端点规范

### 2.1 标注集管理

#### 创建标注集
```
POST /api/annotation/sets
```

**请求体:**
```json
{
    "set_id": "set_abc123",
    "ct_image_id": "img_001",
    "series_uid": "series_xxx",
    "name": "肺部结节标注",
    "description": "右肺上叶结节标注"
}
```

**响应 (201):**
```json
{
    "success": true,
    "data": {
        "annotation_set_id": "set_abc123",
        "ct_image_id": "img_001",
        "name": "肺部结节标注",
        "annotation_count": 0,
        "created_at": "2026-04-14T10:00:00"
    }
}
```

#### 获取标注集
```
GET /api/annotation/sets/<set_id>
```

**响应 (200):**
```json
{
    "success": true,
    "data": {
        "annotation_set_id": "set_abc123",
        "series_instance_uid": "series_xxx",
        "annotations": [...],
        "name": "肺部结节标注",
        "version": 1,
        "annotation_count": 5
    }
}
```

#### 删除标注集
```
DELETE /api/annotation/sets/<set_id>
```

**响应 (200):**
```json
{
    "success": true,
    "message": "标注集 set_abc123 已删除"
}
```

### 2.2 标注管理

#### 创建标注
```
POST /api/annotation/sets/<set_id>/annotations
```

**请求体:**
```json
{
    "type": "polygon",
    "points": [{"x": 100.5, "y": 200.3}, {"x": 150.2, "y": 180.7}, {"x": 180.1, "y": 220.4}],
    "label": "右肺上叶结节",
    "category": "lesion",
    "severity": "medium",
    "slice_index": 50,
    "ct_image_id": "img_001",
    "creator": {
        "user_id": "D001",
        "name": "张医生",
        "role": "RADIOLOGIST"
    },
    "visual_preset": "lung_nodule"
}
```

**响应 (201):**
```json
{
    "success": true,
    "data": {
        "annotation_id": "anno_xyz789",
        "graphic_type": "polygon",
        "label": "右肺上叶结节",
        "category": "lesion",
        "severity": "medium",
        "slice_index": 50,
        "visual_attributes": {
            "fill_color": [255, 230, 109, 100],
            "stroke_color": [255, 230, 109, 255],
            "stroke_width": 2
        },
        "created_at": "2026-04-14T10:05:00"
    }
}
```

#### 更新标注
```
PUT /api/annotation/sets/<set_id>/annotations/<anno_id>
```

**请求体:**
```json
{
    "label": "右肺上叶结节 (已确认)",
    "severity": "high",
    "workflow_status": "confirmed"
}
```

#### 删除标注 (软删除)
```
DELETE /api/annotation/sets/<set_id>/annotations/<anno_id>
```

#### 确认标注
```
POST /api/annotation/sets/<set_id>/annotations/<anno_id>/confirm
```

### 2.3 切片查询

#### 按切片获取标注
```
GET /api/annotation/sets/<set_id>/slices/<slice_index>
```

**响应 (200):**
```json
{
    "success": true,
    "data": [
        {
            "annotation_id": "anno_xyz789",
            "graphic_type": "polygon",
            "label": "右肺上叶结节",
            "slice_index": 50
        }
    ],
    "count": 1
}
```

### 2.4 导入/导出

#### 导出标注集
```
GET /api/annotation/sets/<set_id>/export?format=json
GET /api/annotation/sets/<set_id>/export?format=dicom_sr
```

**JSON 响应:**
```json
{
    "success": true,
    "data": {
        "annotation_set_id": "set_abc123",
        "annotations": [...]
    }
}
```

**DICOM-SR 响应:**
```json
{
    "success": true,
    "message": "导出成功",
    "path": "./data/exports/set_abc123_dicom_sr.xml"
}
```

#### 导入标注集
```
POST /api/annotation/sets/<set_id>/import
```

### 2.5 辅助端点

#### 获取可视化预设
```
GET /api/annotation/presets
```

**响应:**
```json
{
    "success": true,
    "data": {
        "lung_nodule": {
            "fill_color": [255, 230, 109, 100],
            "stroke_color": [255, 230, 109, 255],
            "stroke_width": 2
        },
        "ai_suspicious": {
            "fill_color": [255, 71, 87, 100],
            "stroke_color": [255, 71, 87, 255],
            "stroke_width": 3
        }
    }
}
```

#### 获取标注类型
```
GET /api/annotation/types
```

#### 计算测量值
```
POST /api/annotation/measurement/calculate
```

**请求体:**
```json
{
    "annotation": {...},
    "pixel_spacing": [0.5, 0.5],
    "slice_thickness": 2.5
}
```

---

## 3. 数据流设计

### 3.1 CT 图像加载流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 CT 加载流程                           │
└─────────────────────────────────────────────────────────────────┘

[用户上传 .nii 文件]
        │
        ▼
┌─────────────────┐
│  文件验证器      │  检查文件类型、大小、格式
│  FileValidator   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  NIfTI 解析器   │  解析头部信息、提取元数据
│  NIfTILoader    │  支持 .nii 和 .nii.gz
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  图像数据缓存   │  ArrayBuffer / SharedArrayBuffer
│  ImageCache     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HU 转换器      │  pixel_value * slope + intercept
│  HUConverter    │  输出 Float32Array
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  窗宽窗位工具   │  应用窗口预设或自定义窗口
│  WindowingTool  │  输出 Uint8Array (0-255)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Cornerstone    │  渲染到 Canvas
│  ImageLoader    │
└─────────────────┘
```

### 3.2 标注操作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        标注操作流程                              │
└─────────────────────────────────────────────────────────────────┘

[医生在图像上绘制标注]
        │
        ▼
┌─────────────────┐
│  标注工具       │  点、线、多边形、矩形、椭圆等
│  AnnotationTool │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  验证服务       │  检查点数、坐标有效性
│  AnnotationService│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API 调用       │  POST /api/annotation/sets/...
│  annotationApi  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  后端处理       │  保存到 JSON 文件
│  AnnotationService│  更新缓存
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  响应返回       │  返回创建的标注对象
│  { success }   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  前端状态更新   │  Zustand Store 更新
│  useCTStore    │  触发重新渲染
└─────────────────┘
```

### 3.3 窗宽窗位调整流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    窗宽窗位调整流程                              │
└─────────────────────────────────────────────────────────────────┘

[用户切换窗预设/拖动滑块]
        │
        ▼
┌─────────────────────────┐
│  预设选择 / 自定义输入  │
│  LUNG / MEDIASTINAL /   │
│  BONE / CUSTOM          │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  WindowingTool          │
│  .apply_windowing()     │
│  window_center: -600    │
│  window_width: 1500     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  范围计算               │
│  min = -600 - 1500/2   │
│      = -1350            │
│  max = -600 + 1500/2   │
│      = 150              │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  HU 数组裁剪             │
│  clipped = clip(HU,     │
│      -1350, 150)         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  归一化到 0-255          │
│  normalized =           │
│  (clipped - min) / ww   │
│  * 255                   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Cornerstone 重新渲染    │
│  触发 Canvas 更新       │
└─────────────────────────┘
```

---

## 4. 状态管理架构

### 4.1 Zustand Store 设计

```typescript
// stores/ctStore.ts

interface CTState {
  // 图像数据
  imageData: Float32Array | null;
  originalData: Float32Array | null;
  shape: [number, number, number];
  spacing: [number, number, number];

  // 显示状态
  currentSlice: number;
  viewType: 'axial' | 'coronal' | 'sagittal';
  windowCenter: number;
  windowWidth: number;

  // 标注状态
  annotationSets: Map<string, AnnotationSet>;
  activeAnnotationSet: string | null;
  activeAnnotation: string | null;
  selectedTool: AnnotationTool;

  // UI 状态
  isLoading: boolean;
  error: string | null;
  zoom: number;
  pan: { x: number; y: number };

  // 操作
  setSlice: (slice: number) => void;
  setWindow: (center: number, width: number) => void;
  loadImage: (data: ArrayBuffer) => Promise<void>;
  createAnnotation: (anno: AnnotationInput) => Promise<void>;
  updateAnnotation: (id: string, updates: Partial<Annotation>) => Promise<void>;
  deleteAnnotation: (id: string) => Promise<void>;
}

export const useCTStore = create<CTState>((set, get) => ({
  // 初始状态
  imageData: null,
  originalData: null,
  shape: [0, 0, 0],
  spacing: [1.0, 1.0, 2.5],
  currentSlice: 0,
  viewType: 'axial',
  windowCenter: -600,
  windowWidth: 1500,
  annotationSets: new Map(),
  activeAnnotationSet: null,
  activeAnnotation: null,
  selectedTool: 'pointer',
  isLoading: false,
  error: null,
  zoom: 1.0,
  pan: { x: 0, y: 0 },

  setSlice: (slice) => set({ currentSlice: Math.max(0, Math.min(slice, get().shape[2] - 1)) }),

  setWindow: (center, width) => {
    set({ windowCenter: center, windowWidth: width });
    get().applyWindowing();
  },

  loadImage: async (buffer) => {
    set({ isLoading: true, error: null });
    try {
      const data = new Float32Array(buffer);
      set({
        originalData: data,
        imageData: data,
        isLoading: false
      });
    } catch (e) {
      set({ error: '图像加载失败', isLoading: false });
    }
  },

  createAnnotation: async (input) => {
    const response = await fetch(`/api/annotation/sets/${get().activeAnnotationSet}/annotations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input)
    });
    const result = await response.json();
    if (result.success) {
      // 更新本地状态
    }
  }
}));
```

### 4.2 状态流转图

```
┌─────────────────────────────────────────────────────────────────┐
│                         状态流转图                               │
└─────────────────────────────────────────────────────────────────┘

┌──────────┐    loadImage()     ┌──────────┐    setWindow()    ┌──────────┐
│  IDLE    │ ─────────────────► │ LOADING  │ ─────────────────► │ READY    │
└──────────┘                   └──────────┘                    └──────────┘
     ▲                              │                              │
     │                              │ error                        │
     │                              ▼                              │
     │                       ┌──────────┐                         │
     └─────────────────────── │  ERROR   │ ◄───────────────────────┘
                              └──────────┘      applyWindowing()

┌─────────────────────────────────────────────────────────────────┐

                    标注状态流转

┌──────────┐   createAnnotation()   ┌──────────┐   confirmAnnotation()
│ PRELIMINARY │ ─────────────────► │ CONFIRMED │ ─────────────────► │
└──────────┘                       └──────────┘                      │
     ▲                                                                  │
     │   updateAnnotation() / deleteAnnotation()                       │
     │                                                                  │
     └──────────────────────────────────────────────────────────────────┘
```

---

## 5. UI 组件架构

### 5.1 组件层次结构

```
CTViewer
├── CTHeader                    # 标题栏、切片信息
│   ├── SliceIndicator
│   └── ViewTypeSelector
├── CTMainViewport              # 主视图区域
│   ├── CornerstoneCanvas       # Cornerstone 渲染画布
│   ├── AnnotationOverlay       # 标注叠加层
│   └── MeasurementOverlay      # 测量值显示
├── CTSidePanel                 # 侧边面板 (PC端)
│   ├── OrganSegmentList        # 器官分割列表
│   └── AnnotationList          # 标注列表
├── CTControlBar                # 底部控制栏
│   ├── ToolButtons             # 工具按钮组
│   ├── SliceSlider             # 切片滑块
│   └── WindowPresetSelector    # 窗宽窗位选择
├── CTThumbnails                # 切片缩略图条
└── CTMobilePanel               # 移动端面板 (抽屉)
```

### 5.2 组件规格

#### CTMainViewport

| 属性 | 类型 | 说明 |
|------|------|------|
| className | string | CSS 类名 |
| imageData | Float32Array | CT 图像数据 |
| sliceIndex | number | 当前切片索引 |
| windowCenter | number | 窗位 |
| windowWidth | number | 窗宽 |
| annotations | Annotation[] | 标注列表 |
| onAnnotationCreate | function | 创建标注回调 |

**样式规格:**
```css
.ct-main-viewport {
    position: relative;
    background-color: #1a1a1a;  /* 黑色背景 */
    border-radius: 8px;
    overflow: hidden;
    min-height: 400px;
    max-height: 60vh;
}

.ct-canvas {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}

.annotation-overlay {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: none;
}

.annotation-overlay.active {
    pointer-events: auto;
}
```

#### WindowPresetSelector

| 预设 | 窗宽 | 窗位 | 适用场景 |
|------|------|------|----------|
| 肺窗 | 1500 | -600 | 肺部病变 |
| 纵隔窗 | 400 | 40 | 纵隔结构 |
| 骨窗 | 2000 | 300 | 骨骼 |
| 脑窗 | 80 | 40 | 脑组织 |
| 腹窗 | 400 | 50 | 腹部 |

#### ToolButtons

| 工具 | 图标 | 快捷键 | 说明 |
|------|------|--------|------|
| 指针 | pointer | V | 选择/移动 |
| 画笔 | paintbrush | B | 涂抹标注 |
| 橡皮擦 | eraser | E | 擦除 |
| 智能套索 | lasso | L | 智能选择 |
| 撤销 | undo | Ctrl+Z | 撤销 |
| 重做 | redo | Ctrl+Y | 重做 |
| 缩放 | zoom-in | Z | 缩放 |
| 平移 | move | M | 平移 |

### 5.3 响应式设计

```css
/* PC 端 (>= 1024px) */
.ct-viewer {
    display: flex;
    flex-direction: row;
}

.ct-side-panel {
    width: 320px;
    display: block;
}

/* 平板端 (768px - 1023px) */
@media (max-width: 1023px) {
    .ct-side-panel {
        width: 280px;
    }
}

/* 移动端 (< 768px) */
@media (max-width: 767px) {
    .ct-side-panel {
        position: fixed;
        right: -100%;
        top: 0;
        bottom: 0;
        width: 100%;
        z-index: 100;
        transition: right 0.3s ease;
    }

    .ct-side-panel.open {
        right: 0;
    }
}
```

---

## 6. 错误处理机制

### 6.1 错误分类

| 错误类型 | HTTP 状态码 | 处理方式 |
|----------|-------------|----------|
| VALIDATION_ERROR | 400 | 提示用户输入有误 |
| NOT_FOUND | 404 | 提示资源不存在 |
| SERVICE_ERROR | 500 | 提示服务异常 |
| INTERNAL_ERROR | 500 | 记录日志，提示系统错误 |

### 6.2 错误响应格式

```json
{
    "error": "VALIDATION_ERROR",
    "message": "缺少必需字段: type"
}
```

### 6.3 前端错误处理

```typescript
// utils/apiClient.ts

class APIError extends Error {
    constructor(
        public code: string,
        message: string,
        public statusCode: number
    ) {
        super(message);
        this.name = 'APIError';
    }
}

async function handleResponse<T>(response: Response): Promise<T> {
    const data = await response.json();

    if (!response.ok) {
        throw new APIError(
            data.error || 'UNKNOWN_ERROR',
            data.message || '请求失败',
            response.status
        );
    }

    return data;
}

// 使用示例
try {
    const result = await createAnnotation(data);
} catch (e) {
    if (e instanceof APIError) {
        switch (e.code) {
            case 'VALIDATION_ERROR':
                showToast(e.message, 'warning');
                break;
            case 'NOT_FOUND':
                showToast('标注不存在', 'error');
                break;
            default:
                showToast('系统错误，请稍后重试', 'error');
        }
    }
}
```

### 6.4 用户反馈机制

```typescript
// Toast 通知
showToast('标注已保存', 'success');
showToast('网络连接失败', 'error');
showToast('正在加载...', 'info');

// 加载状态
{ isLoading && <LoadingOverlay /> }

// 空状态
{ annotations.length === 0 && (
    <EmptyState message="暂无标注，点击添加第一个标注" />
)}
```

---

## 7. 集成检查清单

### 7.1 API 集成

- [ ] 标注集 CRUD 操作
- [ ] 标注创建、更新、删除
- [ ] 切片级别标注查询
- [ ] JSON/DICOM-SR 导出
- [ ] 可视化预设获取
- [ ] 错误响应处理

### 7.2 图像渲染

- [ ] NIfTI 文件加载 (.nii, .nii.gz)
- [ ] HU 值转换
- [ ] 窗宽窗位调整
- [ ] Cornerstone.js 集成
- [ ] 多平面重建 (MPR)
- [ ] 缩放/平移交互

### 7.3 标注功能

- [ ] 点标注
- [ ] 线段标注
- [ ] 多边形标注
- [ ] 矩形标注
- [ ] 椭圆标注
- [ ] 标注选择和移动
- [ ] 标注删除

### 7.4 响应式设计

- [ ] PC 端布局
- [ ] 平板端布局
- [ ] 移动端布局
- [ ] 侧边栏折叠

---

## 8. 文件结构

```
ctai_backend/
├── services/
│   ├── nifti_service.py         # NIfTI 解析
│   ├── annotation_service.py   # 标注服务
│   └── medical_image_utils.py   # HU 转换、窗宽窗位
├── routes/
│   └── annotation_api.py       # REST API
├── models/
│   └── annotation.py            # 数据模型
└── tests/
    └── test_medical_imaging.py  # 单元测试

static/
├── js/
│   ├── cornerstone/            # Cornerstone.js
│   │   ├── cornerstoneCore.js
│   │   ├── cornerstoneWADOImageLoader.js
│   │   └── cornerstoneMath.js
│   ├── ct/
│   │   ├── ctViewer.js          # 主视图组件
│   │   ├── ctStore.js           # Zustand 状态
│   │   ├── annotationTool.js    # 标注工具
│   │   └── windowingTool.js     # 窗宽窗位
│   └── utils/
│       └── apiClient.js         # API 客户端
└── css/
    └── ct-viewer.css            # CT 组件样式
```

---

## 9. 集成步骤

1. **环境准备**
   - 引入 Cornerstone.js 库
   - 配置 Zustand 状态管理

2. **后端验证**
   - 确认 annotation_api.py 路由正常
   - 运行单元测试 `python tests/test_medical_imaging.py`

3. **前端基础组件**
   - 创建 CTViewer 主组件
   - 实现 Cornerstone 画布集成

4. **窗宽窗位功能**
   - 实现 WindowPresetSelector
   - 绑定 HU 转换逻辑

5. **标注功能**
   - 集成 annotationApi
   - 实现 AnnotationOverlay

6. **响应式适配**
   - 实现 CTMobilePanel
   - 侧边栏折叠动画

7. **测试验证**
   - 端到端功能测试
   - 响应式布局测试
