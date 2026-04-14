/**
 * NIfTI 医学影像解析器 (浏览器端)
 * 支持 .nii 和 .nii.gz 格式的CT图像加载
 */

const NIfTILoader = {
    HEADER_SIZE: 352,
    MAGIC: { NI1: 'ni1\x00', N_PLUS_1: 'n+1\x00' },

    DTYPE_MAP: {
        2: { name: 'UINT8', size: 1 },
        4: { name: 'INT16', size: 2 },
        8: { name: 'INT32', size: 4 },
        16: { name: 'FLOAT32', size: 4 },
        64: { name: 'FLOAT64', size: 8 },
        256: { name: 'INT8', size: 1 },
        512: { name: 'UINT16', size: 2 },
        768: { name: 'UINT32', size: 4 },
        1024: { name: 'INT64', size: 8 },
        1280: { name: 'UINT64', size: 8 }
    },

    async loadFromFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = (e) => {
                try {
                    const buffer = e.target.result;
                    const result = this.parseBuffer(buffer, file.name);
                    resolve(result);
                } catch (err) {
                    reject(err);
                }
            };

            reader.onerror = () => reject(new Error('文件读取失败'));

            const isGzipped = file.name.toLowerCase().endsWith('.gz') ||
                             file.name.toLowerCase().endsWith('.nii.gz');
            reader.readAsArrayBuffer(file);
        });
    },

    async loadFromUrl(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`加载失败: ${response.status}`);
        }
        const buffer = await response.arrayBuffer();
        return this.parseBuffer(buffer, url);
    },

    parseBuffer(buffer, filename) {
        const bytes = new Uint8Array(buffer);
        const isGzippedFile = filename.toLowerCase().endsWith('.gz') ||
                             filename.toLowerCase().endsWith('.nii.gz');

        if (isGzippedFile || this.isGzipped(bytes)) {
            return this.parseGzipped(bytes);
        }

        return this.parseStandard(bytes);
    },

    isGzipped(bytes) {
        if (bytes.length < 2) return false;
        return bytes[0] === 0x1f && bytes[1] === 0x8b;
    },

    parseGzipped(bytes) {
        try {
            const decompressed = this.decompressGzip(bytes);
            return this.parseStandard(new Uint8Array(decompressed));
        } catch (e) {
            throw new Error('GZip解压失败: ' + e.message);
        }
    },

    decompressGzip(bytes) {
        const cs = new pako.Inflate();
        cs.push(bytes, true);
        if (cs.err) {
            throw new Error(cs.msg);
        }
        return cs.result;
    },

    parseStandard(bytes) {
        if (bytes.length < this.HEADER_SIZE) {
            throw new Error('文件过小，不是有效的NIfTI文件');
        }

        const header = this.parseHeader(bytes);
        const dataOffset = Math.floor(header.vox_offset);
        const dataSize = this.calculateDataSize(header);

        if (bytes.length < dataOffset + dataSize) {
            throw new Error('文件数据不完整');
        }

        const dataBytes = bytes.slice(dataOffset, dataOffset + dataSize);
        const data = this.parseData(dataBytes, header);

        return {
            header,
            data,
            shape: header.shape,
            spacing: header.voxel_dims,
            filename
        };
    },

    parseHeader(bytes) {
        const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);

        const sizeof_hdr = view.getInt32(0, true);
        if (sizeof_hdr !== 348) {
            throw new Error('无效的NIfTI头文件');
        }

        const dim = [
            view.getInt16(40, true),
            view.getInt16(42, true),
            view.getInt16(44, true),
            view.getInt16(46, true),
            view.getInt16(48, true),
            view.getInt16(50, true),
            view.getInt16(52, true),
            view.getInt16(54, true)
        ];

        const pixel_dims = [
            view.getFloat32(56, true),
            view.getFloat32(60, true),
            view.getFloat32(64, true),
            view.getFloat32(68, true),
            view.getFloat32(72, true),
            view.getFloat32(76, true),
            view.getFloat32(80, true),
            view.getFloat32(84, true)
        ];

        const datatype = view.getInt16(70, true);
        const bitpix = view.getInt16(72, true);
        const vox_offset = view.getFloat32(108, true);

        const slope = view.getFloat32(124, true);
        const inter = view.getFloat32(128, true);

        const descrip = this.readString(bytes, 148, 80);
        const magic = this.readString(bytes, 344, 4);

        return {
            sizeof_hdr,
            dim,
            shape: [dim[1] || 0, dim[2] || 0, dim[3] || 0],
            pixel_dims,
            voxel_dims: [
                pixel_dims[1] || 1.0,
                pixel_dims[2] || 1.0,
                pixel_dims[3] || 1.0
            ],
            datatype,
            bitpix,
            vox_offset,
            slope: slope || 1.0,
            inter: inter || 0.0,
            descrip,
            magic,
            number_of_slices: dim[3] || 1
        };
    },

    readString(bytes, start, length) {
        let end = start;
        while (end < start + length && bytes[end] !== 0) {
            end++;
        }
        return new TextDecoder('utf-8', { fatal: false })
            .decode(bytes.slice(start, end))
            .trim();
    },

    calculateDataSize(header) {
        const dtype = this.DTYPE_MAP[header.datatype];
        if (!dtype) {
            throw new Error('不支持的数据类型: ' + header.datatype);
        }

        const totalVoxels = header.shape[0] * header.shape[1] * header.shape[2];
        return totalVoxels * dtype.size;
    },

    parseData(bytes, header) {
        const dtype = this.DTYPE_MAP[header.datatype];
        if (!dtype) {
            throw new Error('不支持的数据类型: ' + header.datatype);
        }

        const shape = header.shape;
        const totalVoxels = shape[0] * shape[1] * shape[2];

        let array;
        switch (dtype.name) {
            case 'UINT8':
                array = new Uint8Array(bytes);
                break;
            case 'INT16':
                array = new Int16Array(bytes.buffer, bytes.byteOffset, totalVoxels);
                break;
            case 'INT32':
                array = new Int32Array(bytes.buffer, bytes.byteOffset, totalVoxels);
                break;
            case 'FLOAT32':
                array = new Float32Array(bytes.buffer, bytes.byteOffset, totalVoxels);
                break;
            case 'FLOAT64':
                array = new Float64Array(bytes.buffer, bytes.byteOffset, totalVoxels);
                break;
            case 'UINT16':
                array = new Uint16Array(bytes.buffer, bytes.byteOffset, totalVoxels);
                break;
            case 'INT8':
                array = new Int8Array(bytes.buffer, bytes.byteOffset, totalVoxels);
                break;
            default:
                throw new Error('不支持的数据类型: ' + dtype.name);
        }

        let result;
        if (array instanceof Float32Array) {
            result = array;
        } else {
            result = new Float32Array(array);
        }

        if (header.slope && header.slope !== 1.0 && header.slope !== 0) {
            for (let i = 0; i < result.length; i++) {
                result[i] = result[i] * header.slope + header.inter;
            }
        } else if (header.inter && header.inter !== 0) {
            for (let i = 0; i < result.length; i++) {
                result[i] = result[i] + header.inter;
            }
        }

        return result;
    },

    getSlice(data, shape, sliceIndex, viewType = 'axial') {
        const [dimX, dimY, dimZ] = shape;
        const sliceSize = dimX * dimY;

        if (viewType === 'axial') {
            const start = sliceIndex * sliceSize;
            return {
                data: data.slice(start, start + sliceSize),
                width: dimX,
                height: dimY
            };
        }

        if (viewType === 'coronal') {
            const result = new Float32Array(dimX * dimZ);
            for (let z = 0; z < dimZ; z++) {
                for (let x = 0; x < dimX; x++) {
                    const srcIdx = z * sliceSize + x * dimY + sliceIndex;
                    const dstIdx = z * dimX + x;
                    result[dstIdx] = data[srcIdx];
                }
            }
            return { data: result, width: dimX, height: dimZ };
        }

        if (viewType === 'sagittal') {
            const result = new Float32Array(dimY * dimZ);
            for (let z = 0; z < dimZ; z++) {
                for (let y = 0; y < dimY; y++) {
                    const srcIdx = z * sliceSize + sliceIndex * dimY + y;
                    const dstIdx = z * dimY + y;
                    result[dstIdx] = data[srcIdx];
                }
            }
            return { data: result, width: dimY, height: dimZ };
        }

        return null;
    }
};

if (typeof pako === 'undefined') {
    console.warn('pako (GZip库) 未加载，GZip压缩的NIfTI文件可能无法加载');
}

window.NIfTILoader = NIfTILoader;
