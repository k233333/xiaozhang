"""下载 opus.dll 到 venv Scripts 目录"""
import urllib.request
import zipfile
import shutil
from pathlib import Path

OPUS_URL = "https://github.com/xiph/opus/releases/download/v1.5.2/opus-1.5.2-win64.zip"
VENV_SCRIPTS = Path(r"D:\11111begin\xiaozhang\.venv\Scripts")
ZIP_PATH = Path(r"D:\11111begin\xiaozhang\opus_win64.zip")

print(f"Downloading opus from {OPUS_URL}...")
urllib.request.urlretrieve(OPUS_URL, ZIP_PATH)
print(f"Downloaded to {ZIP_PATH}")

with zipfile.ZipFile(ZIP_PATH) as z:
    print("Contents:", z.namelist())
    for name in z.namelist():
        if name.lower().endswith(".dll"):
            print(f"Extracting {name}...")
            data = z.read(name)
            # 放到 venv Scripts（Python 会在这里找 DLL）
            dll_name = Path(name).name
            # opuslib 查找 "opus.dll" 或 "libopus.dll"
            for target_name in ["opus.dll", "libopus.dll", dll_name]:
                target = VENV_SCRIPTS / target_name
                target.write_bytes(data)
                print(f"  -> {target}")

ZIP_PATH.unlink()
print("Done!")
