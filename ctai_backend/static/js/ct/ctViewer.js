/**
 * CT 医学影像主视图组件
 * 整合 NIfTI 加载、窗宽窗位调整、标注绘制功能
 */

class CTViewer {
    constructor(container, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;

        if (!this.container) {
            throw new Error('CTViewer: 容器元素未找到');
        }

        this.options = {
            annotationSetId: options.annotationSetId || null,
            ctImageId: options.ctImageId || null,
            initialSlice: options.initialSlice || 0,
            initialPreset: options.initialPreset || 'lung',
            onAnnotationCreated: options.onAnnotationCreated || (() => {}),
            onAnnotationSelected: options.onAnnotationSelected || (() => {}),
            onAnnotationDeleted: options.onAnnotationDeleted || (() => {}),
            onSliceChange: options.onSliceChange || (() => {}),
            onError: options.onError || console.error,
            ...options
        };

        this.state = {
            loaded: false,
            loading: false,
            niftiData: null,
            shape: [0, 0, 0],
            spacing: [1.0, 1.0, 2.5],
            currentSlice: 0,
            viewType: 'axial',
            windowCenter: -600,
            windowWidth: 1500,
            zoom: 1.0,
            pan: { x: 0, y: 0 },
            error: null
        };

        this.canvas = null;
        this.ctx = null;
        this.annotationOverlay = null;
        this.annotationCtx = null;
        this.annotationTool = null;
        this.sliceCanvas = null;
        this.sliceCtx = null;
        this.displayedSlice = null;

        this.init();
    }

    init() {
        this.render();
        this.bindEvents();
        this.initStore();
    }

