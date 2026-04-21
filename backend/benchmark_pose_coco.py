#!/usr/bin/env python3
"""Quantitatively benchmark MediaPipe Pose on COCO keypoints.

This script evaluates 2D keypoint accuracy on a configurable subset of
COCO val2017 person instances and reports:
  - PCK@0.05 and PCK@0.10 (normalized by sqrt(bbox_area))
  - Mean normalized keypoint error
  - Per-joint normalized error and PCK@0.10

It is designed for ErgoPilot's current CV stack (MediaPipe landmarks in browser).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


COCO_ANN_ZIP_URL = "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
COCO_VAL_IMAGES_ZIP_URL = "http://images.cocodataset.org/zips/val2017.zip"
MEDIAPIPE_POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

ANN_REL_PATH = Path("annotations/person_keypoints_val2017.json")
VAL_DIR_NAME = "val2017"

COCO_KEYPOINT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

# COCO 17-keypoints index -> MediaPipe Pose landmark index
COCO_TO_MEDIAPIPE = {
    0: 0,   # nose
    1: 2,   # left_eye
    2: 5,   # right_eye
    3: 7,   # left_ear
    4: 8,   # right_ear
    5: 11,  # left_shoulder
    6: 12,  # right_shoulder
    7: 13,  # left_elbow
    8: 14,  # right_elbow
    9: 15,  # left_wrist
    10: 16, # right_wrist
    11: 23, # left_hip
    12: 24, # right_hip
    13: 25, # left_knee
    14: 26, # right_knee
    15: 27, # left_ankle
    16: 28, # right_ankle
}


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading: {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"Saved: {dest}")


def extract_zip(zip_path: Path, out_dir: Path) -> None:
    print(f"Extracting: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    print(f"Extracted to: {out_dir}")


def ensure_coco(dataset_dir: Path, allow_download: bool) -> tuple[Path, Path]:
    ann_path = dataset_dir / ANN_REL_PATH
    images_dir = dataset_dir / VAL_DIR_NAME

    if ann_path.exists() and images_dir.exists():
        return ann_path, images_dir

    if not allow_download:
        raise FileNotFoundError(
            "COCO files not found. Pass --download or place files manually:\n"
            f"- {ann_path}\n"
            f"- {images_dir}"
        )

    ann_zip = dataset_dir / "annotations_trainval2017.zip"
    val_zip = dataset_dir / "val2017.zip"

    if not ann_path.exists():
        if not ann_zip.exists():
            download_file(COCO_ANN_ZIP_URL, ann_zip)
        extract_zip(ann_zip, dataset_dir)
    if not images_dir.exists():
        if not val_zip.exists():
            download_file(COCO_VAL_IMAGES_ZIP_URL, val_zip)
        extract_zip(val_zip, dataset_dir)

    if not ann_path.exists() or not images_dir.exists():
        raise FileNotFoundError("COCO download/extract did not produce expected files.")

    return ann_path, images_dir


def ensure_pose_model(model_path: Path, allow_download: bool) -> Path:
    if model_path.exists():
        return model_path
    if not allow_download:
        raise FileNotFoundError(
            f"Pose model missing at {model_path}. "
            "Pass --download-model (or --download) to fetch it automatically."
        )
    model_path.parent.mkdir(parents=True, exist_ok=True)
    download_file(MEDIAPIPE_POSE_MODEL_URL, model_path)
    return model_path


def load_coco_people(
    ann_path: Path,
    num_instances: int,
    min_keypoints: int,
    min_bbox_area: float,
    seed: int,
) -> tuple[dict[int, str], list[dict]]:
    with ann_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    image_id_to_name = {img["id"]: img["file_name"] for img in payload["images"]}

    annotations: list[dict] = []
    for ann in payload["annotations"]:
        if ann.get("iscrowd", 0) == 1:
            continue
        if ann.get("num_keypoints", 0) < min_keypoints:
            continue
        bbox = ann.get("bbox", [0, 0, 0, 0])
        _, _, bw, bh = bbox
        if float(bw) * float(bh) < min_bbox_area:
            continue
        annotations.append(ann)

    if not annotations:
        raise RuntimeError("No COCO annotations passed the selection filters.")

    rng = random.Random(seed)
    rng.shuffle(annotations)
    selected = annotations[: min(num_instances, len(annotations))]
    return image_id_to_name, selected


def crop_with_padding(
    image: "np.ndarray",
    bbox: list[float],
    pad_ratio: float,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    h, w = image.shape[:2]
    x, y, bw, bh = bbox
    x1 = max(0, int(math.floor(x - bw * pad_ratio)))
    y1 = max(0, int(math.floor(y - bh * pad_ratio)))
    x2 = min(w, int(math.ceil(x + bw * (1.0 + pad_ratio))))
    y2 = min(h, int(math.ceil(y + bh * (1.0 + pad_ratio))))
    crop = image[y1:y2, x1:x2]
    return crop, (x1, y1, x2, y2)


def evaluate(
    images_dir: Path,
    image_id_to_name: dict[int, str],
    anns: list[dict],
    model_path: Path,
    model_complexity: int,
    min_detection_confidence: float,
    min_tracking_confidence: float,
    pad_ratio: float,
) -> dict[str, object]:
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(model_path),
            delegate=BaseOptions.Delegate.CPU,
        ),
        running_mode=vision.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=min_detection_confidence,
        min_pose_presence_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )
    pose = vision.PoseLandmarker.create_from_options(options)

    all_norm_errors: list[float] = []
    joint_norm_errors: dict[str, list[float]] = defaultdict(list)
    pck_hits_005 = 0
    pck_hits_010 = 0
    pck_total = 0
    processed_instances = 0
    skipped_no_image = 0
    skipped_no_pose = 0

    try:
        for ann in anns:
            image_name = image_id_to_name.get(ann["image_id"])
            if image_name is None:
                skipped_no_image += 1
                continue
            image_path = images_dir / image_name
            bgr = cv2.imread(str(image_path))
            if bgr is None:
                skipped_no_image += 1
                continue

            crop, (x1, y1, _x2, _y2) = crop_with_padding(
                bgr,
                ann["bbox"],
                pad_ratio=pad_ratio,
            )
            if crop.size == 0:
                skipped_no_image += 1
                continue

            rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_crop)
            result = pose.detect(mp_image)
            if not result.pose_landmarks:
                skipped_no_pose += 1
                continue

            processed_instances += 1
            c_h, c_w = rgb_crop.shape[:2]
            norm_scale = math.sqrt(max(1.0, float(ann["bbox"][2]) * float(ann["bbox"][3])))
            kpts = ann["keypoints"]  # flat [x, y, v, ...]

            for coco_idx, mp_idx in COCO_TO_MEDIAPIPE.items():
                gt_x, gt_y, v = kpts[coco_idx * 3 : coco_idx * 3 + 3]
                if v <= 0:
                    continue

                lm = result.pose_landmarks[0][mp_idx]
                pred_x = x1 + lm.x * c_w
                pred_y = y1 + lm.y * c_h
                err_px = math.hypot(pred_x - gt_x, pred_y - gt_y)
                err_norm = err_px / norm_scale
                joint_name = COCO_KEYPOINT_NAMES[coco_idx]

                all_norm_errors.append(err_norm)
                joint_norm_errors[joint_name].append(err_norm)
                pck_total += 1
                if err_norm <= 0.05:
                    pck_hits_005 += 1
                if err_norm <= 0.10:
                    pck_hits_010 += 1
    finally:
        if hasattr(pose, "close"):
            pose.close()

    if pck_total == 0:
        raise RuntimeError(
            "No valid keypoints were evaluated. Try larger --num-instances, "
            "or lower filters like --min-keypoints."
        )

    per_joint = {}
    for k, vals in sorted(joint_norm_errors.items()):
        per_joint[k] = {
            "count": len(vals),
            "mean_norm_error": float(np.mean(vals)),
            "pck@0.10": float(np.mean(np.array(vals) <= 0.10)),
        }

    return {
        "instances_requested": len(anns),
        "instances_processed": processed_instances,
        "skipped_no_image": skipped_no_image,
        "skipped_no_pose": skipped_no_pose,
        "keypoints_evaluated": pck_total,
        "mean_norm_error": float(np.mean(all_norm_errors)),
        "median_norm_error": float(np.median(all_norm_errors)),
        "pck@0.05": pck_hits_005 / pck_total,
        "pck@0.10": pck_hits_010 / pck_total,
        "per_joint": per_joint,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark MediaPipe Pose on COCO val2017 keypoints."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("backend/data/coco"),
        help="Directory containing COCO annotations/ and val2017/.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download/extract required COCO files and pose model if missing.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("backend/data/mediapipe/pose_landmarker_lite.task"),
        help="Path to MediaPipe PoseLandmarker .task model file.",
    )
    parser.add_argument(
        "--download-model",
        action="store_true",
        help="Download the pose landmarker model if missing.",
    )
    parser.add_argument(
        "--num-instances",
        type=int,
        default=500,
        help="Number of random COCO person annotations to evaluate.",
    )
    parser.add_argument(
        "--min-keypoints",
        type=int,
        default=8,
        help="Minimum annotated keypoints per selected person instance.",
    )
    parser.add_argument(
        "--min-bbox-area",
        type=float,
        default=32.0 * 32.0,
        help="Minimum bbox area in pixels^2 for selected instances.",
    )
    parser.add_argument(
        "--pad-ratio",
        type=float,
        default=0.20,
        help="BBox crop padding ratio before pose inference.",
    )
    parser.add_argument(
        "--model-complexity",
        type=int,
        default=1,
        choices=[0, 1, 2],
        help="MediaPipe Pose model complexity (0,1,2).",
    )
    parser.add_argument(
        "--min-detection-confidence",
        type=float,
        default=0.5,
        help="MediaPipe min_detection_confidence.",
    )
    parser.add_argument(
        "--min-tracking-confidence",
        type=float,
        default=0.5,
        help="MediaPipe min_tracking_confidence.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for annotation sampling.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("backend/benchmark_results/coco_pose_metrics.json"),
        help="Where to write benchmark results JSON.",
    )
    args = parser.parse_args()

    try:
        # Delay heavy deps so --help works without installing extras.
        import cv2  # noqa: F401
        import mediapipe as mp  # noqa: F401
        import numpy as np  # noqa: F401
    except ModuleNotFoundError as exc:
        print(
            "Missing benchmark dependency. Install with:\n"
            "  pip install -r backend/requirements-benchmark.txt\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        return 1

    try:
        ann_path, images_dir = ensure_coco(
            dataset_dir=args.dataset_dir,
            allow_download=args.download,
        )
        model_path = ensure_pose_model(
            model_path=args.model_path,
            allow_download=(args.download or args.download_model),
        )
        image_id_to_name, selected = load_coco_people(
            ann_path=ann_path,
            num_instances=args.num_instances,
            min_keypoints=args.min_keypoints,
            min_bbox_area=args.min_bbox_area,
            seed=args.seed,
        )
        metrics = evaluate(
            images_dir=images_dir,
            image_id_to_name=image_id_to_name,
            anns=selected,
            model_path=model_path,
            model_complexity=args.model_complexity,
            min_detection_confidence=args.min_detection_confidence,
            min_tracking_confidence=args.min_tracking_confidence,
            pad_ratio=args.pad_ratio,
        )
    except (FileNotFoundError, RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Benchmark failed: {exc}", file=sys.stderr)
        return 1

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("\n=== COCO Pose Benchmark Results ===")
    print(f"Instances requested: {metrics['instances_requested']}")
    print(f"Instances processed: {metrics['instances_processed']}")
    print(f"Keypoints evaluated: {metrics['keypoints_evaluated']}")
    print(f"Mean normalized error: {metrics['mean_norm_error']:.4f}")
    print(f"Median normalized error: {metrics['median_norm_error']:.4f}")
    print(f"PCK@0.05: {metrics['pck@0.05']:.4f}")
    print(f"PCK@0.10: {metrics['pck@0.10']:.4f}")
    print(f"Saved JSON: {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
