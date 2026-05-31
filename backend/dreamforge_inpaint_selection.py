"""Smart inpaint mask generation (Samsung Gallery / Photoshop-style selections)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from _paths import OUTPUTS_ROOT
from dreamforge_paths import resolve_image_path_or_raise

SELECTION_KINDS = frozenset(
    {
        "subject",
        "background",
        "person",
        "clothes",
        "face",
        "eyes",
        "hands",
        "legs",
        "feet",
        "tap_object",
        "tap_background",
    }
)

YOLO_BBOX_CANDIDATES = {
    "face": ["face_yolov8m.pt", "face_yolov8n.pt", "face_yolov8s.pt"],
    "hands": ["hand_yolov8n.pt", "hand_yolov8s.pt"],
    "person": ["yolov8n.pt", "yolov8s.pt"],
}


def _mask_output_path() -> Path:
    folder = OUTPUTS_ROOT / "dreamforge" / "temp" / "inpaint_masks"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"mask_{uuid.uuid4().hex}.png"


def _to_gray_mask(array: np.ndarray) -> np.ndarray:
    if array.ndim == 3:
        if array.shape[2] == 4:
            return (array[:, :, 3] > 16).astype(np.uint8) * 255
        return (array[:, :, 0] > 127).astype(np.uint8) * 255
    return (array > 127).astype(np.uint8) * 255


def _bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask > 127)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _apply_bbox_region(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = bbox
    out = np.zeros_like(mask)
    out[y0 : y1 + 1, x0 : x1 + 1] = mask[y0 : y1 + 1, x0 : x1 + 1]
    return out


def _find_yolo_model(candidates: list[str]) -> Path | None:
    try:
        from dreamforge_cli_inventory import MODELS_ROOT
    except Exception:
        return None
    root = Path(MODELS_ROOT)
    search_dirs = [
        root / "ultralytics" / "bbox",
        root / "ultralytics" / "segm",
        root / "ultralytics",
    ]
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for name in candidates:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        for name in candidates:
            matches = sorted(directory.glob(name.replace(".pt", "*.pt")))
            if matches:
                return matches[0]
    return None


def _yolo_union_mask(image: Image.Image, candidates: list[str]) -> tuple[np.ndarray | None, str]:
    model_path = _find_yolo_model(candidates)
    if model_path is None:
        return None, "yolo_model_missing"
    try:
        from ultralytics import YOLO
    except Exception:
        return None, "ultralytics_unavailable"

    model = YOLO(str(model_path))
    results = model(np.array(image.convert("RGB")), verbose=False)
    if not results:
        return None, "yolo_no_results"
    mask = np.zeros((image.height, image.width), dtype=np.uint8)
    found = False
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes.xyxy.cpu().numpy():
            x0, y0, x1, y1 = [int(round(v)) for v in box]
            x0 = max(0, x0)
            y0 = max(0, y0)
            x1 = min(image.width - 1, x1)
            y1 = min(image.height - 1, y1)
            mask[y0 : y1 + 1, x0 : x1 + 1] = 255
            found = True
    if not found:
        return None, "yolo_no_detections"
    return mask, f"yolo:{model_path.name}"


def _rembg_subject_mask(image: Image.Image) -> tuple[np.ndarray, str]:
    import rembg

    session = rembg.new_session()
    rgba = rembg.remove(image.convert("RGBA"), session=session)
    alpha = np.array(rgba)[:, :, 3]
    mask = (alpha > 16).astype(np.uint8) * 255
    return mask, "rembg"


def _heuristic_face_mask(subject: np.ndarray) -> np.ndarray:
    bbox = _bbox_from_mask(subject)
    if bbox is None:
        return np.zeros_like(subject)
    x0, y0, x1, y1 = bbox
    h = max(1, y1 - y0 + 1)
    w = max(1, x1 - x0 + 1)
    face = np.zeros_like(subject)
    fy1 = y0 + int(h * 0.32)
    fx0 = x0 + int(w * 0.18)
    fx1 = x1 - int(w * 0.18)
    face[y0:fy1, fx0 : fx1 + 1] = 255
    return face & subject


def _heuristic_eyes_mask(face_mask: np.ndarray) -> np.ndarray:
    bbox = _bbox_from_mask(face_mask)
    if bbox is None:
        return np.zeros_like(face_mask)
    x0, y0, x1, y1 = bbox
    h = max(1, y1 - y0 + 1)
    w = max(1, x1 - x0 + 1)
    eye_band_top = y0 + int(h * 0.18)
    eye_band_bottom = y0 + int(h * 0.52)
    out = np.zeros_like(face_mask)
    radius_x = max(2, int(w * 0.11))
    radius_y = max(2, int(h * 0.09))
    centers = [
        (x0 + int(w * 0.33), eye_band_top + (eye_band_bottom - eye_band_top) // 2),
        (x0 + int(w * 0.67), eye_band_top + (eye_band_bottom - eye_band_top) // 2),
    ]
    yy, xx = np.ogrid[: face_mask.shape[0], : face_mask.shape[1]]
    for cx, cy in centers:
        ellipse = (((xx - cx) ** 2) / (radius_x**2 + 1e-6) + ((yy - cy) ** 2) / (radius_y**2 + 1e-6)) <= 1.0
        out[ellipse] = 255
    return out & face_mask


def _heuristic_hands_mask(subject: np.ndarray) -> np.ndarray:
    bbox = _bbox_from_mask(subject)
    if bbox is None:
        return np.zeros_like(subject)
    x0, y0, x1, y1 = bbox
    h = max(1, y1 - y0 + 1)
    w = max(1, x1 - x0 + 1)
    band_top = y0 + int(h * 0.42)
    band_bottom = y0 + int(h * 0.72)
    out = np.zeros_like(subject)
    left = np.zeros_like(subject)
    right = np.zeros_like(subject)
    left[band_top:band_bottom, x0 : x0 + int(w * 0.28)] = 255
    right[band_top:band_bottom, x1 - int(w * 0.28) : x1 + 1] = 255
    out = (left | right) & subject
    return out


def _vertical_band_mask(subject: np.ndarray, start_ratio: float, end_ratio: float) -> np.ndarray:
    bbox = _bbox_from_mask(subject)
    if bbox is None:
        return np.zeros_like(subject)
    x0, y0, x1, y1 = bbox
    h = max(1, y1 - y0 + 1)
    top = y0 + int(h * start_ratio)
    bottom = y0 + int(h * end_ratio)
    band = np.zeros_like(subject)
    band[top : bottom + 1, x0 : x1 + 1] = 255
    return band & subject


def _clothes_mask(subject: np.ndarray, face_mask: np.ndarray) -> np.ndarray:
    head = face_mask.copy()
    bbox = _bbox_from_mask(subject)
    if bbox is not None:
        x0, y0, x1, y1 = bbox
        h = max(1, y1 - y0 + 1)
        head[y0 : y0 + int(h * 0.28), x0 : x1 + 1] = 255
    clothes = subject.copy()
    clothes[head > 127] = 0
    return clothes


def _tap_object_mask(image: Image.Image, tap_x: float, tap_y: float) -> tuple[np.ndarray, str]:
    import cv2

    rgb = np.array(image.convert("RGB"))
    h, w = rgb.shape[:2]
    px = int(round(max(0.0, min(1.0, tap_x)) * (w - 1)))
    py = int(round(max(0.0, min(1.0, tap_y)) * (h - 1)))

    # Color-region flood fill (Samsung tap / circle selection fallback).
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    tolerance = 28
    work = bgr.copy()
    cv2.floodFill(
        work,
        flood_mask,
        (px, py),
        (255, 255, 255),
        (tolerance, tolerance, tolerance),
        (tolerance, tolerance, tolerance),
        cv2.FLOODFILL_MASK_ONLY,
    )
    region = flood_mask[1:-1, 1:-1] * 255
    coverage = float(np.count_nonzero(region)) / float(region.size)
    if coverage > 0.72:
        region = np.zeros((h, w), dtype=np.uint8)

    if np.count_nonzero(region) < 32:
        try:
            subject, _ = _rembg_subject_mask(image)
            labels = cv2.connectedComponents((subject > 127).astype(np.uint8))[1]
            label = labels[py, px]
            if label > 0:
                region = (labels == label).astype(np.uint8) * 255
        except Exception:
            pass

    if np.count_nonzero(region) < 32:
        radius = max(8, min(w, h) // 24)
        yy, xx = np.ogrid[:h, :w]
        circle = ((xx - px) ** 2 + (yy - py) ** 2) <= radius**2
        region = circle.astype(np.uint8) * 255

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    region = cv2.morphologyEx(region, cv2.MORPH_CLOSE, kernel, iterations=2)
    return region, "tap_floodfill"


def _save_mask(mask: np.ndarray, output_path: Path | None = None) -> str:
    path = output_path or _mask_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_to_gray_mask(mask), mode="L").save(path, format="PNG")
    return str(path.resolve())


def generate_inpaint_selection_mask(
    image_path: str,
    selection: str,
    *,
    tap_x: float | None = None,
    tap_y: float | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build a grayscale inpaint mask (white = edit region)."""
    kind = str(selection or "").strip().lower()
    if kind not in SELECTION_KINDS:
        return {"ok": False, "error": f"selection_invalid: {selection}"}

    resolved = resolve_image_path_or_raise(image_path)
    image = Image.open(resolved).convert("RGB")
    method = kind
    mask: np.ndarray

    if kind in {"tap_object", "tap_background"}:
        if tap_x is None or tap_y is None:
            return {"ok": False, "error": "tap_coordinates_required"}
        mask, method = _tap_object_mask(image, float(tap_x), float(tap_y))
        if kind == "tap_background":
            mask = 255 - _to_gray_mask(mask)
            method = f"{method}_background"
    else:
        subject, subject_method = _rembg_subject_mask(image)
        if kind in {"subject", "person"}:
            mask = subject
            method = subject_method
        elif kind == "background":
            mask = 255 - subject
            method = f"{subject_method}_invert"
        elif kind == "face":
            yolo_mask, yolo_method = _yolo_union_mask(image, YOLO_BBOX_CANDIDATES["face"])
            mask = yolo_mask if yolo_mask is not None else _heuristic_face_mask(subject)
            method = yolo_method if yolo_mask is not None else "heuristic_face"
        elif kind == "eyes":
            face_yolo, _ = _yolo_union_mask(image, YOLO_BBOX_CANDIDATES["face"])
            face = face_yolo if face_yolo is not None else _heuristic_face_mask(subject)
            mask = _heuristic_eyes_mask(face)
            method = "heuristic_eyes"
        elif kind == "hands":
            yolo_mask, yolo_method = _yolo_union_mask(image, YOLO_BBOX_CANDIDATES["hands"])
            mask = yolo_mask if yolo_mask is not None else _heuristic_hands_mask(subject)
            method = yolo_method if yolo_mask is not None else "heuristic_hands"
        elif kind == "legs":
            mask = _vertical_band_mask(subject, 0.52, 0.98)
            method = "heuristic_legs"
        elif kind == "feet":
            mask = _vertical_band_mask(subject, 0.82, 1.0)
            method = "heuristic_feet"
        elif kind == "clothes":
            face_yolo, _ = _yolo_union_mask(image, YOLO_BBOX_CANDIDATES["face"])
            face = face_yolo if face_yolo is not None else _heuristic_face_mask(subject)
            mask = _clothes_mask(subject, face)
            method = "heuristic_clothes"
        else:
            return {"ok": False, "error": f"selection_unhandled: {kind}"}

    if np.count_nonzero(_to_gray_mask(mask)) == 0:
        return {"ok": False, "error": "empty_selection", "method": method}

    out = Path(output_path).resolve() if output_path else None
    saved = _save_mask(mask, out)
    return {
        "ok": True,
        "mask_path": saved,
        "selection": kind,
        "method": method,
        "coverage": round(float(np.count_nonzero(_to_gray_mask(mask))) / float(mask.size), 4),
    }
