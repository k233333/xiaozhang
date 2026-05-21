# coding: utf-8
"""验证所有本地模型在 GPU (DirectML) 上运行"""
import onnxruntime as ort
import time

print("ONNX providers:", ort.get_available_providers())
has_dml = "DmlExecutionProvider" in ort.get_available_providers()
print("DirectML GPU:", "YES" if has_dml else "NO")

models = [
    ("wake_word", r"D:\11111begin\xiaozhang\models\wake_word\xiaozhang_wakeword.onnx"),
    ("silero_vad", r"D:\11111begin\xiaozhang\models\silero_vad.onnx"),
    ("sensevoice", r"D:\11111begin\xiaozhang\models\sensevoice_small.onnx"),
]

for name, path in models:
    t0 = time.time()
    try:
        sess = ort.InferenceSession(path, providers=["DmlExecutionProvider", "CPUExecutionProvider"])
        actual = sess.get_providers()
        on_gpu = "DmlExecutionProvider" in actual
        elapsed = time.time() - t0
        tag = "GPU" if on_gpu else "CPU(WARNING)"
        print(f"  {name}: {tag}  load={elapsed:.1f}s  providers={actual}")
    except Exception as e:
        print(f"  {name}: FAIL  error={e}")

print("\nDone.")
