from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from src.config import env


@dataclass(frozen=True)
class R2Settings:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    public_base_url: str
    key_prefix: str

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"


def r2_settings_from_env() -> R2Settings:
    prefix = env("R2_KEY_PREFIX", "sjkx").strip().strip("/")
    public_base = env("R2_PUBLIC_BASE_URL").rstrip("/")
    return R2Settings(
        account_id=env("R2_ACCOUNT_ID"),
        access_key_id=env("R2_ACCESS_KEY_ID"),
        secret_access_key=env("R2_SECRET_ACCESS_KEY"),
        bucket=env("R2_BUCKET"),
        public_base_url=public_base,
        key_prefix=prefix or "sjkx",
    )


class R2Storage:
    def __init__(self, settings: R2Settings) -> None:
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            region_name="auto",
        )

    @property
    def bucket(self) -> str:
        return self._settings.bucket

    @property
    def key_prefix(self) -> str:
        return self._settings.key_prefix

    def public_url(self, key: str) -> str:
        return f"{self._settings.public_base_url}/{key.lstrip('/')}"

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def upload(self, key: str, body: bytes, content_type: str | None) -> None:
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        self._client.put_object(Bucket=self.bucket, Key=key, Body=body, **extra)
