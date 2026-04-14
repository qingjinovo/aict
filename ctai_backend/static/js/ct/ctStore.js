/**
 * CT 医学影像状态管理
 * 模拟 Zustand Store 的功能
 */

const CTStore = {
    state: {
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
        pixelSpacing: [1.0, 1.0],
        sliceThickness: 2.5,
        listeners: new Set()
    },

    subscribe(listener) {
        this.state.listeners.add(listener);
        return () => this.state.listeners.delete(listener);
    },

    notify() {
        this.state.listeners.forEach(listener => listener(this.state));
    },

    getState() {
        return this.state;
    },

    setState(updates) {
        Object.assign(this.state, updates);
        this.notify();
    },

    setSlice(slice) {
        const maxSlice = this.state.shape[2] - 1;
        const newSlice = Math.max(0, Math.min(slice, maxSlice));
        this.setState({ currentSlice: newSlice });
    },

    nextSlice() {
        this.setSlice(this.state.currentSlice + 1);
    },

    prevSlice() {
        this.setSlice(this.state.currentSlice - 1);
    },

    setViewType(viewType) {
        this.setState({ viewType });
    },

    setWindow(center, width) {
        this.setState({
            windowCenter: center,
            windowWidth: width
        });
    },

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
            this.setState(p);
        }
    },

    setTool(tool) {
        this.setState({ selectedTool: tool });
    },

    setZoom(zoom) {
        this.setState({ zoom: Math.max(0.1, Math.min(zoom, 10)) });
    },

    setPan(x, y) {
        this.setState({ pan: { x, y } });
    },

    setLoading(isLoading) {
        this.setState({ isLoading });
    },

    setError(error) {
        this.setState({ error });
    },

    clearError() {
        this.setState({ error: null });
    },

    async loadImage(buffer) {
        this.setLoading(true);
        this.clearError();

        try {
            const data = new Float32Array(buffer);
            this.setState({
                originalData: data,
                imageData: data,
                isLoading: false
            });
            return true;
        } catch (e) {
            this.setError('图像加载失败: ' + e.message);
            this.setLoading(false);
            return false;
        }
    },

    setImageMetadata(shape, spacing, pixelSpacing, sliceThickness) {
        this.setState({
            shape,
            spacing,
            pixelSpacing: pixelSpacing || [1.0, 1.0],
            sliceThickness: sliceThickness || 2.5
        });
    },

    setActiveAnnotationSet(setId) {
        this.setState({ activeAnnotationSet: setId });
    },

    setActiveAnnotation(annoId) {
        this.setState({ activeAnnotation: annoId });
    },

    addAnnotationToSet(setId, annotation) {
        const sets = new Map(this.state.annotationSets);
        if (!sets.has(setId)) {
            sets.set(setId, { annotations: [] });
        }
        const set = sets.get(setId);
        set.annotations.push(annotation);
        sets.set(setId, set);
        this.setState({ annotationSets: sets });
    },

    updateAnnotationInSet(setId, annoId, updates) {
        const sets = new Map(this.state.annotationSets);
        if (sets.has(setId)) {
            const set = sets.get(setId);
            const idx = set.annotations.findIndex(a => a.annotation_id === annoId);
            if (idx !== -1) {
                set.annotations[idx] = { ...set.annotations[idx], ...updates };
                sets.set(setId, set);
                this.setState({ annotationSets: sets });
            }
        }
    },

    removeAnnotationFromSet(setId, annoId) {
        const sets = new Map(this.state.annotationSets);
        if (sets.has(setId)) {
            const set = sets.get(setId);
            set.annotations = set.annotations.filter(a => a.annotation_id !== annoId);
            sets.set(setId, set);
            this.setState({ annotationSets: sets });
        }
    },

    getAnnotationsForSlice(sliceIndex) {
        const setId = this.state.activeAnnotationSet;
        if (!setId) return [];

        const sets = this.state.annotationSets;
        if (!sets.has(setId)) return [];

        const set = sets.get(setId);
        return set.annotations.filter(a =>
            a.graphic_data && a.graphic_data.slice_index === sliceIndex
        );
    },

    async createAnnotation(data) {
        const setId = this.state.activeAnnotationSet;
        if (!setId) {
            this.setError('未选择标注集');
            return null;
        }

        try {
            const result = await CTApiClient.createAnnotation(setId, {
                ...data,
                ct_image_id: data.ct_image_id || setId
            });

            if (result.success) {
                this.addAnnotationToSet(setId, result.data);
                return result.data;
            }
        } catch (e) {
            this.setError('创建标注失败: ' + e.message);
        }
        return null;
    },

    async updateAnnotation(annoId, updates) {
        const setId = this.state.activeAnnotationSet;
        if (!setId) return false;

        try {
            const result = await CTApiClient.updateAnnotation(setId, annoId, updates);
            if (result.success) {
                this.updateAnnotationInSet(setId, annoId, updates);
                return true;
            }
        } catch (e) {
            this.setError('更新标注失败: ' + e.message);
        }
        return false;
    },

    async deleteAnnotation(annoId) {
        const setId = this.state.activeAnnotationSet;
        if (!setId) return false;

        try {
            const result = await CTApiClient.deleteAnnotation(setId, annoId);
            if (result.success) {
                this.removeAnnotationFromSet(setId, annoId);
                return true;
            }
        } catch (e) {
            this.setError('删除标注失败: ' + e.message);
        }
        return false;
    },

    async confirmAnnotation(annoId) {
        const setId = this.state.activeAnnotationSet;
        if (!setId) return false;

        try {
            const result = await CTApiClient.confirmAnnotation(setId, annoId);
            if (result.success) {
                this.updateAnnotationInSet(setId, annoId, {
                    workflow_status: 'confirmed'
                });
                return true;
            }
        } catch (e) {
            this.setError('确认标注失败: ' + e.message);
        }
        return false;
    },

    async loadAnnotationSet(setId) {
        this.setLoading(true);
        this.clearError();

        try {
            const result = await CTApiClient.getAnnotationSet(setId);
            if (result.success) {
                const sets = new Map(this.state.annotationSets);
                sets.set(setId, result.data);
                this.setState({
                    annotationSets: sets,
                    activeAnnotationSet: setId,
                    isLoading: false
                });
                return result.data;
            }
        } catch (e) {
            this.setError('加载标注集失败: ' + e.message);
        }
        this.setLoading(false);
        return null;
    },

    reset() {
        this.setState({
            imageData: null,
            originalData: null,
            shape: [0, 0, 0],
            currentSlice: 0,
            viewType: 'axial',
            windowCenter: -600,
            windowWidth: 1500,
            activeAnnotation: null,
            selectedTool: 'pointer',
            isLoading: false,
            error: null,
            zoom: 1.0,
            pan: { x: 0, y: 0 }
        });
    }
};

window.CTStore = CTStore;
