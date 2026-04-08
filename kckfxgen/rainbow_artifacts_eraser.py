# SPDX-License-Identifier: GPL-3.0-or-later
"""削弱固定版式漫画在 Kindle Colorsoft 等设备上可能出现的彩虹摩尔纹（频域定向衰减）。

算法与实现改编自 **Kindle Comic Converter (KCC)** 的 ``rainbow_artifacts_eraser.py``（同 GPL-3.0）：
https://github.com/ciromattia/kcc/blob/master/kindlecomicconverter/rainbow_artifacts_eraser.py

在 kckfxgen 中仅做必要整理：修正 ``is_color is None`` 分支、类型注解与模块说明。
"""

from __future__ import annotations

import gc
import logging
from functools import lru_cache

import numpy as np
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True
logger = logging.getLogger(__name__)
_GPU_STATUS: str = "未探测"


def fourier_transform_image(img: Image.Image | np.ndarray) -> np.ndarray:
    """对实值图像（PIL 或 ``float32``/``uint8`` 数组）做 ``rfft2``。"""
    img_array = np.asarray(img, dtype=np.float32)
    return np.fft.rfft2(img_array)


def attenuate_diagonal_frequencies(
    fft_spectrum: np.ndarray,
    *,
    xp: object = np,
    freq_threshold: float = 0.30,
    target_angle: float = 135,
    angle_tolerance: float = 10,
    attenuation_factor: float = 0.10,
) -> np.ndarray:
    """在频域削弱沿特定角度的高频能量（彩虹纹常见走向）。"""
    if fft_spectrum.ndim == 2:
        height, width_rfft = fft_spectrum.shape
    else:
        height, width_rfft = fft_spectrum.shape[:2]

    width_original = (width_rfft - 1) * 2

    fft_mod = xp.fft  # type: ignore[attr-defined]
    freq_y = fft_mod.fftfreq(height, d=1.0)
    freq_x = fft_mod.rfftfreq(width_original, d=1.0)

    freq_y_grid = freq_y.reshape(-1, 1)
    freq_x_grid = freq_x.reshape(1, -1)

    freq_radial_sq = freq_x_grid**2 + freq_y_grid**2
    freq_threshold_sq = freq_threshold**2

    freq_condition = freq_radial_sq >= freq_threshold_sq

    if not xp.any(freq_condition):  # type: ignore[attr-defined]
        return fft_spectrum

    angles_rad = xp.arctan2(freq_y_grid, freq_x_grid)  # type: ignore[attr-defined]
    angles_deg = xp.rad2deg(angles_rad) % 360  # type: ignore[attr-defined]

    target_angle_2 = (target_angle + 180) % 360
    target_angle_3 = (target_angle + 90) % 360
    target_angle_4 = (target_angle_3 + 180) % 360

    angle_condition = xp.zeros_like(angles_deg, dtype=bool)  # type: ignore[attr-defined]

    for angle in (target_angle, target_angle_2, target_angle_3, target_angle_4):
        min_angle = (angle - angle_tolerance) % 360
        max_angle = (angle + angle_tolerance) % 360

        if min_angle > max_angle:
            angle_condition |= (angles_deg >= min_angle) | (angles_deg <= max_angle)
        else:
            angle_condition |= (angles_deg >= min_angle) & (angles_deg <= max_angle)

    combined_condition = freq_condition & angle_condition

    if attenuation_factor == 0:
        if fft_spectrum.ndim == 2:
            fft_spectrum[combined_condition] = 0
        else:
            fft_spectrum[combined_condition, :] = 0
        return fft_spectrum
    if attenuation_factor == 1:
        return fft_spectrum

    if fft_spectrum.ndim == 2:
        fft_spectrum[combined_condition] *= attenuation_factor
    else:
        fft_spectrum[combined_condition, :] *= attenuation_factor
    return fft_spectrum


def inverse_fourier_transform_image(
    fft_spectrum: np.ndarray,
    is_color: bool,
    original_shape: tuple[int, int] | None = None,
) -> Image.Image:
    if original_shape is not None:
        img_reconstructed = np.fft.irfft2(fft_spectrum, s=original_shape)
    else:
        img_reconstructed = np.fft.irfft2(fft_spectrum)

    img_reconstructed = np.clip(img_reconstructed, 0, 255)
    img_reconstructed = img_reconstructed.astype(np.uint8)

    if is_color and img_reconstructed.ndim == 3:
        return Image.fromarray(img_reconstructed, mode="RGB")
    return Image.fromarray(img_reconstructed, mode="L")


def _cleanup_cupy_memory(cp: object) -> None:
    """及时回收 CuPy 内存池，避免长任务中显存阶梯式升高。"""
    try:
        cp.get_default_memory_pool().free_all_blocks()  # type: ignore[attr-defined]
        cp.get_default_pinned_memory_pool().free_all_blocks()  # type: ignore[attr-defined]
    except Exception:
        pass


