import os

from flask import current_app


class LocalDiskDriver:
    def __init__(self, root):
        self.root = root

    def _resolve(self, rel_path):
        # Defense in depth: reject any path that escapes the upload root.
        root = os.path.realpath(self.root)
        full = os.path.realpath(os.path.join(root, rel_path))
        if full != root and not full.startswith(root + os.sep):
            raise ValueError("Path escapes the storage root.")
        return full

    def put(self, rel_path, data):
        full = self._resolve(rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)

    def get(self, rel_path):
        with open(self._resolve(rel_path), "rb") as f:
            return f.read()

    def delete(self, rel_path):
        try:
            os.remove(self._resolve(rel_path))
        except FileNotFoundError:
            pass


def get_storage():
    root = current_app.config.get("UPLOAD_ROOT") or os.path.join(current_app.instance_path, "uploads")
    return LocalDiskDriver(root)
