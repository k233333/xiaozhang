# coding: utf-8
"""通用桌面 UI 元素解析（Phase 2）

截屏 → YOLOv8 ONNX 检测控件框 → EasyOCR 读文字 → 元素表 → find_element_by_text。
0 token，0.5-1s。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class UIElement:
    id: int
    type: str          # "icon" | "text"
    bbox: list[int]    # [x1, y1, x2, y2]
    center: list[int]  # [cx, cy]
    text: str = ""
    score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParseResult:
    elements: list[UIElement] = field(default_factory=list)
    yolo_ms: float = 0.0
    ocr_ms: float = 0.0
    total_ms: float = 0.0
    image_size: tuple[int, int] = (0, 0)


_yolo_session: Any = None
_yolo_input_name: str | None = None
_yolo_input_size: int = 1280


def _yolo_model_path() -> Path:
    return settings.resolve_path(settings.paths.models_dir) / "omniparser_v2" / "icon_detect" / "model.onnx"


def _ensure_yolo_loaded() -> bool:
    """优先从 resource_manager 拿已加载的 omniparser session，否则自行加载。"""
    global _yolo_session, _yolo_input_name
    if _yolo_session is not None:
        return True

    # 尝试从 resource_manager 拿（开机后已预加载到显存）
    try:
        from src.core.resource_manager import resource_manager  # noqa: PLC0415

        op = resource_manager.get_model("omniparser")
        if op is not None and hasattr(op, "_yolo") and op._yolo is not None:
            _yolo_session = op._yolo
            _yolo_input_name = _yolo_session.get_inputs()[0].name
            log.info("YOLO 从 resource_manager 获取（已预加载）")
            return True
    except Exception:
        pass

    # 兜底：自行加载
    p = _yolo_model_path()
    if not p.exists():
        log.warning("YOLOv8 ONNX 不存在", path=str(p))
        return False
    try:
        import onnxruntime as ort  # noqa: PLC0415
    except ImportError:
        log.warning("onnxruntime 未装")
        return False
    providers: list[str] = []
    avail = ort.get_available_providers()
    if "DmlExecutionProvider" in avail:
        providers.append("DmlExecutionProvider")
    providers.append("CPUExecutionProvider")
    try:
        _yolo_session = ort.InferenceSession(str(p), providers=providers)
        _yolo_input_name = _yolo_session.get_inputs()[0].name
        log.info("YOLOv8 ONNX 自行加载成功", providers=providers)
        return True
    except Exception as e:
        log.warning("YOLOv8 加载失败", err=str(e))
        return False


def _letterbox(img: np.ndarray, size: int = 1280) -> tuple[np.ndarray, float, tuple[int, int]]:
    h, w = img.shape[:2]
    scale = size / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    import cv2  # noqa: PLC0415
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_x = (size - nw) // 2
    pad_y = (size - nh) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = resized
    return canvas, scale, (pad_x, pad_y)


def _yolo_infer(img: np.ndarray, conf: float = 0.25) -> list[tuple[list[int], float]]:
    if not _ensure_yolo_loaded():
        return []
    h0, w0 = img.shape[:2]
    canvas, scale, (pad_x, pad_y) = _letterbox(img, _yolo_input_size)
    inp = canvas[..., ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    inp = inp[None, ...]
    out = _yolo_session.run(None, {_yolo_input_name: inp})[0]
    if out.ndim == 3:
        out = out[0]
        if out.shape[0] < out.shape[1]:
            out = out.T
    boxes_xywh = out[:, :4]
    scores = out[:, 4:].max(axis=1) if out.shape[1] > 4 else out[:, 4]
    keep = scores > conf
    boxes_xywh = boxes_xywh[keep]
    scores = scores[keep]
    if len(boxes_xywh) == 0:
        return []
    boxes = np.zeros_like(boxes_xywh)
    boxes[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
    boxes[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
    boxes[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2
    boxes[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2
    boxes[:, [0, 2]] -= pad_x
    boxes[:, [1, 3]] -= pad_y
    boxes /= scale
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, w0)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, h0)
    keep_idx = _nms(boxes, scores, iou_threshold=0.45)
    out_list: list[tuple[list[int], float]] = []
    for i in keep_idx:
        x1, y1, x2, y2 = boxes[i].astype(int).tolist()
        out_list.append(([x1, y1, x2, y2], float(scores[i])))
    return out_list


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.45) -> list[int]:
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou < iou_threshold]
    return keep


_ocr_reader: Any = None


def _ensure_ocr_loaded() -> bool:
    """优先从 resource_manager 拿已加载的 RapidOCR，否则自行加载。

    优先级：resource_manager 预加载 > 自行 RapidOCR(DML) > easyocr(CPU 兜底)
    """
    global _ocr_reader
    if _ocr_reader is not None:
        return True

    # 尝试从 resource_manager 拿（开机后已预加载到显存）
    try:
        from src.core.resource_manager import resource_manager  # noqa: PLC0415

        rm = resource_manager.get_model("rapidocr")
        if rm is not None and hasattr(rm, "_ocr") and rm._ocr is not None:
            _ocr_reader = rm  # 直接用 RapidOCRModel 实例
            log.info("RapidOCR 从 resource_manager 获取（已预加载）")
            return True
    except Exception:
        pass

    # 兜底：自行加载
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415

        _ocr_reader = RapidOCR(det_use_dml=True, rec_use_dml=True, cls_use_dml=True)
        log.info("RapidOCR 自行加载成功（DirectML）")
        return True
    except ImportError:
        log.debug("rapidocr_onnxruntime 未装")
    except Exception as e:
        log.warning("RapidOCR 自行加载失败", err=str(e))
        _ocr_reader = None

    # 最后兜底：EasyOCR CPU
    try:
        import easyocr  # noqa: PLC0415

        _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
        log.warning("EasyOCR 加载成功（CPU 兜底，建议装 rapidocr 走 GPU）")
        return True
    except Exception:
        log.warning("OCR 引擎都没装。装：uv pip install rapidocr-onnxruntime")
        return False


def _ocr_run(img: np.ndarray, *, max_side: int = 1920) -> list[tuple[list[int], str, float]]:
    """OCR 推理。img 太大时（>max_side）先缩放再 OCR，bbox 自动还原回原尺寸。

    返回：[([x1,y1,x2,y2], text, conf), ...]
    自动适配 RapidOCR 和 EasyOCR 两种输出格式。
    """
    if not _ensure_ocr_loaded():
        return []

    h0, w0 = img.shape[:2]
    scale = 1.0
    if max(h0, w0) > max_side:
        scale = max_side / max(h0, w0)
        import cv2  # noqa: PLC0415
        nh, nw = int(h0 * scale), int(w0 * scale)
        img_proc = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        img_proc = img

    inv_scale = 1.0 / scale if scale != 0 else 1.0
    out: list[tuple[list[int], str, float]] = []

    # 判断引擎类型
    is_rapidocr_model = hasattr(_ocr_reader, "ocr") and callable(getattr(_ocr_reader, "ocr"))
    is_rapidocr_raw = type(_ocr_reader).__name__ == "RapidOCR"

    try:
        if is_rapidocr_model:
            # 从 resource_manager 拿的 RapidOCRModel 实例，.ocr() 返回 [([x1,y1,x2,y2], text, conf)]
            raw = _ocr_reader.ocr(img_proc)
            for bbox, text, conf in raw:
                x1 = int(bbox[0] * inv_scale)
                y1 = int(bbox[1] * inv_scale)
                x2 = int(bbox[2] * inv_scale)
                y2 = int(bbox[3] * inv_scale)
                out.append(([x1, y1, x2, y2], text, conf))
        elif is_rapidocr_raw:
            results, _elapsed = _ocr_reader(img_proc)
            if not results:
                return []
            for item in results:
                box, text, conf = item[0], item[1], item[2]
                xs = [int(p[0] * inv_scale) for p in box]
                ys = [int(p[1] * inv_scale) for p in box]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                text = (text or "").strip()
                if not text:
                    continue
                out.append(([x1, y1, x2, y2], text, float(conf)))
        else:
            # EasyOCR
            results = _ocr_reader.readtext(img_proc, detail=1, paragraph=False)
            for box, text, conf in results:
                xs = [int(p[0] * inv_scale) for p in box]
                ys = [int(p[1] * inv_scale) for p in box]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                text = (text or "").strip()
                if not text:
                    continue
                out.append(([x1, y1, x2, y2], text, float(conf)))
    except Exception as e:
        log.warning("OCR 推理异常", err=str(e))
        return []

    return out


def parse_screen(image: Image.Image | None = None) -> ParseResult:
    t0 = time.monotonic()
    if image is None:
        from src.vision.screenshot import grab_full  # noqa: PLC0415
        image, _ = grab_full(save=False)

    img_np = np.array(image)
    img_bgr = img_np[..., ::-1].copy()

    t_yolo = time.monotonic()
    icons = _yolo_infer(img_bgr)
    yolo_ms = (time.monotonic() - t_yolo) * 1000

    t_ocr = time.monotonic()
    texts = _ocr_run(img_bgr)
    ocr_ms = (time.monotonic() - t_ocr) * 1000

    elements: list[UIElement] = []
    eid = 0
    for bbox, score in icons:
        x1, y1, x2, y2 = bbox
        elements.append(UIElement(id=eid, type="icon", bbox=bbox,
                                  center=[(x1 + x2) // 2, (y1 + y2) // 2], score=score))
        eid += 1
    for bbox, text, score in texts:
        x1, y1, x2, y2 = bbox
        elements.append(UIElement(id=eid, type="text", bbox=bbox,
                                  center=[(x1 + x2) // 2, (y1 + y2) // 2],
                                  text=text, score=score))
        eid += 1

    total_ms = (time.monotonic() - t0) * 1000
    h, w = img_np.shape[:2]
    log.info("屏幕解析完成", n_icons=len(icons), n_texts=len(texts),
             yolo_ms=round(yolo_ms, 1), ocr_ms=round(ocr_ms, 1),
             total_ms=round(total_ms, 1))
    return ParseResult(elements=elements, yolo_ms=yolo_ms, ocr_ms=ocr_ms,
                       total_ms=total_ms, image_size=(w, h))


def find_element_by_text(description: str, *, parse_result: ParseResult | None = None,
                         fuzzy_threshold: float = 0.7) -> UIElement | None:
    if parse_result is None:
        parse_result = parse_screen()
    if not parse_result.elements:
        return None
    desc = description.strip().lower()
    if not desc:
        return None

    text_elements = [e for e in parse_result.elements if e.type == "text" and e.text]

    for e in text_elements:
        if e.text.strip().lower() == desc:
            return e

    for e in text_elements:
        et = e.text.strip().lower()
        if desc in et or et in desc:
            return e

    from difflib import SequenceMatcher  # noqa: PLC0415
    best: tuple[UIElement, float] | None = None
    for e in text_elements:
        ratio = SequenceMatcher(None, desc, e.text.strip().lower()).ratio()
        if best is None or ratio > best[1]:
            best = (e, ratio)
    if best and best[1] >= fuzzy_threshold:
        return best[0]
    return None