def _apply_luminance_cleanup_cpu(img: Image.Image) -> Image.Image:
    """CPU 路径：仅调整亮度，减少中间数组数量与峰值内存。"""
    rgb_u8 = np.asarray(img, dtype=np.uint8)
    rgb_f = rgb_u8.astype(np.float32, copy=True)

    y = (
        0.299 * rgb_f[:, :, 0]
        + 0.587 * rgb_f[:, :, 1]
        + 0.114 * rgb_f[:, :, 2]
    )
    fft_spectrum = np.fft.rfft2(y)
    clean_spectrum = attenuate_diagonal_frequencies(fft_spectrum, xp=np)
    clean_y = np.fft.irfft2(clean_spectrum, s=y.shape).astype(np.float32, copy=False)

    delta = (clean_y - y).astype(np.float32, copy=False)
    rgb_f += delta[:, :, None]
    rgb_out = np.clip(rgb_f, 0, 255).astype(np.uint8, copy=False)

    return Image.fromarray(rgb_out, mode="RGB")


def _apply_luminance_cleanup_gpu(img_array: np.ndarray, cp: object) -> Image.Image:
    """GPU 路径：仅亮度差分，降低显存峰值并减少临时矩阵。"""
    rgb_gpu = cp.asarray(img_array, dtype=cp.float32)  # type: ignore[attr-defined]
    y = (
        0.299 * rgb_gpu[:, :, 0]
        + 0.587 * rgb_gpu[:, :, 1]
        + 0.114 * rgb_gpu[:, :, 2]
    )
    fft_spectrum = cp.fft.rfft2(y)  # type: ignore[attr-defined]
    clean_spectrum = attenuate_diagonal_frequencies(fft_spectrum, xp=cp)
    clean_y = cp.fft.irfft2(clean_spectrum, s=y.shape)  # type: ignore[attr-defined]
    delta = clean_y - y
    rgb_gpu += delta[:, :, None]
    rgb_array = cp.clip(rgb_gpu, 0, 255).astype(cp.uint8).get()  # type: ignore[attr-defined]
    return Image.fromarray(rgb_array, mode="RGB")


@lru_cache(maxsize=1)
def _resolve_cupy():
    global _GPU_STATUS
    try:
        import cupy as cp

        if int(cp.cuda.runtime.getDeviceCount()) <= 0:
            _GPU_STATUS = "GPU设备数为0"
            return None
        # 仅 getDeviceCount 不能覆盖 cublas/cufft 动态库是否可用；做一次轻量探针。
        a = cp.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=cp.float32)
        _ = a @ a.T
        _ = cp.fft.rfft2(cp.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=cp.float32))
        _GPU_STATUS = "CuPy GPU 可用"
        return cp
    except Exception as e:
        _GPU_STATUS = f"CuPy GPU 不可用: {type(e).__name__}: {e}"
        logger.debug("CuPy GPU 探针失败，禁用 GPU 路径并回退 CPU：%s: %s", type(e).__name__, e)
        return None


def gpu_runtime_status() -> str:
    """返回最近一次 GPU 可用性探测结果（供上层日志展示）。"""
    return _GPU_STATUS


def erase_rainbow_artifacts(
    img: Image.Image,
    is_color: bool | None,
    *,
    use_gpu: bool = False,
) -> Image.Image:
    """去除或削弱彩虹摩尔纹；彩色图只处理亮度 (Y) 通道，色度保留。"""
    if is_color is None:
        is_color = img.mode in ("RGB", "RGBA")

    cp = _resolve_cupy() if use_gpu else None
    if use_gpu and cp is None:
        logger.debug("彩虹纹削弱：GPU 不可用，回退 CPU 路径")

    if is_color and img.mode in ("RGB", "RGBA"):
        if img.mode == "RGBA":
            img = img.convert("RGB")
        img_array = np.asarray(img, dtype=np.uint8)

        if cp is not None:
            try:
                out = _apply_luminance_cleanup_gpu(img_array, cp)
                _cleanup_cupy_memory(cp)
                return out
            except Exception as e:
                logger.debug("彩虹纹削弱：GPU 路径失败，回退 CPU（%s: %s）", type(e).__name__, e)
                _cleanup_cupy_memory(cp)

        return _apply_luminance_cleanup_cpu(img)

    if img.mode != "L":
        img = img.convert("L")

    original_shape = (img.height, img.width)

    if cp is not None:
        try:
            gray_gpu = cp.asarray(np.asarray(img, dtype=np.float32))
            fft_spectrum = cp.fft.rfft2(gray_gpu)
            clean_spectrum = attenuate_diagonal_frequencies(fft_spectrum, xp=cp)
            rec = cp.fft.irfft2(clean_spectrum, s=original_shape)
            rec = cp.clip(rec, 0, 255).astype(cp.uint8).get()
            _cleanup_cupy_memory(cp)
            return Image.fromarray(rec, mode="L")
        except Exception as e:
            logger.debug("彩虹纹削弱：GPU 灰度路径失败，回退 CPU（%s: %s）", type(e).__name__, e)
            _cleanup_cupy_memory(cp)

    fft_spectrum = fourier_transform_image(img)
    clean_spectrum = attenuate_diagonal_frequencies(fft_spectrum, xp=np)
    out = inverse_fourier_transform_image(clean_spectrum, False, original_shape)
    # 大图连续处理时，及时释放 CPU 临时对象，降低 RSS 峰值滞后。
    gc.collect()
    return out
