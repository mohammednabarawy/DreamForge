"""One-off E2E test: Qwen Edit + reference + Speed/Lightning."""
from __future__ import annotations

import json
import sys
import time
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from _paths import extend_sys_path

extend_sys_path()

PROMPT_FILE = BACKEND / "outputs" / "test_runs" / "arabic_cover_prompt.txt"
NEG_FILE = BACKEND / "outputs" / "test_runs" / "arabic_cover_negative.txt"
REF_IMAGE = Path(
    r"C:\Users\moham\Desktop\1778182698575-1777642911342-20240709_010711_5aacb593d990bb7575608e3404fdab2b.jpeg"
)
OUT_DIR = BACKEND / "outputs" / "test_runs"
OUT_IMAGE = OUT_DIR / "arabic_cover_qwen_speed_test.png"
LOG_FILE = OUT_DIR / "arabic_cover_qwen_speed_test.log"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not REF_IMAGE.is_file():
        print(json.dumps({"status": "error", "message": f"reference missing: {REF_IMAGE}"}))
        return 1

    prompt = PROMPT_FILE.read_text(encoding="utf-8").strip()
    negative = NEG_FILE.read_text(encoding="utf-8").strip()

    args = Namespace(
        model="qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        prompt=prompt,
        negative_prompt=negative,
        width=832,
        height=1248,
        aspect_ratio=None,
        seed=42,
        image_number=1,
        output=str(OUT_IMAGE),
        performance="Speed",
        steps=None,
        cfg_scale=None,
        sampler=None,
        scheduler=None,
        styles=None,
        lora=[],
        input_image=str(REF_IMAGE),
        reference_images=None,
        comfy_workflow_api=None,
        use_comfy_server=True,
        upscale_image=None,
        upscale_method="2x",
        edit_type="qwen_edit",
        edit_strength=1.0,
        qwen_edit_mode="single",
        qwen_image_shift=None,
        qwen_scale_megapixels=1.0,
        inpaint_mask_path=None,
        cn_selection="None",
        cn_type="None",
        controlnet_model=None,
        cn_strength=None,
        cn_start=None,
        cn_stop=None,
        outpaint_left=0,
        outpaint_top=0,
        outpaint_right=0,
        outpaint_bottom=0,
        outpaint_amount=256,
        outpaint_direction="",
        outpaint_feathering=40,
        hires=False,
        workflow_mode=None,
        reference_mode="",
        vram_profile="16gb",
        use_case="image_edit",
        validate_output=True,
        json=True,
        dry_run=False,
        batch=None,
        brain_plan=False,
        subcommand="generate",
    )

    from dreamforge_comfy_server import boot_managed_comfy_server

    import os

    os.environ.setdefault("DREAMFORGE_USE_COMFY_SERVER", "1")

    t0 = time.time()
    lines: list[str] = []

    def log(msg: str) -> None:
        lines.append(msg)
        print(msg, flush=True)

    log("Booting Comfy server…")
    boot_managed_comfy_server()

    from dreamforge_cli_direct import process_single

    log("Starting Qwen Edit generation (Speed + Lightning LoRA)…")
    result = process_single(args)
    elapsed = round(time.time() - t0, 1)
    result["elapsed_seconds"] = elapsed
    LOG_FILE.write_text("\n".join(lines) + "\n" + json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
