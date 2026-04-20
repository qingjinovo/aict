"""
SAM-Med3D 模型推理服务
直接集成 PyTorch 模型进行医学影像分割推理
"""

import os
import sys
import json
import logging
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

try:
    import SimpleITK as sitk
    SIMPLEITK_AVAILABLE = True
except ImportError:
    SIMPLEITK_AVAILABLE = False
    sitk = None

try:
    import torchio as tio
    TORCHIO_AVAILABLE = True
except ImportError:
    TORCHIO_AVAILABLE = False
    tio = None

logger = logging.getLogger(__name__)

MODEL_CHECKPOINT_PATH = os.environ.get(
    'SAM3D_MODEL_PATH',
    'D:/Study/Project/JSJDS/demo/Model/sam_med3d_turbo.pth'
)

SAM3D_CODE_PATH = os.environ.get(
    'SAM3D_CODE_PATH',
    'D:/Study/Github/SAM-Med3D'
)


class SAM3DInferenceService:
    """
    SAM-Med3D 模型推理服务

    输入: CT NIfTI 图像文件 (必需)
          GT NIfTI 标注文件 (可选，用于生成提示点)
    输出: 预测分割 NIfTI 文件
    """

    def __init__(self, checkpoint_path: str = None, code_path: str = None):
        self.checkpoint_path = checkpoint_path or MODEL_CHECKPOINT_PATH
        self.code_path = code_path or SAM3D_CODE_PATH
        self.model = None
        self.device = None

    def setup(self) -> bool:
        """
        初始化模型

        Returns:
            是否成功初始化
        """
        try:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            logger.info(f'SAM3D 使用设备: {self.device}')

            if not os.path.exists(self.checkpoint_path):
                logger.warning(f'模型文件不存在: {self.checkpoint_path}，将使用模拟模式')
                return False

            sys.path.insert(0, self.code_path)

            from segment_anything import build_sam3D, sam_model_registry3D

            try:
                checkpoint = torch.load(self.checkpoint_path, map_location='cpu')
                if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                    checkpoint = checkpoint['model_state_dict']

                embed_dim = None
                if 'image_encoder.patch_embed.proj.weight' in checkpoint:
                    weight_shape = checkpoint['image_encoder.patch_embed.proj.weight'].shape
                    embed_dim = weight_shape[0]
                    print(f'Detected embed_dim from checkpoint: {embed_dim}')

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pth')
                torch.save(checkpoint, temp_file.name)
                temp_file.close()

                if embed_dim == 768:
                    print('Using build_sam3D_vit_b_ori (embed_dim=768)')
                    self.model = sam_model_registry3D["vit_b_ori"](checkpoint=temp_file.name)
                elif embed_dim == 384:
                    print('Using build_sam3D_vit_b (embed_dim=384)')
                    self.model = build_sam3D(checkpoint=temp_file.name)
                elif embed_dim == 1280:
                    print('Using build_sam3D_vit_h (embed_dim=1280)')
                    self.model = build_sam3D(checkpoint=temp_file.name)
                else:
                    print(f'Unknown embed_dim {embed_dim}, trying default build_sam3D')
                    self.model = build_sam3D(checkpoint=temp_file.name)

                self.model = self.model.to(self.device)
                self.model.eval()
                os.unlink(temp_file.name)
                print('SAM-Med3D 模型加载成功')
                return True
            except Exception as e:
                print(f'SAM-Med3D 模型加载失败: {e}')
                import traceback
                print(traceback.format_exc())
                return False

        except Exception as e:
            logger.error(f'SAM3D 模型初始化失败: {e}')
            return False

    def _random_sample_next_click(self, prev_mask: torch.Tensor, gt_mask: torch.Tensor, method: str = 'random'):
        """
        从 ground-truth mask 随机采样一个点击点作为提示

        Args:
            prev_mask: 之前的预测 mask
            gt_mask: ground-truth mask
            method: 采样方法 ('random' 或 'ritm')

        Returns:
            采样点和标签
        """
        def ensure_3D_data(roi_tensor):
            if roi_tensor.ndim != 3:
                roi_tensor = roi_tensor.squeeze()
            assert roi_tensor.ndim == 3, "Input tensor must be 3D"
            return roi_tensor

        prev_mask = ensure_3D_data(prev_mask)
        gt_mask = ensure_3D_data(gt_mask)

        prev_mask = prev_mask > 0
        true_masks = gt_mask > 0

        if not true_masks.any():
            raise ValueError("Cannot find true value in the ground-truth!")

        fn_masks = torch.logical_and(true_masks, torch.logical_not(prev_mask))
        fp_masks = torch.logical_and(torch.logical_not(true_masks), prev_mask)

        if method.lower() == 'random':
            to_point_mask = torch.logical_or(fn_masks, fp_masks)

            if not to_point_mask.any():
                all_points = torch.argwhere(true_masks)
                point = all_points[np.random.randint(len(all_points))]
                is_positive = True
            else:
                all_points = torch.argwhere(to_point_mask)
                point = all_points[np.random.randint(len(all_points))]
                is_positive = bool(fn_masks[point[0], point[1], point[2]])

            sampled_point = point.clone().detach().reshape(1, 1, 3)
            sampled_label = torch.tensor([[int(is_positive)]], dtype=torch.long)

            return sampled_point, sampled_label

        elif method.lower() == 'ritm':
            import edt
            fn_mask_single = torch.nn.functional.pad(fn_masks[None, None], (1, 1, 1, 1, 1, 1), "constant", value=0)[0, 0]
            fp_mask_single = torch.nn.functional.pad(fp_masks[None, None], (1, 1, 1, 1, 1, 1), "constant", value=0)[0, 0]

            fn_mask_dt = torch.tensor(edt.edt(fn_mask_single.cpu().numpy(), black_border=True, parallel=4))[1:-1, 1:-1, 1:-1]
            fp_mask_dt = torch.tensor(edt.edt(fp_mask_single.cpu().numpy(), black_border=True, parallel=4))[1:-1, 1:-1, 1:-1]

            fn_max_dist = torch.max(fn_mask_dt)
            fp_max_dist = torch.max(fp_mask_dt)

            is_positive = fn_max_dist > fp_max_dist
            dt = fn_mask_dt if is_positive else fp_mask_dt
            max_dist = max(fn_max_dist, fp_max_dist)

            to_point_mask = (dt > (max_dist / 2.0))
            all_points = torch.argwhere(to_point_mask)

            if len(all_points) == 0:
                point = torch.tensor([gt_mask.shape[0] // 2, gt_mask.shape[1] // 2, gt_mask.shape[2] // 2])
                is_positive = False
            else:
                point = all_points[np.random.randint(len(all_points))]
                is_positive = bool(fn_masks[point[0], point[1], point[2]])

            sampled_point = point.clone().detach().reshape(1, 1, 3)
            sampled_label = torch.tensor([[int(is_positive)]], dtype=torch.long)

            return sampled_point, sampled_label

        else:
            raise ValueError(f"Unsupported method: {method}. Choose 'ritm' or 'random'.")

    def _sam_model_infer(
        self,
        roi_image: torch.Tensor,
        roi_gt: Optional[torch.Tensor] = None,
        num_clicks: int = 1,
        prev_low_res_mask: Optional[torch.Tensor] = None
    ) -> Tuple[np.ndarray, Optional[torch.Tensor]]:
        """
        SAM-Med3D 推理

        Args:
            roi_image: ROI 图像 (1, 1, D, H, W)
            roi_gt: ROI 标注 (可选)
            num_clicks: 点击次数
            prev_low_res_mask: 上一次的低分辨率 mask

        Returns:
            预测 mask 和最后的低分辨率 mask
        """
        if self.model is None:
            raise RuntimeError("模型未初始化，请先调用 setup()")

        self.model.eval()
        device = self.device
        logger.info(f"_sam_model_infer: roi_image shape={roi_image.shape}, roi_gt shape={roi_gt.shape if roi_gt is not None else None}, num_clicks={num_clicks}")

        if roi_gt is not None and (roi_gt == 0).all() and num_clicks > 0:
            print("_sam_model_infer: GT is all zeros, returning empty mask")
            return np.zeros_like(roi_image.cpu().numpy().squeeze()), None

        try:
            with torch.no_grad():
                input_tensor = roi_image.to(device)
                print("_sam_model_infer: Running image_encoder")
                try:
                    image_embeddings = self.model.image_encoder(input_tensor)
                except Exception as e:
                    print(f"_sam_model_infer: image_encoder failed: {e}")
                    raise
                print(f"_sam_model_infer: image_embeddings type: {type(image_embeddings)}")

                points_coords = torch.zeros(1, 0, 3).to(device)
                points_labels = torch.zeros(1, 0).to(device)
                new_points_co = torch.Tensor([[[64, 64, 64]]]).to(device)
                new_points_la = torch.Tensor([[1]]).to(torch.int64)

                current_prev_mask = torch.zeros_like(roi_image, device=device)[:, 0, ...]

                if prev_low_res_mask is None:
                    prev_low_res_mask = torch.zeros(
                        1, 1,
                        roi_image.shape[2] // 4,
                        roi_image.shape[3] // 4,
                        roi_image.shape[4] // 4,
                        device=device,
                        dtype=torch.float
                    )

                for click_idx in range(num_clicks):
                    print(f"_sam_model_infer: Processing click {click_idx+1}/{num_clicks}")
                    if roi_gt is not None:
                        print("_sam_model_infer: Sampling next click from GT")
                        try:
                            new_points_co, new_points_la = self._random_sample_next_click(
                                current_prev_mask.squeeze(0).cpu(),
                                roi_gt[0, 0].cpu()
                            )
                        except Exception as e:
                            print(f"_sam_model_infer: _random_sample_next_click failed: {e}")
                            raise
                        new_points_co = new_points_co.to(device)
                        new_points_la = new_points_la.to(device)
                    else:
                        if points_coords.shape[1] == 0:
                            center_z = roi_image.shape[2] // 2
                            center_y = roi_image.shape[3] // 2
                            center_x = roi_image.shape[4] // 2
                            new_points_co = torch.tensor([[[center_x, center_y, center_z]]], device=device, dtype=torch.float)
                            new_points_la = torch.tensor([[1]], device=device, dtype=torch.int64)
                        else:
                            break

                    points_coords = torch.cat([points_coords, new_points_co], dim=1)
                    points_labels = torch.cat([points_labels, new_points_la], dim=1)

                    print("_sam_model_infer: Running prompt_encoder")
                    try:
                        sparse_embeddings, dense_embeddings = self.model.prompt_encoder(
                            points=[points_coords, points_labels],
                            boxes=None,
                            masks=prev_low_res_mask,
                        )
                    except Exception as e:
                        print(f"_sam_model_infer: prompt_encoder failed: {e}")
                        raise
                    print("_sam_model_infer: Running mask_decoder")
                    try:
                        low_res_masks, _ = self.model.mask_decoder(
                            image_embeddings=image_embeddings,
                            image_pe=self.model.prompt_encoder.get_dense_pe(),
                            sparse_prompt_embeddings=sparse_embeddings,
                            dense_prompt_embeddings=dense_embeddings,
                            multimask_output=False,
                        )
                    except Exception as e:
                        print(f"_sam_model_infer: mask_decoder failed: {e}")
                        raise
                    print(f"_sam_model_infer: mask_decoder output shape: {low_res_masks.shape}")
                    prev_low_res_mask = low_res_masks.detach()

                    print("_sam_model_infer: Interpolating mask")
                    current_prev_mask = torch.nn.functional.interpolate(
                        low_res_masks,
                        size=roi_image.shape[-3:],
                        mode='trilinear',
                        align_corners=False
                    )
                    current_prev_mask = torch.sigmoid(current_prev_mask) > 0.5

                print("_sam_model_infer: Final interpolation")
                final_masks_hr = torch.nn.functional.interpolate(
                    low_res_masks,
                    size=roi_image.shape[-3:],
                    mode='trilinear',
                    align_corners=False
                )

            print("_sam_model_infer: Computing sigmoid and thresholding")
            medsam_seg_prob = torch.sigmoid(final_masks_hr)
            medsam_seg_prob = medsam_seg_prob.cpu().numpy().squeeze()
            medsam_seg_mask = (medsam_seg_prob > 0.5).astype(np.uint8)
            print(f"_sam_model_infer: Final mask shape: {medsam_seg_mask.shape}")

            return medsam_seg_mask, low_res_masks.detach()
        except Exception as e:
            import traceback
            print(f'_sam_model_infer exception: {e}')
            print(traceback.format_exc())
            raise

    def _read_nifti(self, nii_path: str, get_meta_info: bool = False):
        """读取 NIfTI 文件"""
        sitk_image = sitk.ReadImage(nii_path)
        arr = sitk.GetArrayFromImage(sitk_image)

        if not get_meta_info:
            return arr

        meta_info = {
            "sitk_image_object": sitk_image,
            "sitk_origin": sitk_image.GetOrigin(),
            "sitk_direction": sitk_image.GetDirection(),
            "sitk_spacing": sitk_image.GetSpacing(),
            "original_numpy_shape": arr.shape,
        }
        return arr, meta_info

    def _get_roi(
        self,
        subject_canonical,
        meta_info,
        crop_transform,
        norm_transform
    ):
        """从 canonical subject 获取 ROI"""
        meta_info["canonical_subject_shape"] = subject_canonical.spatial_shape
        meta_info["canonical_subject_affine"] = subject_canonical.image.affine.copy()

        padding_params, cropping_params = crop_transform._compute_center_crop_or_pad(subject_canonical)
        subject_cropped = crop_transform(subject_canonical)

        meta_info["padding_params_functional"] = padding_params
        meta_info["cropping_params_functional"] = cropping_params
        meta_info["roi_subject_affine"] = subject_cropped.image.affine.copy()

        img3D_roi = subject_cropped.image.data.clone().detach()
        img3D_roi = norm_transform(img3D_roi.squeeze(dim=1))
        img3D_roi = img3D_roi.unsqueeze(dim=1)

        gt3D_roi = subject_cropped.label.data.clone().detach()

        def correct_roi_dim(roi_tensor):
            if roi_tensor.ndim == 3:
                roi_tensor = roi_tensor.unsqueeze(0).unsqueeze(0)
            if roi_tensor.ndim == 4:
                roi_tensor = roi_tensor.unsqueeze(0)
            if img3D_roi.shape[0] != 1:
                roi_tensor = roi_tensor[:, 0:1, ...]
            return roi_tensor

        img3D_roi = correct_roi_dim(img3D_roi)
        gt3D_roi = correct_roi_dim(gt3D_roi)

        return img3D_roi, gt3D_roi, meta_info

    def _data_preprocess(self, subject, meta_info, category_index, target_spacing=(1.5, 1.5, 1.5), crop_size=128):
        """数据预处理"""
        logger.info(f"_data_preprocess: category_index={category_index}, target_spacing={target_spacing}, crop_size={crop_size}")
        label_data_for_cat = subject.label.data.clone()
        new_label_data = torch.zeros_like(label_data_for_cat)
        new_label_data[label_data_for_cat == category_index] = 1
        subject.label.set_data(new_label_data)
        logger.info(f"_data_preprocess: label shape: {subject.label.data.shape}")

        meta_info["original_subject_affine"] = subject.image.affine.copy()
        meta_info["original_subject_spatial_shape"] = subject.image.spatial_shape

        logger.info("_data_preprocess: Resampling...")
        resampler = tio.Resample(target=target_spacing)
        subject_resampled = resampler(subject)

        logger.info("_data_preprocess: Converting to canonical...")
        transform_canonical = tio.ToCanonical()
        subject_canonical = transform_canonical(subject_resampled)

        logger.info("_data_preprocess: Cropping/padding...")
        crop_transform = tio.CropOrPad(mask_name='label', target_shape=(crop_size, crop_size, crop_size))
        norm_transform = tio.ZNormalization(masking_method=lambda x: x > 0)

        roi_image, roi_label, meta_info = self._get_roi(
            subject_canonical, meta_info, crop_transform, norm_transform
        )
        logger.info(f"_data_preprocess: Complete - roi_image: {roi_image.shape}, roi_label: {roi_label.shape}")

        return roi_image, roi_label, meta_info

    def _data_postprocess(self, roi_pred_numpy: np.ndarray, meta_info: dict) -> np.ndarray:
        """后处理，将 ROI 预测映射回原始空间"""
        logger.info(f"_data_postprocess: input shape: {roi_pred_numpy.shape}")
        roi_pred_tensor = torch.from_numpy(roi_pred_numpy.astype(np.float32)).unsqueeze(0)

        pred_label_map_roi_space = tio.LabelMap(
            tensor=roi_pred_tensor,
            affine=meta_info["roi_subject_affine"]
        )

        reference_tensor_shape = (1, *meta_info["original_subject_spatial_shape"])
        logger.info(f"_data_postprocess: original spatial shape: {meta_info['original_subject_spatial_shape']}")

        reference_image_original_space = tio.ScalarImage(
            tensor=torch.zeros(reference_tensor_shape),
            affine=meta_info["original_subject_affine"]
        )

        logger.info("_data_postprocess: Resampling to original space...")
        resampler_to_original_grid = tio.Resample(
            target=reference_image_original_space,
            image_interpolation='nearest'
        )

        pred_resampled_to_original_space = resampler_to_original_grid(pred_label_map_roi_space)
        final_pred_numpy_dhw = pred_resampled_to_original_space.data.squeeze(0).cpu().numpy()
        final_pred_numpy = final_pred_numpy_dhw.astype(np.uint8)

        return final_pred_numpy.transpose(2, 1, 0)

    def _save_nifti(self, in_arr: np.ndarray, out_path: str, meta_info_for_saving: dict):
        """保存 NIfTI 文件"""
        out_img = sitk.GetImageFromArray(in_arr)

        original_sitk_image = meta_info_for_saving.get("sitk_image_object")
        if original_sitk_image:
            out_img.SetOrigin(original_sitk_image.GetOrigin())
            out_img.SetDirection(original_sitk_image.GetDirection())
            out_img.SetSpacing(original_sitk_image.GetSpacing())
        else:
            out_img.SetOrigin(meta_info_for_saving["sitk_origin"])
            out_img.SetDirection(meta_info_for_saving["sitk_direction"])
            out_img.SetSpacing(meta_info_for_saving["sitk_spacing"])

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        sitk.WriteImage(out_img, out_path)

    def _get_category_list_and_zero_mask(self, gt_path: str) -> Tuple[List[int], np.ndarray]:
        """获取标注中的类别列表"""
        arr, meta = self._read_nifti(gt_path, get_meta_info=True)
        unique_label = np.unique(arr)
        unique_fg_labels = [int(l) for l in unique_label if l != 0]
        return unique_fg_labels, np.zeros(meta["original_numpy_shape"], dtype=np.uint8)

    def infer(
        self,
        img_path: str,
        gt_path: str = None,
        output_path: str = None,
        num_clicks: int = 1,
        crop_size: int = 128,
        target_spacing: Tuple[float, float, float] = (1.5, 1.5, 1.5),
        seed: int = 233
    ) -> Dict[str, Any]:
        """
        执行推理

        Args:
            img_path: 输入 CT 图像路径 (.nii 或 .nii.gz)
            gt_path: 标注文件路径 (可选，用于生成提示点)
            output_path: 输出路径 (可选，默认自动生成)
            num_clicks: 点击次数
            crop_size: 裁剪大小
            target_spacing: 目标体素间距
            seed: 随机种子

        Returns:
            包含结果的字典
        """
        torch.manual_seed(seed)
        np.random.seed(seed)

        def log(msg):
            print(f"[SAM3D] {msg}")
            logger.info(msg)

        if output_path is None:
            output_dir = os.path.join(os.path.dirname(img_path), 'pred')
            os.makedirs(output_dir, exist_ok=True)
            basename = os.path.basename(img_path)
            output_path = os.path.join(output_dir, basename)

        try:
            log(f"Step 1: Checking model initialization")
            if self.model is None:
                log("Model is None, calling setup()")
                setup_result = self.setup()
                log(f"setup() returned: {setup_result}")
                if not setup_result:
                    return {
                        'success': False,
                        'error': '模型初始化失败',
                        'output_path': None
                    }
                log("Model setup complete")

            log(f"Step 2: Getting category list from {gt_path or img_path}")
            try:
                exist_categories, final_pred_numpy_original_grid = self._get_category_list_and_zero_mask(gt_path or img_path)
            except Exception as e:
                print(f'[SAM3D] Step 2 failed: {e}')
                raise
            log(f"Found categories: {exist_categories}")

            log(f"Step 3: Reading metadata from {gt_path or img_path}")
            try:
                _, gt_meta_for_saving = self._read_nifti(gt_path or img_path, get_meta_info=True)
            except Exception as e:
                print(f'[SAM3D] Step 3 failed: {e}')
                raise
            log(f"Metadata read successfully")

            log(f"Step 4: Creating TorchIO Subject")
            try:
                subject = tio.Subject(
                    image=tio.ScalarImage(img_path),
                    label=tio.LabelMap(gt_path) if gt_path else tio.ScalarImage(img_path)
                )
            except Exception as e:
                print(f'[SAM3D] Step 4 failed creating TorchIO Subject: {e}')
                raise
            log("TorchIO Subject created successfully")

            log(f"Step 5: Reading sitk image (this reads the file 4 times - inefficient!)")
            try:
                sitk_image = sitk.ReadImage(img_path)
            except Exception as e:
                print(f'[SAM3D] Step 5 failed reading sitk image: {e}')
                raise
            meta_info = {
                "sitk_image_object": sitk_image,
                "sitk_origin": sitk_image.GetOrigin(),
                "sitk_direction": sitk_image.GetDirection(),
                "sitk_spacing": sitk_image.GetSpacing(),
                "original_numpy_shape": sitk.GetArrayFromImage(sitk_image).shape,
            }
            log(f"sitk spacing: {sitk_image.GetSpacing()}, shape: {sitk.GetArrayFromImage(sitk_image).shape}")

            if gt_path:
                log(f"Step 6: Reading gt_path: {gt_path}")
                try:
                    subject.label = tio.LabelMap(gt_path)
                    gt_sitk_image = sitk.ReadImage(gt_path)
                    _, meta_for_gt = self._read_nifti(gt_path, get_meta_info=True)
                    meta_info.update({
                        "original_subject_affine": gt_sitk_image.GetOrigin(),
                        "original_subject_spatial_shape": sitk.GetArrayFromImage(gt_sitk_image).shape,
                    })
                except Exception as e:
                    print(f'[SAM3D] Step 6 failed: {e}')
                    raise
                log(f"GT spatial shape: {sitk.GetArrayFromImage(gt_sitk_image).shape}")
            else:
                meta_info.update({
                    "original_subject_affine": meta_info["sitk_image_object"].GetOrigin(),
                    "original_subject_spatial_shape": meta_info["original_numpy_shape"],
                })

            log(f"Step 7: Processing {len(exist_categories) if exist_categories else 1} categories")
            for idx, category_index in enumerate(exist_categories if exist_categories else [1]):
                log(f"  Processing category {idx+1}/{len(exist_categories) if exist_categories else 1}: index={category_index}")
                category_specific_subject = subject
                category_specific_meta_info = meta_info.copy()

                log(f"  Step 7.{idx+1}.1: _data_preprocess")
                try:
                    roi_image, roi_label, meta_info = self._data_preprocess(
                        category_specific_subject,
                        category_specific_meta_info,
                        category_index=category_index,
                        target_spacing=target_spacing,
                        crop_size=crop_size
                    )
                except Exception as e:
                    print(f'[SAM3D] Step 7.{idx+1}.1 _data_preprocess failed: {e}')
                    raise
                log(f"  ROI image shape: {roi_image.shape}, ROI label shape: {roi_label.shape}")

                log(f"  Step 7.{idx+1}.2: _sam_model_infer")
                try:
                    roi_pred_numpy, _ = self._sam_model_infer(
                        roi_image,
                        roi_gt=roi_label,
                        num_clicks=num_clicks,
                        prev_low_res_mask=None
                    )
                except Exception as e:
                    print(f'[SAM3D] Step 7.{idx+1}.2 _sam_model_infer failed: {e}')
                    raise
                log(f"  Prediction shape: {roi_pred_numpy.shape}")

                log(f"  Step 7.{idx+1}.3: _data_postprocess")
                try:
                    cls_pred_original_grid = self._data_postprocess(roi_pred_numpy, meta_info)
                except Exception as e:
                    print(f'[SAM3D] Step 7.{idx+1}.3 _data_postprocess failed: {e}')
                    raise
                log(f"  Postprocessed shape: {cls_pred_original_grid.shape}")
                final_pred_numpy_original_grid[cls_pred_original_grid == 1] = category_index

            log(f"Step 8: Saving to {output_path}")
            try:
                self._save_nifti(final_pred_numpy_original_grid, output_path, gt_meta_for_saving)
            except Exception as e:
                print(f'[SAM3D] Step 8 _save_nifti failed: {e}')
                raise

            return {
                'success': True,
                'output_path': output_path,
                'num_categories': len(exist_categories) if exist_categories else 1,
                'processing_time': 0,
                'model_version': 'SAM-Med3D'
            }

        except Exception as e:
            import traceback
            print(f'[SAM3D] Exception: {e}')
            print(traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'output_path': None
            }

    def infer_simple(
        self,
        img_path: str,
        output_path: str = None,
        center_point: Tuple[int, int, int] = None
    ) -> Dict[str, Any]:
        """
        简化推理（无需标注文件，使用中心点作为提示）

        Args:
            img_path: 输入 CT 图像路径
            output_path: 输出路径
            center_point: 中心点坐标 (z, y, x)，默认使用图像中心

        Returns:
            结果字典
        """
        try:
            if self.model is None:
                if not self.setup():
                    return {
                        'success': False,
                        'error': '模型初始化失败',
                        'output_path': None
                    }

            if output_path is None:
                output_dir = os.path.join(os.path.dirname(img_path), 'pred')
                os.makedirs(output_dir, exist_ok=True)
                basename = os.path.basename(img_path)
                output_path = os.path.join(output_dir, basename)

            sitk_image = sitk.ReadImage(img_path)
            arr = sitk.GetArrayFromImage(sitk_image)
            spacing = sitk_image.GetSpacing()
            origin = sitk_image.GetOrigin()
            direction = sitk_image.GetDirection()

            crop_size = 128
            target_spacing = (1.5, 1.5, 1.5)

            print(f"infer_simple: arr shape before processing: {arr.shape}")
            subject = tio.Subject(
                image=tio.ScalarImage(tensor=torch.from_numpy(arr).unsqueeze(0).float(), affine=np.eye(4))
            )
            print(f"infer_simple: subject created, image shape: {subject.image.data.shape}")

            resampler = tio.Resample(target=target_spacing)
            subject_resampled = resampler(subject)

            transform_canonical = tio.ToCanonical()
            subject_canonical = transform_canonical(subject_resampled)

            crop_transform = tio.CropOrPad(target_shape=(crop_size, crop_size, crop_size))

            print(f"infer_simple: before crop, image data shape: {subject_canonical.image.data.shape}")
            subject_cropped = crop_transform(subject_canonical)
            print(f"infer_simple: after crop, image data shape: {subject_cropped.image.data.shape}")

            img_data = subject_cropped.image.data.squeeze(0)
            print(f"infer_simple: img_data shape after squeeze: {img_data.shape}")

            mask = img_data > 0
            mean_val = img_data[mask].mean() if mask.any() else 0
            std_val = img_data[mask].std() if mask.any() else 1
            normalized = (img_data - mean_val) / (std_val + 1e-8)
            normalized = normalized.clamp(-5, 5)

            print(f"infer_simple: normalized shape: {normalized.shape}")

            roi_image = normalized.unsqueeze(0).unsqueeze(0).float()
            print(f"infer_simple: roi_image shape: {roi_image.shape}")

            if center_point is None:
                center_point = (
                    roi_image.shape[2] // 2,
                    roi_image.shape[3] // 2,
                    roi_image.shape[4] // 2
                )

            with torch.no_grad():
                input_tensor = roi_image.to(self.device)
                image_embeddings = self.model.image_encoder(input_tensor)

                points_coords = torch.zeros(1, 0, 3).to(self.device)
                points_labels = torch.zeros(1, 0).to(self.device)

                new_points_co = torch.tensor([[[center_point[2], center_point[1], center_point[0]]]], device=self.device, dtype=torch.float)
                new_points_la = torch.tensor([[1]], device=self.device, dtype=torch.int64)

                points_coords = torch.cat([points_coords, new_points_co], dim=1)
                points_labels = torch.cat([points_labels, new_points_la], dim=1)

                prev_low_res_mask = torch.zeros(
                    1, 1,
                    roi_image.shape[2] // 4,
                    roi_image.shape[3] // 4,
                    roi_image.shape[4] // 4,
                    device=self.device,
                    dtype=torch.float
                )

                sparse_embeddings, dense_embeddings = self.model.prompt_encoder(
                    points=[points_coords, points_labels],
                    boxes=None,
                    masks=prev_low_res_mask,
                )

                low_res_masks, _ = self.model.mask_decoder(
                    image_embeddings=image_embeddings,
                    image_pe=self.model.prompt_encoder.get_dense_pe(),
                    sparse_prompt_embeddings=sparse_embeddings,
                    dense_prompt_embeddings=dense_embeddings,
                    multimask_output=False,
                )

                final_masks_hr = torch.nn.functional.interpolate(
                    low_res_masks,
                    size=roi_image.shape[-3:],
                    mode='trilinear',
                    align_corners=False
                )

            medsam_seg_prob = torch.sigmoid(final_masks_hr)
            medsam_seg_prob = medsam_seg_prob.cpu().numpy().squeeze()
            medsam_seg_mask = (medsam_seg_prob > 0.5).astype(np.uint8)

            out_img = sitk.GetImageFromArray(medsam_seg_mask)
            out_img.SetOrigin(origin)
            out_img.SetDirection(direction)
            out_img.SetSpacing(spacing)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            sitk.WriteImage(out_img, output_path)

            return {
                'success': True,
                'output_path': output_path,
                'center_point': center_point,
                'model_version': 'SAM-Med3D'
            }

        except Exception as e:
            logger.exception(f'SAM3D 简化推理失败: {e}')
            return {
                'success': False,
                'error': str(e),
                'output_path': None
            }


_sam3d_service: Optional[SAM3DInferenceService] = None


def get_sam3d_service() -> SAM3DInferenceService:
    """获取 SAM3D 服务单例"""
    global _sam3d_service
    if _sam3d_service is None:
        _sam3d_service = SAM3DInferenceService()
    return _sam3d_service


def run_inference(
    img_path: str,
    gt_path: str = None,
    output_path: str = None,
    num_clicks: int = 1
) -> Dict[str, Any]:
    """运行 SAM3D 推理的便捷函数"""
    service = get_sam3d_service()
    return service.infer(img_path, gt_path, output_path, num_clicks)
