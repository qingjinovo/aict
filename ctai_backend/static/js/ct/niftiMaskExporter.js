/**
 * NIfTI 掩码导出工具
 * 将标注转换为 NIfTI 格式的分割掩码文件
 */

const NIfTIMaskExporter = {
    LABEL_BG: 0,

    annotationsToMask(annotations, shape) {
        const mask = new Uint8Array(shape[0] * shape[1] * shape[2]);
        mask.fill(this.LABEL_BG);

        for (const anno of annotations) {
            if (!anno.graphic_data || !anno.graphic_data.points) continue;
            if (anno.workflow_status === 'deleted') continue;

            const sliceIndex = anno.graphic_data.slice_index;
            if (sliceIndex < 0 || sliceIndex >= shape[2]) continue;

            const label = this.getLabelValue(anno);
            this.fillAnnotationMask(mask, anno, shape, sliceIndex, label);
        }

        return mask;
    },

    getLabelValue(annotation) {
        const labelMap = {
            'normal': 1,
            'low': 2,
            'medium': 3,
            'high': 4,
            'critical': 5
        };

        const categoryMap = {
            'anatomy': 10,
            'lesion': 20,
            'finding': 30,
            'ai_result': 40,
            'measurement': 50
        };

        const severityVal = labelMap[annotation.severity] || 1;
        const categoryVal = categoryMap[annotation.category] || 30;

        return severityVal * 100 + categoryVal;
    },

    fillAnnotationMask(mask, annotation, shape, sliceIndex, label) {
        const { width, height } = shape;
        const sliceSize = width * height;
        const sliceStart = sliceIndex * sliceSize;

        const pts = annotation.graphic_data.points;
        const type = annotation.graphic_type;

        switch (type) {
            case 'point':
                this.fillPoint(mask, pts, width, height, sliceStart, label);
                break;
            case 'line':
                this.fillLine(mask, pts, width, height, sliceStart, label);
                break;
            case 'rectangle':
                this.fillRectangle(mask, pts, width, height, sliceStart, label);
                break;
            case 'ellipse':
                this.fillEllipse(mask, pts, width, height, sliceStart, label);
                break;
            case 'polygon':
                this.fillPolygon(mask, pts, width, height, sliceStart, label);
                break;
            case 'brush':
                this.fillBrush(mask, pts, width, height, sliceStart, label);
                break;
            default:
                break;
        }
    },

    fillPoint(mask, pts, width, height, sliceStart, label) {
        if (pts.length < 1) return;
        const x = Math.round(pts[0].x);
        const y = Math.round(pts[0].y);
        if (x >= 0 && x < width && y >= 0 && y < height) {
            mask[sliceStart + y * width + x] = label;
        }
    },

    fillLine(mask, pts, width, height, sliceStart, label) {
        if (pts.length < 2) return;

        const x0 = Math.round(pts[0].x);
        const y0 = Math.round(pts[0].y);
        const x1 = Math.round(pts[pts.length - 1].x);
        const y1 = Math.round(pts[pts.length - 1].y);

        const dx = Math.abs(x1 - x0);
        const dy = Math.abs(y1 - y0);
        const sx = x0 < x1 ? 1 : -1;
        const sy = y0 < y1 ? 1 : -1;
        let err = dx - dy;

        let x = x0, y = y0;
        while (true) {
            if (x >= 0 && x < width && y >= 0 && y < height) {
                mask[sliceStart + y * width + x] = label;
            }

            if (x === x1 && y === y1) break;

            const e2 = 2 * err;
            if (e2 > -dy) {
                err -= dy;
                x += sx;
            }
            if (e2 < dx) {
                err += dx;
                y += sy;
            }
        }
    },

    fillRectangle(mask, pts, width, height, sliceStart, label) {
        if (pts.length < 2) return;

        const x0 = Math.round(Math.min(pts[0].x, pts[1].x));
        const y0 = Math.round(Math.min(pts[0].y, pts[1].y));
        const x1 = Math.round(Math.max(pts[0].x, pts[1].x));
        const y1 = Math.round(Math.max(pts[0].y, pts[1].y));

        for (let y = y0; y <= y1; y++) {
            for (let x = x0; x <= x1; x++) {
                if (x >= 0 && x < width && y >= 0 && y < height) {
                    mask[sliceStart + y * width + x] = label;
                }
            }
        }
    },

    fillEllipse(mask, pts, width, height, sliceStart, label) {
        if (pts.length < 2) return;

        const cx = (pts[0].x + pts[1].x) / 2;
        const cy = (pts[0].y + pts[1].y) / 2;
        const rx = Math.abs(pts[1].x - pts[0].x) / 2;
        const ry = Math.abs(pts[1].y - pts[0].y) / 2;

        if (rx === 0 || ry === 0) return;

        const x0 = Math.max(0, Math.floor(cx - rx));
        const x1 = Math.min(width - 1, Math.ceil(cx + rx));
        const y0 = Math.max(0, Math.floor(cy - ry));
        const y1 = Math.min(height - 1, Math.ceil(cy + ry));

        for (let y = y0; y <= y1; y++) {
            for (let x = x0; x <= x1; x++) {
                const norm = ((x - cx) * (x - cx)) / (rx * rx) +
                             ((y - cy) * (y - cy)) / (ry * ry);
                if (norm <= 1) {
                    mask[sliceStart + y * width + x] = label;
                }
            }
        }
    },

    fillPolygon(mask, pts, width, height, sliceStart, label) {
        if (pts.length < 3) return;

        const minX = Math.max(0, Math.floor(Math.min(...pts.map(p => p.x))));
        const maxX = Math.min(width - 1, Math.ceil(Math.max(...pts.map(p => p.x))));
        const minY = Math.max(0, Math.floor(Math.min(...pts.map(p => p.y))));
        const maxY = Math.min(height - 1, Math.ceil(Math.max(...pts.map(p => p.y))));

        for (let y = minY; y <= maxY; y++) {
            for (let x = minX; x <= maxX; x++) {
                if (this.isPointInPolygon({ x, y }, pts)) {
                    mask[sliceStart + y * width + x] = label;
                }
            }
        }
    },

    fillBrush(mask, pts, width, height, sliceStart, label) {
        if (pts.length < 1) return;

        const brushWidth = 3;

        for (let i = 0; i < pts.length - 1; i++) {
            const p1 = pts[i];
            const p2 = pts[i + 1];

            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const steps = Math.max(1, Math.ceil(dist));

            for (let s = 0; s <= steps; s++) {
                const t = steps === 0 ? 0 : s / steps;
                const bx = Math.round(p1.x + dx * t);
                const by = Math.round(p1.y + dy * t);

                for (let dy2 = -brushWidth; dy2 <= brushWidth; dy2++) {
                    for (let dx2 = -brushWidth; dx2 <= brushWidth; dx2++) {
                        const x = bx + dx2;
                        const y = by + dy2;
                        if (x >= 0 && x < width && y >= 0 && y < height) {
                            const dist2 = Math.sqrt(dx2 * dx2 + dy2 * dy2);
                            if (dist2 <= brushWidth) {
                                mask[sliceStart + y * width + x] = label;
                            }
                        }
                    }
                }
            }
        }

        for (const pt of pts) {
            const x = Math.round(pt.x);
            const y = Math.round(pt.y);
            for (let dy2 = -brushWidth; dy2 <= brushWidth; dy2++) {
                for (let dx2 = -brushWidth; dx2 <= brushWidth; dx2++) {
                    const px = x + dx2;
                    const py = y + dy2;
                    if (px >= 0 && px < width && py >= 0 && py < height) {
                        const dist = Math.sqrt(dx2 * dx2 + dy2 * dy2);
                        if (dist <= brushWidth) {
                            mask[sliceStart + py * width + px] = label;
                        }
                    }
                }
            }
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

    createNIfTIFromMask(mask, shape, spacing, filename = 'annotation_mask.nii') {
        const headerSize = 352;
        const extensionSize = 4;
        const totalSize = headerSize + extensionSize + mask.length;

        const buffer = new ArrayBuffer(totalSize);
        const bytes = new Uint8Array(buffer);
        const view = new DataView(buffer);

        view.setInt32(0, 348, true);

        view.setInt16(40, shape.length, true);
        view.setInt16(42, shape[0], true);
        view.setInt16(44, shape[1], true);
        view.setInt16(46, shape[2], true);

        view.setFloat32(56, 0, true);
        view.setFloat32(60, spacing[0], true);
        view.setFloat32(64, spacing[1], true);
        view.setFloat32(68, spacing[2], true);

        view.setInt16(70, 2, true);
        view.setInt16(72, 8, true);
        view.setFloat32(108, headerSize + extensionSize, true);

        view.setFloat32(124, 1, true);
        view.setFloat32(128, 0, true);

        const descrip = 'Annotation Mask - SAM-Med3D';
        for (let i = 0; i < descrip.length && i < 80; i++) {
            bytes[148 + i] = descrip.charCodeAt(i);
        }

        bytes[344] = 110;
        bytes[345] = 43;
        bytes[346] = 49;
        bytes[347] = 0;

        bytes[348] = 0;
        bytes[349] = 0;
        bytes[350] = 0;
        bytes[351] = 0;

        for (let i = 0; i < mask.length; i++) {
            bytes[headerSize + extensionSize + i] = mask[i];
        }

        return new Blob([buffer], { type: 'application/octet-stream' });
    },

    downloadMask(annotations, shape, spacing, filename = 'annotation_mask.nii') {
        const mask = this.annotationsToMask(annotations, shape);
        const blob = this.createNIfTIFromMask(mask, shape, spacing, filename);

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    getLabelLegend(annotations) {
        const labels = new Map();

        for (const anno of annotations) {
            if (anno.workflow_status === 'deleted') continue;

            const label = this.getLabelValue(anno);
            if (!labels.has(label)) {
                labels.set(label, {
                    value: label,
                    category: anno.category,
                    severity: anno.severity,
                    label: anno.label || anno.graphic_type,
                    count: 0
                });
            }
            labels.get(label).count++;
        }

        return Array.from(labels.values());
    }
};

window.NIfTIMaskExporter = NIfTIMaskExporter;