    render() {
        this.container.innerHTML = `
            <div class="ct-viewer-container">
                <div class="ct-viewer-header">
                    <div class="ct-slice-info">
                        <span class="ct-view-type">轴位</span>
                        <span class="ct-slice-number">切片: <span id="ct-slice-num">0</span> / <span id="ct-slice-total">0</span></span>
                    </div>
                    <div class="ct-view-controls">
                        <div class="ct-zoom-control">
                            <button class="ct-btn ct-btn-sm" id="ct-zoom-out">-</button>
                            <span class="ct-zoom-value"><span id="ct-zoom-num">100</span>%</span>
                            <button class="ct-btn ct-btn-sm" id="ct-zoom-in">+</button>
                        </div>
                        <div class="ct-view-type-btns">
                            <button class="ct-btn ct-btn-sm ct-btn-active" data-view="axial">轴位</button>
                            <button class="ct-btn ct-btn-sm" data-view="coronal">冠状</button>
                            <button class="ct-btn ct-btn-sm" data-view="sagittal">矢状</button>
                        </div>
                        <div class="ct-export-dropdown">
                            <button class="ct-btn ct-btn-sm" id="ct-export-btn">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                导出
                            </button>
                            <div class="ct-export-menu" id="ct-export-menu" style="display: none;">
                                <button class="ct-export-item" data-format="nifti">导出为 NIfTI 掩码</button>
                                <button class="ct-export-item" data-format="json">导出为 JSON</button>
                                <button class="ct-export-item" data-format="dicom_sr">导出为 DICOM-SR</button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="ct-viewport-wrapper">
                    <div class="ct-main-viewport">
                        <canvas id="ct-main-canvas"></canvas>
                        <canvas id="ct-annotation-overlay" class="ct-annotation-overlay"></canvas>
                        <div class="ct-viewport-overlay" id="ct-viewport-overlay">
                            <div class="ct-loading" id="ct-loading" style="display: none;">
                                <div class="ct-spinner"></div>
                                <span>加载中...</span>
                            </div>
                            <div class="ct-error" id="ct-error" style="display: none;"></div>
                            <div class="ct-empty-state" id="ct-empty-state">
                                <div class="ct-empty-icon">🫁</div>
                                <p>点击或拖拽上传 CT 图像</p>
                                <p class="ct-empty-hint">支持 .nii 和 .nii.gz 格式</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="ct-control-bar">
                    <div class="ct-tool-buttons" id="ct-tool-buttons">
                        <button class="ct-tool-btn ct-tool-active" data-tool="pointer" title="指针 (V)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/>
                            </svg>
                        </button>
                        <button class="ct-tool-btn" data-tool="polygon" title="多边形 (P)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
                            </svg>
                        </button>
                        <button class="ct-tool-btn" data-tool="rectangle" title="矩形 (R)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                            </svg>
                        </button>
                        <button class="ct-tool-btn" data-tool="ellipse" title="椭圆 (E)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                            </svg>
                        </button>
                        <button class="ct-tool-btn" data-tool="line" title="线段 (L)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="19" x2="19" y2="5"/>
                            </svg>
                        </button>
                        <button class="ct-tool-btn" data-tool="brush" title="画笔 (B)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 19l7-7 3 3-7 7-3-3z"/>
                                <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/>
                            </svg>
                        </button>
                        <button class="ct-tool-btn" data-tool="arrow" title="箭头 (A)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"/>
                                <polyline points="12 5 19 12 12 19"/>
                            </svg>
                        </button>
                        <div class="ct-tool-divider"></div>
                        <button class="ct-tool-btn" id="ct-undo-btn" title="撤销 (Ctrl+Z)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="1 4 1 10 7 10"/>
                                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                            </svg>
                        </button>
                        <button class="ct-tool-btn" id="ct-delete-btn" title="删除选中 (Del)">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                        </button>
                    </div>

                    <div class="ct-slice-control">
                        <button class="ct-btn ct-btn-icon" id="ct-prev-slice">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="15 18 9 12 15 6"/>
                            </svg>
                        </button>
                        <input type="range"
                               id="ct-slice-slider"
                               min="0"
                               max="100"
                               value="0"
                               class="ct-slice-slider">
                        <button class="ct-btn ct-btn-icon" id="ct-next-slice">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="9 18 15 12 9 6"/>
                            </svg>
                        </button>
                        <input type="number"
                               id="ct-slice-input"
                               class="ct-slice-input"
                               min="0"
                               value="0">
                    </div>

                    <div class="ct-window-presets">
                        <button class="ct-preset-btn ct-preset-active" data-preset="lung">肺窗</button>
                        <button class="ct-preset-btn" data-preset="mediastinal">纵隔窗</button>
                        <button class="ct-preset-btn" data-preset="bone">骨窗</button>
                        <button class="ct-btn ct-btn-sm ct-custom-window-btn" id="ct-custom-window-btn">自定义</button>
                    </div>
                </div>

                <div class="ct-thumbnails-bar" id="ct-thumbnails-bar">
                    <div class="ct-thumbnails-scroll" id="ct-thumbnails-scroll"></div>
                </div>
            </div>

            <div class="ct-custom-window-modal" id="ct-custom-window-modal" style="display: none;">
                <div class="ct-modal-content">
                    <h3>自定义窗宽窗位</h3>
                    <div class="ct-modal-body">
                        <div class="ct-modal-field">
                            <label>窗位 (Center):</label>
                            <input type="range" id="ct-modal-center" min="-1000" max="1000" value="-600">
                            <span id="ct-modal-center-val">-600</span>
                        </div>
                        <div class="ct-modal-field">
                            <label>窗宽 (Width):</label>
                            <input type="range" id="ct-modal-width" min="1" max="4000" value="1500">
                            <span id="ct-modal-width-val">1500</span>
                        </div>
                    </div>
                    <div class="ct-modal-footer">
                        <button class="ct-btn" id="ct-modal-cancel">取消</button>
                        <button class="ct-btn ct-btn-primary" id="ct-modal-apply">应用</button>
                    </div>
                </div>
            </div>
        `;

        this.canvas = document.getElementById('ct-main-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.annotationOverlay = document.getElementById('ct-annotation-overlay');
        this.annotationCtx = this.annotationOverlay.getContext('2d');

        this.annotationTool = AnnotationTool.init(this.annotationOverlay, {
            onAnnotationCreated: (anno) => this.handleAnnotationCreated(anno),
            onAnnotationSelected: (anno) => this.handleAnnotationSelected(anno),
            onAnnotationDeleted: (anno) => this.handleAnnotationDeleted(anno)
        });

        this.setupDragDrop();
    }

    bindEvents() {
        document.getElementById('ct-prev-slice')?.addEventListener('click', () => this.prevSlice());
        document.getElementById('ct-next-slice')?.addEventListener('click', () => this.nextSlice());

        const slider = document.getElementById('ct-slice-slider');
        slider?.addEventListener('input', (e) => this.setSlice(parseInt(e.target.value)));

        const sliceInput = document.getElementById('ct-slice-input');
        sliceInput?.addEventListener('change', (e) => this.setSlice(parseInt(e.target.value)));

        document.getElementById('ct-zoom-in')?.addEventListener('click', () => this.zoomIn());
        document.getElementById('ct-zoom-out')?.addEventListener('click', () => this.zoomOut());

        document.querySelectorAll('[data-view]').forEach(btn => {
            btn.addEventListener('click', (e) => this.setViewType(e.target.dataset.view || e.target.closest('[data-view]').dataset.view));
        });

        document.querySelectorAll('[data-preset]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.target.closest('[data-preset]');
                if (target) this.setWindowPreset(target.dataset.preset);
            });
        });

        document.querySelectorAll('[data-tool]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.target.closest('[data-tool]');
                if (target) this.setTool(target.dataset.tool);
            });
        });

        document.getElementById('ct-undo-btn')?.addEventListener('click', () => this.undo());
        document.getElementById('ct-delete-btn')?.addEventListener('click', () => this.deleteSelected());

        document.getElementById('ct-custom-window-btn')?.addEventListener('click', () => this.showCustomWindowModal());

        const modalCenter = document.getElementById('ct-modal-center');
        const modalWidth = document.getElementById('ct-modal-width');
        modalCenter?.addEventListener('input', (e) => {
            document.getElementById('ct-modal-center-val').textContent = e.target.value;
        });
        modalWidth?.addEventListener('input', (e) => {
            document.getElementById('ct-modal-width-val').textContent = e.target.value;
        });

        document.getElementById('ct-modal-cancel')?.addEventListener('click', () => this.hideCustomWindowModal());
        document.getElementById('ct-modal-apply')?.addEventListener('click', () => this.applyCustomWindow());

        document.getElementById('ct-export-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const menu = document.getElementById('ct-export-menu');
            if (menu) menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
        });

        document.querySelectorAll('[data-format]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.target.closest('[data-format]');
                if (target) this.exportAnnotations(target.dataset.format);
            });
        });

        document.addEventListener('click', (e) => {
            const menu = document.getElementById('ct-export-menu');
            const btn = document.getElementById('ct-export-btn');
            if (menu && btn && !btn.contains(e.target) && !menu.contains(e.target)) {
                menu.style.display = 'none';
            }
        });

        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    }

    initStore() {
        CTStore.subscribe((state) => {
            this.state.windowCenter = state.windowCenter;
            this.state.windowWidth = state.windowWidth;
            this.state.currentSlice = state.currentSlice;
            this.state.zoom = state.zoom;
        });
    }

    setupDragDrop() {
        const viewport = this.container.querySelector('.ct-main-viewport');
        if (!viewport) return;

        viewport.addEventListener('dragover', (e) => {
            e.preventDefault();
            viewport.classList.add('ct-drag-over');
        });

        viewport.addEventListener('dragleave', () => {
            viewport.classList.remove('ct-drag-over');
        });

        viewport.addEventListener('drop', async (e) => {
            e.preventDefault();
            viewport.classList.remove('ct-drag-over');

            const file = e.dataTransfer.files[0];
            if (file) {
                await this.loadFile(file);
            }
        });
    }

    async loadFile(file) {
        const validExtensions = ['.nii', '.gz', '.nii.gz'];
        const ext = file.name.toLowerCase();
        const isValid = validExtensions.some(e => ext.endsWith(e));

        if (!isValid) {
            this.showError('不支持的文件格式，请上传 .nii 或 .nii.gz 文件');
            return;
        }

        this.showLoading(true);
        this.hideError();

        try {
            const result = await NIfTILoader.loadFromFile(file);

            this.state.niftiData = result.data;
            this.state.shape = result.shape;
            this.state.spacing = result.spacing;
            this.state.loaded = true;
            this.state.currentSlice = 0;

            CTStore.setImageMetadata(
                result.shape,
                result.spacing,
                [result.spacing[0], result.spacing[1]],
                result.spacing[2]
            );

            this.updateSliceControls();
            this.renderSlice();

            document.getElementById('ct-empty-state').style.display = 'none';

            if (this.options.annotationSetId) {
                await this.loadAnnotations();
            }
        } catch (e) {
            this.showError('图像加载失败: ' + e.message);
            this.options.onError(e);
        } finally {
            this.showLoading(false);
        }
    }

    async loadAnnotations() {
        if (!this.options.annotationSetId) return;

        try {
            await CTStore.loadAnnotationSet(this.options.annotationSetId);
            const annotations = CTStore.getAnnotationsForSlice(this.state.currentSlice);
            this.annotationTool.setAnnotations(annotations);
        } catch (e) {
            console.error('加载标注失败:', e);
        }
    }

    async loadFromUrl(url) {
        this.showLoading(true);
        this.hideError();

        try {
            const result = await NIfTILoader.loadFromUrl(url);

            this.state.niftiData = result.data;
            this.state.shape = result.shape;
            this.state.spacing = result.spacing;
            this.state.loaded = true;
            this.state.currentSlice = 0;

            CTStore.setImageMetadata(
                result.shape,
                result.spacing,
                [result.spacing[0], result.spacing[1]],
                result.spacing[2]
            );

            this.updateSliceControls();
            this.renderSlice();

            document.getElementById('ct-empty-state').style.display = 'none';

            if (this.options.annotationSetId) {
                await this.loadAnnotations();
            }
        } catch (e) {
            this.showError('图像加载失败: ' + e.message);
            this.options.onError(e);
        } finally {
            this.showLoading(false);
        }
    }

    renderSlice() {
        if (!this.state.loaded || !this.state.niftiData) return;

        const sliceData = NIfTILoader.getSlice(
            this.state.niftiData,
            this.state.shape,
            this.state.currentSlice,
            this.state.viewType
        );

        if (!sliceData) return;

        const windowedData = WindowingTool.applyWindowing(
            sliceData.data,
            this.state.windowCenter,
            this.state.windowWidth
        );

        if (!this.displayedSlice ||
            this.displayedSlice.width !== sliceData.width ||
            this.displayedSlice.height !== sliceData.height) {
            this.displayedSlice = {
                width: sliceData.width,
                height: sliceData.height,
                data: new Uint8Array(sliceData.width * sliceData.height)
            };
        }

        this.displayedSlice.data.set(windowedData);

        this.canvas.width = sliceData.width;
        this.canvas.height = sliceData.height;
        this.annotationOverlay.width = sliceData.width;
        this.annotationOverlay.height = sliceData.height;

        const imageData = this.ctx.createImageData(sliceData.width, sliceData.height);
        imageData.data.set(this.displayedSlice.data);
        for (let i = 3; i < imageData.data.length; i += 4) {
            imageData.data[i] = 255;
        }

        this.ctx.putImageData(imageData, 0, 0);
        this.annotationTool.redraw();

        this.updateAnnotationsForCurrentSlice();
    }

    updateAnnotationsForCurrentSlice() {
        const annotations = CTStore.getAnnotationsForSlice(this.state.currentSlice);
        this.annotationTool.setAnnotations(annotations);
    }

    setSlice(slice) {
        const maxSlice = this.state.shape[2] - 1;
        slice = Math.max(0, Math.min(slice, maxSlice));

        if (slice !== this.state.currentSlice) {
            this.state.currentSlice = slice;
            CTStore.setSlice(slice);
            this.updateSliceControls();
            this.renderSlice();
            this.options.onSliceChange(slice);
        }
    }

    nextSlice() {
        this.setSlice(this.state.currentSlice + 1);
    }

    prevSlice() {
        this.setSlice(this.state.currentSlice - 1);
    }

    setViewType(viewType) {
        this.state.viewType = viewType;

        document.querySelectorAll('[data-view]').forEach(btn => {
            btn.classList.toggle('ct-btn-active', btn.dataset.view === viewType);
        });

        const viewNames = { axial: '轴位', coronal: '冠状位', sagittal: '矢状位' };
        const viewTypeEl = this.container.querySelector('.ct-view-type');
        if (viewTypeEl) {
            viewTypeEl.textContent = viewNames[viewType] || viewType;
        }

        if (this.state.loaded) {
            this.updateSliceControls();
            this.renderSlice();
        }
    }

    setWindowPreset(preset) {
        const presets = {
            lung: { center: -600, width: 1500 },
            mediastinal: { center: 40, width: 400 },
            bone: { center: 300, width: 2000 },
            brain: { center: 40, width: 80 },
            abdomen: { center: 50, width: 400 },
            liver: { center: 30, width: 150 }
        };

        const p = presets[preset];
        if (p) {
            this.state.windowCenter = p.center;
            this.state.windowWidth = p.width;
            CTStore.setWindow(p.center, p.width);

            document.querySelectorAll('[data-preset]').forEach(btn => {
                btn.classList.toggle('ct-preset-active', btn.dataset.preset === preset);
            });

            if (this.state.loaded) {
                this.renderSlice();
            }
        }
    }

    setTool(tool) {
        this.annotationTool.setTool(tool);

        document.querySelectorAll('[data-tool]').forEach(btn => {
            btn.classList.toggle('ct-tool-active', btn.dataset.tool === tool);
        });
    }

    zoomIn() {
        this.state.zoom = Math.min(this.state.zoom * 1.2, 10);
        this.applyZoom();
    }

    zoomOut() {
        this.state.zoom = Math.max(this.state.zoom / 1.2, 0.1);
        this.applyZoom();
    }

    applyZoom() {
        document.getElementById('ct-zoom-num').textContent = Math.round(this.state.zoom * 100);
        CTStore.setZoom(this.state.zoom);

        const viewport = this.container.querySelector('.ct-main-viewport');
        if (viewport && this.canvas) {
            this.canvas.style.transform = `scale(${this.state.zoom})`;
            this.annotationOverlay.style.transform = `scale(${this.state.zoom})`;
        }
    }

    undo() {
        this.annotationTool.undo();
    }

    deleteSelected() {
        const selected = this.annotationTool.selectedAnnotation;
        if (selected) {
            this.annotationTool.deleteSelected();
        }
    }

    handleKeyboard(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        switch (e.key) {
            case 'ArrowLeft':
                this.prevSlice();
                break;
            case 'ArrowRight':
                this.nextSlice();
                break;
            case 'v':
            case 'V':
                this.setTool('pointer');
                break;
            case 'p':
            case 'P':
                this.setTool('polygon');
                break;
            case 'r':
            case 'R':
                this.setTool('rectangle');
                break;
            case 'e':
            case 'E':
                this.setTool('ellipse');
                break;
            case 'l':
            case 'L':
                this.setTool('line');
                break;
            case 'b':
            case 'B':
                this.setTool('brush');
                break;
            case 'a':
            case 'A':
                this.setTool('arrow');
                break;
            case 'Delete':
            case 'Backspace':
                this.deleteSelected();
                break;
            case 'z':
            case 'Z':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    this.undo();
                }
                break;
        }
    }

    async handleAnnotationCreated(annotation) {
        if (this.options.annotationSetId) {
            annotation.ct_image_id = this.options.ctImageId;
            const created = await CTStore.createAnnotation(annotation);
            if (created) {
                this.options.onAnnotationCreated(created);
            }
        } else {
            this.options.onAnnotationCreated(annotation);
        }
    }

    handleAnnotationSelected(annotation) {
        CTStore.setActiveAnnotation(annotation?.annotation_id || null);
        this.options.onAnnotationSelected(annotation);
    }

    async handleAnnotationDeleted(annotation) {
        if (this.options.annotationSetId && annotation.annotation_id) {
            await CTStore.deleteAnnotation(annotation.annotation_id);
        }
        this.options.onAnnotationDeleted(annotation);
    }

    updateSliceControls() {
        const slider = document.getElementById('ct-slice-slider');
        const sliceNum = document.getElementById('ct-slice-num');
        const sliceTotal = document.getElementById('ct-slice-total');
        const sliceInput = document.getElementById('ct-slice-input');

        if (slider) slider.max = this.state.shape[2] - 1;
        if (sliceTotal) sliceTotal.textContent = this.state.shape[2] - 1;
        if (sliceNum) sliceNum.textContent = this.state.currentSlice;
        if (sliceInput) {
            sliceInput.max = this.state.shape[2] - 1;
            sliceInput.value = this.state.currentSlice;
        }

        this.renderThumbnails();
    }

    renderThumbnails() {
        const container = document.getElementById('ct-thumbnails-scroll');
        if (!container || !this.state.loaded) return;

        container.innerHTML = '';
        const thumbSize = 64;
        const total = this.state.shape[2];
        const displayCount = Math.min(total, 20);
        const step = Math.max(1, Math.floor(total / displayCount));

        for (let i = 0; i < total; i += step) {
            const thumbCanvas = document.createElement('canvas');
            thumbCanvas.width = thumbSize;
            thumbCanvas.height = thumbSize;
            thumbCanvas.className = 'ct-thumbnail';
            if (i === this.state.currentSlice) {
                thumbCanvas.classList.add('ct-thumbnail-active');
            }

            const sliceData = NIfTILoader.getSlice(
                this.state.niftiData,
                this.state.shape,
                i,
                'axial'
            );

            if (sliceData) {
                const windowed = WindowingTool.applyWindowing(
                    sliceData.data,
                    this.state.windowCenter,
                    this.state.windowWidth
                );

                const scaleX = thumbSize / sliceData.width;
                const scaleY = thumbSize / sliceData.height;
                const scale = Math.min(scaleX, scaleY);

                const imgData = thumbCanvas.getContext('2d').createImageData(thumbSize, thumbSize);
                for (let y = 0; y < thumbSize; y++) {
                    for (let x = 0; x < thumbSize; x++) {
                        const srcX = Math.floor(x / scale);
                        const srcY = Math.floor(y / scale);
                        if (srcX < sliceData.width && srcY < sliceData.height) {
                            const srcIdx = srcY * sliceData.width + srcX;
                            const dstIdx = (y * thumbSize + x) * 4;
                            imgData.data[dstIdx] = windowed[srcIdx];
                            imgData.data[dstIdx + 1] = windowed[srcIdx];
                            imgData.data[dstIdx + 2] = windowed[srcIdx];
                            imgData.data[dstIdx + 3] = 255;
                        }
                    }
                }

                thumbCanvas.getContext('2d').putImageData(imgData, 0, 0);
            }

            const label = document.createElement('span');
            label.className = 'ct-thumbnail-label';
            label.textContent = i;

            const wrapper = document.createElement('div');
            wrapper.className = 'ct-thumbnail-wrapper';
            wrapper.appendChild(thumbCanvas);
            wrapper.appendChild(label);

            wrapper.addEventListener('click', () => this.setSlice(i));

            container.appendChild(wrapper);
        }
    }

    showCustomWindowModal() {
        document.getElementById('ct-custom-window-modal').style.display = 'flex';
        document.getElementById('ct-modal-center').value = this.state.windowCenter;
        document.getElementById('ct-modal-width').value = this.state.windowWidth;
        document.getElementById('ct-modal-center-val').textContent = this.state.windowCenter;
        document.getElementById('ct-modal-width-val').textContent = this.state.windowWidth;
    }

    hideCustomWindowModal() {
        document.getElementById('ct-custom-window-modal').style.display = 'none';
    }

    applyCustomWindow() {
        const center = parseInt(document.getElementById('ct-modal-center').value);
        const width = parseInt(document.getElementById('ct-modal-width').value);

        document.querySelectorAll('[data-preset]').forEach(btn => {
            btn.classList.remove('ct-preset-active');
        });

        this.state.windowCenter = center;
        this.state.windowWidth = width;
        CTStore.setWindow(center, width);

        if (this.state.loaded) {
            this.renderSlice();
        }

        this.hideCustomWindowModal();
    }

    showLoading(show) {
        const el = document.getElementById('ct-loading');
        if (el) el.style.display = show ? 'flex' : 'none';
        this.state.loading = show;
    }

    showError(message) {
        const el = document.getElementById('ct-error');
        if (el) {
            el.textContent = message;
            el.style.display = 'block';
        }
    }

    hideError() {
        const el = document.getElementById('ct-error');
        if (el) el.style.display = 'none';
    }

    getAnnotations() {
        return this.annotationTool?.getAnnotations() || [];
    }

    clearAnnotations() {
        this.annotationTool?.clearAll();
    }

    async exportAnnotations(format) {
        const annotations = this.getAnnotations();
        if (annotations.length === 0) {
            this.showError('没有可导出的标注');
            return;
        }

        const menu = document.getElementById('ct-export-menu');
        if (menu) menu.style.display = 'none';

        const setId = this.options.annotationSetId || 'export';
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);

        try {
            switch (format) {
                case 'nifti':
                    if (!this.state.loaded) {
                        this.showError('请先加载 CT 图像');
                        return;
                    }
                    const filename = `mask_${setId}_${timestamp}.nii`;
                    NIfTIMaskExporter.downloadMask(
                        annotations,
                        this.state.shape,
                        this.state.spacing,
                        filename
                    );
                    break;

                case 'json':
                    const jsonData = JSON.stringify({
                        annotations,
                        metadata: {
                            shape: this.state.shape,
                            spacing: this.state.spacing,
                            exported_at: new Date().toISOString()
                        }
                    }, null, 2);
                    const jsonBlob = new Blob([jsonData], { type: 'application/json' });
                    this.downloadBlob(jsonBlob, `annotations_${setId}_${timestamp}.json`);
                    break;

                case 'dicom_sr':
                    if (this.options.annotationSetId) {
                        const result = await CTApiClient.exportAnnotationSet(
                            this.options.annotationSetId,
                            'dicom_sr'
                        );
                        if (result.success && result.path) {
                            const response = await fetch(`/api/annotation/sets/${this.options.annotationSetId}/export?format=dicom_sr`);
                            const text = await response.text();
                            const blob = new Blob([text], { type: 'application/xml' });
                            this.downloadBlob(blob, `annotation_${setId}_${timestamp}.xml`);
                        }
                    } else {
                        this.showError('DICOM-SR 导出需要标注集 ID');
                    }
                    break;

                default:
                    this.showError('不支持的导出格式');
            }
        } catch (e) {
            this.showError('导出失败: ' + e.message);
            this.options.onError(e);
        }
    }

    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    destroy() {
        this.annotationTool?.destroy();
        this.container.innerHTML = '';
    }
}

window.CTViewer = CTViewer;
