import os
import zipfile

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def zip_dir(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, start=src_dir)
                zf.write(full, arc)
