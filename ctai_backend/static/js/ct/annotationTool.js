/**
 * CT 医学影像标注工具
 * 提供标注绘制、选择、编辑功能
 */

const AnnotationTool = {
    tools: {
        pointer: { name: '指针', icon: 'mouse-pointer', cursor: 'default' },
        paintbrush: { name: '画笔', icon: 'paintbrush', cursor: 'crosshair' },
        eraser: { name: '橡皮擦', icon: 'eraser', cursor: 'crosshair' },
        lasso: { name: '智能套索', icon: 'lasso', cursor: 'crosshair' },
        line: { name: '线段', icon: 'minus', cursor: 'crosshair' },
        rectangle: { name: '矩形', icon: 'square', cursor: 'crosshair' },
        ellipse: { name: '椭圆', icon: 'circle', cursor: 'crosshair' },
        polygon: { name: '多边形', icon: 'pentagon', cursor: 'crosshair' },
        arrow: { name: '箭头', icon: 'arrow-right', cursor: 'crosshair' }
    },

    activeTool: 'pointer',
    isDrawing: false,
    currentPoints: [],
    annotations: [],
    selectedAnnotation: null,

    colors: {
        fill: 'rgba(255, 230, 109, 0.3)',
        stroke: 'rgba(255, 230, 109, 1)',
        selectedFill: 'rgba(22, 93, 255, 0.3)',
        selectedStroke: 'rgba(22, 93, 255, 1)',
        aiSuspicious: {
            fill: 'rgba(255, 71, 87, 0.3)',
            stroke: 'rgba(255, 71, 87, 1)'
        },
        lung: {
            fill: 'rgba(255, 230, 109, 0.3)',
            stroke: 'rgba(255, 230, 109, 1)'
        },
        mediastinal: {
            fill: 'rgba(78, 205, 196, 0.3)',
            stroke: 'rgba(78, 205, 196, 1)'
        }
    },

    init(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.options = {
            onAnnotationCreated: options.onAnnotationCreated || (() => {}),
            onAnnotationSelected: options.onAnnotationSelected || (() => {}),
            ...options
        };

        this.bindEvents();
        return this;
    },

    bindEvents() {
        if (!this.canvas) return;

        this.canvas.addEventListener('mousedown', this.handleMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.handleMouseUp.bind(this));
        this.canvas.addEventListener('mouseleave', this.handleMouseUp.bind(this));

        this.canvas.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        this.canvas.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        this.canvas.addEventListener('touchend', this.handleTouchEnd.bind(this));
    },

    getCanvasCoords(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;

        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    },

    getTouchCoords(e) {
        const touch = e.touches[0] || e.changedTouches[0];
        return this.getCanvasCoords(touch);
    },

    handleMouseDown(e) {
        if (this.activeTool === 'pointer') {
            this.checkAnnotationSelection(this.getCanvasCoords(e));
            return;
        }

        if (['paintbrush', 'eraser'].includes(this.activeTool)) {
            this.startBrushDrawing(this.getCanvasCoords(e));
            return;
        }

        this.isDrawing = true;
        this.currentPoints = [this.getCanvasCoords(e)];
    },

    handleMouseMove(e) {
        const coords = this.getCanvasCoords(e);

        if (this.activeTool === 'pointer' && this.selectedAnnotation) {
            if (e.buttons === 1) {
                this.moveAnnotation(this.selectedAnnotation, coords);
            }
            return;
        }

        if (this.activeTool === 'eraser' && this.isDrawing) {
            this.eraseAt(coords);
            return;
        }

        if (this.activeTool === 'paintbrush' && this.isDrawing) {
            this.continueBrushStroke(coords);
            return;
        }

        if (this.isDrawing) {
            this.currentPoints.push(coords);
            this.redraw();
            this.previewCurrentShape();
        }
    },

    handleMouseUp(e) {
        if (this.isDrawing) {
            this.finishDrawing();
        }

        if (this.isDrawingBrush) {
            this.finishBrushStroke();
        }
    },

    handleTouchStart(e) {
        e.preventDefault();
        const coords = this.getTouchCoords(e);

        if (this.activeTool === 'pointer') {
            this.checkAnnotationSelection(coords);
            return;
        }

        this.isDrawing = true;
        this.currentPoints = [coords];
    },

    handleTouchMove(e) {
        e.preventDefault();
        if (this.isDrawing) {
            this.currentPoints.push(this.getTouchCoords(e));
            this.redraw();
            this.previewCurrentShape();
        }
    },

    handleTouchEnd(e) {
        if (this.isDrawing) {
            this.finishDrawing();
        }
    },

    checkAnnotationSelection(coords) {
        let found = null;

        for (let i = this.annotations.length - 1; i >= 0; i--) {
            const anno = this.annotations[i];
            if (this.isPointInAnnotation(coords, anno)) {
                found = anno;
                break;
            }
        }

        if (found !== this.selectedAnnotation) {
            this.selectedAnnotation = found;
            this.options.onAnnotationSelected(found);
            this.redraw();
        }
    },

    isPointInAnnotation(point, annotation) {
        if (!annotation.graphic_data || !annotation.graphic_data.points) {
            return false;
        }

        const ctx = this.ctx;
        const pts = annotation.graphic_data.points;

        switch (annotation.graphic_type) {
            case 'point':
                const dx = point.x - pts[0].x;
                const dy = point.y - pts[0].y;
                return Math.sqrt(dx * dx + dy * dy) < 10;

            case 'rectangle':
                const minX = Math.min(pts[0].x, pts[1].x);
                const maxX = Math.max(pts[0].x, pts[1].x);
                const minY = Math.min(pts[0].y, pts[1].y);
                const maxY = Math.max(pts[0].y, pts[1].y);
                return point.x >= minX && point.x <= maxX &&
                       point.y >= minY && point.y <= maxY;

            case 'ellipse':
                const cx = (pts[0].x + pts[1].x) / 2;
                const cy = (pts[0].y + pts[1].y) / 2;
                const rx = Math.abs(pts[1].x - pts[0].x) / 2;
                const ry = Math.abs(pts[1].y - pts[0].y) / 2;
                if (rx === 0 || ry === 0) return false;
                const norm = ((point.x - cx) * (point.x - cx)) / (rx * rx) +
                             ((point.y - cy) * (point.y - cy)) / (ry * ry);
                return norm <= 1;

            case 'polygon':
                return this.isPointInPolygon(point, pts);

            case 'line':
                return this.isPointNearLine(point, pts[0], pts[1], 5);

            default:
                return false;
        }
    },

    isPointInPolygon(point, polygon) {
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i].x, yi = polygon[i].y;
            const xj = polygon[j].x, yj = polygon[j].y;

            if (((yi > point.y) !== (yj > point.y)) &&
                (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi)) {
                inside = !inside;
            }
        }
        return inside;
    },

    isPointNearLine(point, p1, p2, threshold) {
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const lengthSq = dx * dx + dy * dy;

        if (lengthSq === 0) {
            const dx2 = point.x - p1.x;
            const dy2 = point.y - p1.y;
            return Math.sqrt(dx2 * dx2 + dy2 * dy2) < threshold;
        }

        let t = ((point.x - p1.x) * dx + (point.y - p1.y) * dy) / lengthSq;
        t = Math.max(0, Math.min(1, t));

        const projX = p1.x + t * dx;
        const projY = p1.y + t * dy;
        const dist = Math.sqrt((point.x - projX) ** 2 + (point.y - projY) ** 2);

        return dist < threshold;
    },

    moveAnnotation(annotation, newCoords) {
        if (!annotation.graphic_data || !annotation.graphic_data.points) return;

        const pts = annotation.graphic_data.points;
        const dx = newCoords.x - this.lastMoveCoords.x;
        const dy = newCoords.y - this.lastMoveCoords.y;

        for (let pt of pts) {
            pt.x += dx;
            pt.y += dy;
        }

        this.lastMoveCoords = newCoords;
        this.redraw();
    },

    startBrushDrawing(coords) {
        this.isDrawing = true;
        this.isDrawingBrush = true;
        this.brushStroke = [coords];
    },

    continueBrushStroke(coords) {
        this.brushStroke.push(coords);
        this.redraw();
        this.drawBrushStroke();
    },

    finishBrushStroke() {
        if (this.brushStroke && this.brushStroke.length > 0) {
            this.currentPoints = [...this.brushStroke];
            this.finishDrawing();
        }
        this.isDrawingBrush = false;
        this.brushStroke = [];
    },

    eraseAt(coords) {
        if (!this.annotations.length) return;

        for (let i = this.annotations.length - 1; i >= 0; i--) {
            if (this.isPointInAnnotation(coords, this.annotations[i])) {
                const deleted = this.annotations.splice(i, 1)[0];
                this.options.onAnnotationDeleted && this.options.onAnnotationDeleted(deleted);
                this.redraw();
                break;
            }
        }
    },

    finishDrawing() {
        if (!this.isDrawing) return;

        this.isDrawing = false;

        if (this.currentPoints.length < 2 &&
            this.activeTool !== 'pointer' &&
            this.activeTool !== 'paintbrush') {
            this.currentPoints = [];
            return;
        }

        const annotation = this.createAnnotationFromPoints();
        if (annotation) {
            this.annotations.push(annotation);
            this.options.onAnnotationCreated(annotation);
        }

        this.currentPoints = [];
        this.redraw();
    },

    createAnnotationFromPoints() {
        if (!this.currentPoints.length) return null;

        const typeMap = {
            line: 'line',
            rectangle: 'rectangle',
            ellipse: 'ellipse',
            polygon: 'polygon',
            arrow: 'arrow',
            lasso: 'polygon',
            paintbrush: 'brush'
        };

        const categoryMap = {
            lung: 'lesion',
            aiSuspicious: 'ai_result'
        };

        return {
            annotation_id: 'anno_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9),
            graphic_type: typeMap[this.activeTool] || 'point',
            category: 'finding',
            label: '',
            severity: 'normal',
            slice_index: CTStore.getState().currentSlice,
            graphic_data: {
                type: typeMap[this.activeTool] || 'point',
                points: this.currentPoints.map(p => ({ x: p.x, y: p.y })),
                slice_index: CTStore.getState().currentSlice
            },
            visual_attributes: {
                fill_color: [255, 230, 109, 100],
                stroke_color: [255, 230, 109, 255],
                stroke_width: 2
            },
            workflow_status: 'preliminary',
            created_at: new Date().toISOString()
        };
    },

    previewCurrentShape() {
        if (!this.currentPoints.length) return;

        const ctx = this.ctx;
        ctx.save();
        ctx.strokeStyle = 'rgba(22, 93, 255, 0.8)';
        ctx.fillStyle = 'rgba(22, 93, 255, 0.2)';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);

        switch (this.activeTool) {
            case 'line':
            case 'lasso':
                if (this.currentPoints.length >= 2) {
                    ctx.beginPath();
                    ctx.moveTo(this.currentPoints[0].x, this.currentPoints[0].y);
                    for (let i = 1; i < this.currentPoints.length; i++) {
                        ctx.lineTo(this.currentPoints[i].x, this.currentPoints[i].y);
                    }
                    if (this.activeTool === 'lasso') {
                        ctx.closePath();
                    }
                    ctx.stroke();
                }
                break;

            case 'rectangle':
                if (this.currentPoints.length >= 2) {
                    const p1 = this.currentPoints[0];
                    const p2 = this.currentPoints[this.currentPoints.length - 1];
                    ctx.strokeRect(p1.x, p1.y, p2.x - p1.x, p2.y - p1.y);
                }
                break;

            case 'ellipse':
                if (this.currentPoints.length >= 2) {
                    const p1 = this.currentPoints[0];
                    const p2 = this.currentPoints[this.currentPoints.length - 1];
                    const cx = (p1.x + p2.x) / 2;
                    const cy = (p1.y + p2.y) / 2;
                    const rx = Math.abs(p2.x - p1.x) / 2;
                    const ry = Math.abs(p2.y - p1.y) / 2;
                    ctx.beginPath();
                    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
                    ctx.stroke();
                }
                break;

            case 'polygon':
            case 'arrow':
                if (this.currentPoints.length >= 2) {
                    ctx.beginPath();
                    ctx.moveTo(this.currentPoints[0].x, this.currentPoints[0].y);
                    for (let i = 1; i < this.currentPoints.length; i++) {
                        ctx.lineTo(this.currentPoints[i].x, this.currentPoints[i].y);
                    }
                    if (this.activeTool === 'polygon' && this.currentPoints.length >= 3) {
                        ctx.closePath();
                        ctx.fill();
                    }
                    ctx.stroke();

                    if (this.activeTool === 'arrow' && this.currentPoints.length >= 2) {
                        this.drawArrowHead(
                            ctx,
                            this.currentPoints[this.currentPoints.length - 2],
                            this.currentPoints[this.currentPoints.length - 1]
                        );
                    }
                }
                break;
        }

        ctx.restore();
    },

    drawArrowHead(ctx, from, to) {
        const headLength = 15;
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const angle = Math.atan2(dy, dx);

        ctx.beginPath();
        ctx.moveTo(to.x, to.y);
        ctx.lineTo(
            to.x - headLength * Math.cos(angle - Math.PI / 6),
            to.y - headLength * Math.sin(angle - Math.PI / 6)
        );
        ctx.moveTo(to.x, to.y);
        ctx.lineTo(
            to.x - headLength * Math.cos(angle + Math.PI / 6),
            to.y - headLength * Math.sin(angle + Math.PI / 6)
        );
        ctx.stroke();
    },

    drawBrushStroke() {
        if (!this.brushStroke || this.brushStroke.length < 2) return;

        const ctx = this.ctx;
        ctx.save();
        ctx.strokeStyle = this.colors.stroke;
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        ctx.beginPath();
        ctx.moveTo(this.brushStroke[0].x, this.brushStroke[0].y);
        for (let i = 1; i < this.brushStroke.length; i++) {
            ctx.lineTo(this.brushStroke[i].x, this.brushStroke[i].y);
        }
        ctx.stroke();
        ctx.restore();
    },

    setTool(toolName) {
        this.activeTool = toolName;
        this.isDrawing = false;
        this.currentPoints = [];

        if (this.canvas) {
            const tool = this.tools[toolName];
            if (tool) {
                this.canvas.style.cursor = tool.cursor;
            }
        }
    },

    setAnnotations(annotations) {
        this.annotations = annotations || [];
        this.redraw();
    },

    getAnnotations() {
        return this.annotations;
    },

    deleteSelected() {
        if (this.selectedAnnotation) {
            const idx = this.annotations.indexOf(this.selectedAnnotation);
            if (idx !== -1) {
                const deleted = this.annotations.splice(idx, 1)[0];
                this.options.onAnnotationDeleted && this.options.onAnnotationDeleted(deleted);
                this.selectedAnnotation = null;
                this.redraw();
            }
        }
    },

    clearAll() {
        this.annotations = [];
        this.selectedAnnotation = null;
        this.redraw();
    },

    redraw() {
        if (!this.ctx) return;

        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        for (const anno of this.annotations) {
            this.drawAnnotation(anno, anno === this.selectedAnnotation);
        }
    },

    drawAnnotation(annotation, isSelected = false) {
        if (!annotation.graphic_data || !annotation.graphic_data.points) return;

        const ctx = this.ctx;
        const pts = annotation.graphic_data.points;
        const attrs = annotation.visual_attributes || {};

        const fillColor = this.rgbaToString(attrs.fill_color || [255, 230, 109, 100], isSelected);
        const strokeColor = this.rgbaToString(attrs.stroke_color || [255, 230, 109, 255], isSelected);
        const strokeWidth = attrs.stroke_width || 2;

        ctx.save();
        ctx.fillStyle = fillColor;
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = strokeWidth;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        switch (annotation.graphic_type) {
            case 'point':
                if (pts.length > 0) {
                    ctx.beginPath();
                    ctx.arc(pts[0].x, pts[0].y, 5, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.stroke();
                }
                break;

            case 'line':
                if (pts.length >= 2) {
                    ctx.beginPath();
                    ctx.moveTo(pts[0].x, pts[0].y);
                    ctx.lineTo(pts[1].x, pts[1].y);
                    ctx.stroke();
                }
                break;

            case 'rectangle':
                if (pts.length >= 2) {
                    ctx.beginPath();
                    ctx.rect(
                        Math.min(pts[0].x, pts[1].x),
                        Math.min(pts[0].y, pts[1].y),
                        Math.abs(pts[1].x - pts[0].x),
                        Math.abs(pts[1].y - pts[0].y)
                    );
                    ctx.fill();
                    ctx.stroke();
                }
                break;

            case 'ellipse':
                if (pts.length >= 2) {
                    const cx = (pts[0].x + pts[1].x) / 2;
                    const cy = (pts[0].y + pts[1].y) / 2;
                    const rx = Math.abs(pts[1].x - pts[0].x) / 2;
                    const ry = Math.abs(pts[1].y - pts[0].y) / 2;
                    ctx.beginPath();
                    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.stroke();
                }
                break;

            case 'polygon':
                if (pts.length >= 3) {
                    ctx.beginPath();
                    ctx.moveTo(pts[0].x, pts[0].y);
                    for (let i = 1; i < pts.length; i++) {
                        ctx.lineTo(pts[i].x, pts[i].y);
                    }
                    ctx.closePath();
                    ctx.fill();
                    ctx.stroke();
                }
                break;

            case 'brush':
                if (pts.length >= 2) {
                    ctx.beginPath();
                    ctx.moveTo(pts[0].x, pts[0].y);
                    for (let i = 1; i < pts.length; i++) {
                        ctx.lineTo(pts[i].x, pts[i].y);
                    }
                    ctx.stroke();
                }
                break;

            case 'arrow':
                if (pts.length >= 2) {
                    ctx.beginPath();
                    ctx.moveTo(pts[0].x, pts[0].y);
                    ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
                    ctx.stroke();

                    this.drawArrowHead(ctx,
                        pts[pts.length - 2] || pts[0],
                        pts[pts.length - 1]
                    );
                }
                break;
        }

        if (isSelected) {
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = 'rgba(22, 93, 255, 0.8)';
            ctx.lineWidth = 1;
            ctx.strokeRect(-2, -2, this.canvas.width + 4, this.canvas.height + 4);
        }

        ctx.restore();
    },

    rgbaToString(color, isSelected = false) {
        if (typeof color === 'string') return color;
        if (isSelected) {
            return `rgba(22, 93, 255, ${(color[3] || 100) / 255})`;
        }
        return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${(color[3] || 100) / 255})`;
    },

    undo() {
        if (this.annotations.length > 0) {
            const removed = this.annotations.pop();
            this.options.onAnnotationDeleted && this.options.onAnnotationDeleted(removed);
            this.redraw();
        }
    },

    destroy() {
        if (this.canvas) {
            this.canvas.removeEventListener('mousedown', this.handleMouseDown);
            this.canvas.removeEventListener('mousemove', this.handleMouseMove);
            this.canvas.removeEventListener('mouseup', this.handleMouseUp);
            this.canvas.removeEventListener('mouseleave', this.handleMouseUp);
            this.canvas.removeEventListener('touchstart', this.handleTouchStart);
            this.canvas.removeEventListener('touchmove', this.handleTouchMove);
            this.canvas.removeEventListener('touchend', this.handleTouchEnd);
        }
        this.annotations = [];
        this.currentPoints = [];
        this.selectedAnnotation = null;
    }
};

window.AnnotationTool = AnnotationTool;
