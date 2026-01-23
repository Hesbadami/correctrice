import os
import logging
import urllib.request
from pathlib import Path
import magic
import mimetypes

logger = logging.getLogger("filemanager")

MEDIA_ROOT = os.environ.get("MEDIA_ROOT")

class FileManager:
    def __init__(self):
        self.root = Path(MEDIA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileManager initialized with root: {self.root}")

    def _find_existing(self, namespace, key):
        directory = self.root.joinpath(*namespace.split('.'))
        if not directory.exists():
            return None
        for f in directory.iterdir():
            if f.is_file() and f.stem == str(key):
                return f
        return None

    def _resolve_path(self, namespace, key, mime_type=None):
        directory = self.root.joinpath(*namespace.split('.'))
        directory.mkdir(parents=True, exist_ok=True)
        ext = mimetypes.guess_extension(mime_type) if mime_type else ""
        return directory / f"{key}{ext}"
    
    def get_upload_tuple(self, namespace, key):
        f = self._find_existing(namespace, key)
        if not f:
            return None
        
        buffer = f.read_bytes()
        mime_type = magic.from_buffer(buffer, mime=True)
        
        return (f.name, buffer, mime_type)

    def save(self, namespace, key, binary, replace=True):
        existing = self._find_existing(namespace, key)
        if existing and not replace:
            return existing

        if isinstance(binary, bytes):
            tmp_bytes = binary
        elif hasattr(binary, "read"):
            tmp_bytes = binary.read()
        else:
            raise TypeError("Unsupported binary type")

        mime_type = magic.from_buffer(tmp_bytes, mime=True)
        file_path = self._resolve_path(namespace, key, mime_type)

        if replace:
            directory = self.root.joinpath(*namespace.split('.'))
            for f in directory.iterdir():
                if f.is_file() and f.stem == str(key) and f != file_path:
                    f.unlink()
                    logger.info(f"Replaced old file variant: {f}")

        with open(file_path, "wb") as f:
            f.write(tmp_bytes)

        logger.info(f"Saved file {namespace}.{key} → {file_path}")
        return file_path

    def download(self, namespace, key, url, replace=True):
        existing = self._find_existing(namespace, key)
        if existing and not replace:
            return existing

        logger.info(f"Downloading {url}")
        response = urllib.request.urlopen(url)
        data = response.read()
        mime_type = response.headers.get_content_type()

        file_path = self._resolve_path(namespace, key, mime_type)

        if replace:
            directory = self.root.joinpath(*namespace.split('.'))
            for f in directory.iterdir():
                if f.is_file() and f.stem == str(key) and f != file_path:
                    f.unlink()
                    logger.info(f"Replaced old file variant: {f}")

        with open(file_path, "wb") as f:
            f.write(data)

        logger.info(f"Saved {namespace}.{key} from {url} → {file_path}")
        return file_path

    def read(self, namespace, key):
        f = self._find_existing(namespace, key)
        if not f:
            return None
        return f.read_bytes()

    def delete(self, namespace, key):
        f = self._find_existing(namespace, key)
        if f:
            f.unlink()
            logger.info(f"Deleted {namespace}.{key}")
            return True
        return False

    def url(self, namespace, key, domain=""):
        f = self._find_existing(namespace, key)
        if not f:
            return None
        rel = f.relative_to(self.root)
        if domain:
            return f"{domain}{rel}"
        return rel

fm = FileManager()
