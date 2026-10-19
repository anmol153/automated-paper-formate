import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.security.files import PrivateFiles


class MemoryObjectStore:
    def __init__(self):
        self.values = {}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.values[(Bucket, Key)] = bytes(Body)

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.values:
            raise RuntimeError("missing test object")
        from io import BytesIO
        return {"Body": BytesIO(self.values[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):
        self.values.pop((Bucket, Key), None)


class MemoryBlobStore:
    def __init__(self):
        self.values = {}

    def put_blob(self, pathname, data, *, access, content_type):
        assert access == "private"
        self.values[pathname] = bytes(data)

    def get_blob(self, pathname, *, access):
        assert access == "private"
        if pathname not in self.values:
            raise FileNotFoundError(pathname)
        return SimpleNamespace(body=self.values[pathname])

    def delete_blob(self, pathname):
        self.values.pop(pathname, None)


def test_s3_objects_are_private_verified_and_deletable(tmp_path, monkeypatch):
    settings = SimpleNamespace(s3_bucket="private-test", s3_access_key_id="key",
                               s3_secret_access_key="secret", s3_endpoint_url="",
                               s3_region="auto")
    object_store = MemoryObjectStore()
    files = PrivateFiles(tmp_path)
    monkeypatch.setattr(files, "_object_settings", lambda: settings)
    monkeypatch.setattr(files, "_object_client", lambda _: object_store)
    data = b"paper revision bytes"

    key, digest = files.put(data)
    assert digest == hashlib.sha256(data).hexdigest()
    assert object_store.values[(settings.s3_bucket, f"paper-revisions/{key}")] == data
    assert files.verified(key, digest, len(data)).read_bytes() == data

    with pytest.raises(HTTPException) as exc:
        files.verified(key, "0" * 64, len(data))
    assert exc.value.status_code == 409

    files.discard(key)
    assert (settings.s3_bucket, f"paper-revisions/{key}") not in object_store.values


def test_shared_database_requires_durable_file_storage(monkeypatch):
    settings = SimpleNamespace(s3_bucket=None, s3_access_key_id=None,
                               s3_secret_access_key=None, max_upload_bytes=50 * 1024 * 1024)
    monkeypatch.setattr("app.security.files.get_settings", lambda: settings)
    monkeypatch.setenv("DATABASE_URL", "postgresql://not-used")
    monkeypatch.delenv("BLOB_STORE_ID", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="private Vercel Blob or S3-compatible storage"):
        PrivateFiles("/tmp/private-test")._storage_backend()


def test_private_vercel_blob_revisions_are_verified_and_deletable(tmp_path, monkeypatch):
    settings = SimpleNamespace(s3_bucket=None, s3_access_key_id=None,
                               s3_secret_access_key=None, max_upload_bytes=50 * 1024 * 1024)
    blob_store = MemoryBlobStore()
    files = PrivateFiles(tmp_path)
    monkeypatch.setattr("app.security.files.get_settings", lambda: settings)
    monkeypatch.setattr(files, "_blob_client", lambda: blob_store)
    monkeypatch.setenv("BLOB_STORE_ID", "store-test")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)

    data = b"private paper revision"
    key, digest = files.put(data)
    pathname = f"paper-revisions/{key}"
    assert blob_store.values[pathname] == data
    assert files.verified(key, digest, len(data)).read_bytes() == data

    with pytest.raises(HTTPException) as exc:
        files.verified(key, "0" * 64, len(data))
    assert exc.value.status_code == 409

    files.discard(key)
    assert pathname not in blob_store.values
