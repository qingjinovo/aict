/**
 * 窗宽窗位工具
 * 提供 HU 值转换和窗口调整功能
 */

const WindowingTool = {
    presets: {
        lung: { name: '肺窗', center: -600, width: 1500 },
        mediastinal: { name: '纵隔窗', center: 40, width: 400 },
        bone: { name: '骨窗', center: 300, width: 2000 },
        brain: { name: '脑窗', center: 40, width: 80 },
        abdomen: { name: '腹窗', center: 50, width: 400 },
        liver: { name: '肝脏窗', center: 30, width: 150 }
    },

    applyWindowing(huArray, windowCenter, windowWidth, outputDtype = Uint8Array) {
        if (huArray == null || windowWidth <= 0) {
            return null;
        }

        const minValue = windowCenter - windowWidth / 2;
        const maxValue = windowCenter + windowWidth / 2;
        const output = new outputDtype(huArray.length);

        for (let i = 0; i < huArray.length; i++) {
            let val = huArray[i];
            if (val < minValue) val = minValue;
            if (val > maxValue) val = maxValue;
            output[i] = Math.round(((val - minValue) / windowWidth) * 255);
        }

        return output;
    },

    applyPreset(huArray, presetName) {
        const preset = this.presets[presetName];
        if (!preset) return null;
        return this.applyWindowing(huArray, preset.center, preset.width);
    },

    getPreset(name) {
        return this.presets[name] || null;
    },

    getAllPresets() {
        return { ...this.presets };
    },

    calculateOptimalWindowing(huArray, percentileLow = 5, percentileHigh = 95) {
        if (!huArray || huArray.length === 0) {
            return { center: 40, width: 400 };
        }

        const sorted = Float32Array.from(huArray).sort();
        const lowIdx = Math.floor(sorted.length * percentileLow / 100);
        const highIdx = Math.floor(sorted.length * percentileHigh / 100);

        const minHu = sorted[lowIdx];
        const maxHu = sorted[highIdx];

        const center = Math.round((minHu + maxHu) / 2);
        const width = Math.round(maxHu - minHu);

        return { center, width: Math.max(width, 1) };
    },

    getHUValueRange() {
        return {
            air: { min: -1200, max: -900 },
            lung: { min: -1000, max: -400 },
            fat: { min: -150, max: -50 },
            water: { min: -10, max: 10 },
            muscle: { min: 20, max: 60 },
            blood: { min: 30, max: 70 },
            liver: { min: 40, max: 60 },
            bone: { min: 400, max: 3000 },
            contrast: { min: 100, max: 300 }
        };
    },

    getDisplayRange(windowCenter, windowWidth) {
        return {
            min: windowCenter - windowWidth / 2,
            max: windowCenter + windowWidth / 2
        };
    }
};

const HUConverter = {
    toHU(pixelArray, slope = 1.0, intercept = -1024) {
        const output = new Float32Array(pixelArray.length);
        for (let i = 0; i < pixelArray.length; i++) {
            output[i] = pixelArray[i] * slope + intercept;
        }
        return output;
    },

    fromHU(huArray, slope = 1.0, intercept = -1024) {
        if (slope === 0) return null;
        const output = new Float32Array(huArray.length);
        for (let i = 0; i < huArray.length; i++) {
            output[i] = (huArray[i] - intercept) / slope;
        }
        return output;
    },

    getTissueRange(tissue) {
        const ranges = {
            air: { min: -1200, max: -900 },
            lung: { min: -1000, max: -400 },
            fat: { min: -150, max: -50 },
            water: { min: -10, max: 10 },
            muscle: { min: 20, max: 60 },
            blood: { min: 30, max: 70 },
            liver: { min: 40, max: 60 },
            bone: { min: 400, max: 3000 },
            contrast: { min: 100, max: 300 }
        };
        return ranges[tissue.toLowerCase()] || { min: 0, max: 0 };
    },

    getStandardValues() {
        return {
            AIR: -1000,
            WATER: 0,
            BONE_MIN: 400,
            FAT: -100,
            MUSCLE: 40,
            BLOOD: 50
        };
    }
};

window.WindowingTool = WindowingTool;
window.HUConverter = HUConverter;
