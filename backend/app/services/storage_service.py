import hashlib
import shutil
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile
from app.core.config import get_settings


ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".zip"}


class StorageService:
    def __init__(self):
        self.root = get_settings().storage_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if self.root not in path.parents:
            raise HTTPException(400, "非法文件路径")
        return path

    async def save_upload(self, file: UploadFile, year: int, achievement_id: int):
        return await self.save(file, Path("achievements") / str(year) / str(achievement_id))

    async def save(self, file: UploadFile, folder: Path):
        extension = Path(file.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, "不支持该文件格式")
        stored = f"{uuid.uuid4().hex}{extension}"
        relative = folder / stored
        target = self.resolve(relative.as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        limit = get_settings().max_upload_mb * 1024 * 1024
        size = 0
        try:
            with target.open("xb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, f"文件不能超过 {get_settings().max_upload_mb}MB")
                    output.write(chunk)
                if not size:
                    raise HTTPException(400, "不能上传空文件")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return stored, relative.as_posix(), size, extension.lstrip(".")

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
