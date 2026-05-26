# coding: utf-8
"""开机预加载本地模型到 GPU（由 startup.ps1 调用）

加载顺序：wake_word → silero_vad → sensevoice
OmniParser 暂未转 ONNX，跳过。
游戏模式下 watchdog 会自动 unload sensevoice 释放显存。
"""
import os
import sys
import time

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MODELS = [
    ("wake_word", os.path.join(ROOT, "models", "wake_word", "xiaozhang_wakeword.onnx")),
    ("silero_vad", os.path.join(ROOT, "models", "silero_vad.onnx")),
    ("sensevoice", os.path.join(ROOT, "models", "sensevoice_small.onnx")),
    ("omniparser_yolo", os.path.join(ROOT, "models", "omniparser_v2", "icon_detect", "model.onnx")),
]


def main():
    try:
        import onnxruntime as ort
    except ImportError:
        print("ERROR: onnxruntime not installed", flush=True)
        return 1

    print(f"ONNX Runtime providers: {ort.get_available_providers()}", flush=True)

    all_gpu = True
    for name, path in MODELS:
        if not os.path.isfile(path):
            print(f"  {name}: SKIP (file missing: {path})", flush=True)
            continue

        t0 = time.time()
        try:
            sess = ort.InferenceSession(
                path,
                providers=["DmlExecutionProvider", "CPUExecutionProvider"],
            )
            gpu = "DmlExecutionProvider" in sess.get_providers()
            tag = "GPU" if gpu else "CPU"
            elapsed = time.time() - t0
            print(f"  {name}: {tag} ({elapsed:.1f}s)", flush=True)
            if not gpu:
                all_gpu = False
            # 释放 session（实际守护进程会自己加载）
            del sess
        except Exception as e:
            print(f"  {name}: FAILED ({e})", flush=True)
            all_gpu = False

    if all_gpu:
        print("All models loaded on GPU successfully.", flush=True)
    else:
        print("WARNING: some models on CPU or failed.", flush=True)

    # RapidOCR（3 个内置 ONNX session，走 DirectML）
    print("  rapidocr: loading...", flush=True)
    try:
        from rapidocr_onnxruntime import RapidOCR
        t0 = time.time()
        ocr = RapidOCR(det_use_dml=True, rec_use_dml=True, cls_use_dml=True)
        elapsed = time.time() - t0
        print(f"  rapidocr: GPU ({elapsed:.1f}s)", flush=True)
        del ocr
    except ImportError:
        print("  rapidocr: SKIP (not installed)", flush=True)
    except Exception as e:
        print(f"  rapidocr: FAILED ({e})", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
