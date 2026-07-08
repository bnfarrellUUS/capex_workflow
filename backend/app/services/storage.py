import os

from flask import current_app


class LocalDiskDriver:
    def __init__(self, root):
        self.root = root

    def put(self, rel_path, data):
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)

    def get(self, rel_path):
        with open(os.path.join(self.root, rel_path), "rb") as f:
            return f.read()

    def delete(self, rel_path):
        try:
            os.remove(os.path.join(self.root, rel_path))
        except FileNotFoundError:
            pass


def get_storage():
    root = current_app.config.get("UPLOAD_ROOT") or os.path.join(current_app.instance_path, "uploads")
    return LocalDiskDriver(root)
