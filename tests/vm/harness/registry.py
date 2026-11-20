"""A minimal OCI distribution registry for the update tests (task P1-14).

It runs inside the offline test container on 127.0.0.1; the guest reaches it as
10.0.2.2 through QEMU's user network. It implements only what skopeo needs to push
an image with its sigstore signature attachments, and what bootc needs to pull it:

- GET /v2/                                   version check
- HEAD/GET /v2/<name>/blobs/<digest>         blob existence and download
- POST /v2/<name>/blobs/uploads/             start an upload (cross-repository
                                             mounts are not supported; the client
                                             falls back to an upload)
- PATCH /v2/<name>/blobs/uploads/<id>        append data (plain or chunked body)
- PUT /v2/<name>/blobs/uploads/<id>?digest=  finish an upload; the digest is checked
- HEAD/GET/PUT /v2/<name>/manifests/<ref>    manifests by tag or digest

There is no authentication and no TLS: the registry is reachable only from inside the
test container and its virtual machine. It never decides what is trustworthy; that is
the job of the signature policy in the guest.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

NAME = r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ROUTE = re.compile(rf"^/v2/(?P<name>{NAME})/(?P<kind>blobs|manifests)/(?P<ref>[^/]+)$")
UPLOADS = re.compile(rf"^/v2/(?P<name>{NAME})/blobs/uploads/(?P<id>[0-9a-f-]*)$")
CHUNK = 1024 * 1024


class Storage:
    """Blobs by digest (shared by all repositories) and manifests per repository."""

    def __init__(self, root: Path):
        self.root = root
        for part in ("blobs", "uploads", "manifests"):
            (root / part).mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def blob(self, digest: str) -> Path:
        return self.root / "blobs" / digest.replace(":", "-")

    def upload(self, upload_id: str) -> Path:
        return self.root / "uploads" / upload_id

    def manifest_dir(self, name: str) -> Path:
        path = self.root / "manifests" / name.replace("/", "__")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def put_manifest(self, name: str, reference: str, body: bytes, media_type: str) -> str:
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        if DIGEST.match(reference) and reference != digest:
            raise ValueError("manifest digest does not match the reference")
        directory = self.manifest_dir(name)
        with self.lock:
            (directory / digest.replace(":", "-")).write_bytes(body)
            (directory / (digest.replace(":", "-") + ".type")).write_text(media_type)
            if not DIGEST.match(reference):
                (directory / f"tag-{reference}").write_text(digest)
        return digest

    def get_manifest(self, name: str, reference: str) -> tuple[bytes, str, str] | None:
        directory = self.manifest_dir(name)
        digest = reference
        if not DIGEST.match(reference):
            tag = directory / f"tag-{reference}"
            if not tag.is_file():
                return None
            digest = tag.read_text()
        path = directory / digest.replace(":", "-")
        if not path.is_file():
            return None
        media_type = (directory / (digest.replace(":", "-") + ".type")).read_text()
        return path.read_bytes(), media_type, digest


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    storage: Storage  # set by Registry

    def log_message(self, format, *args):  # noqa: A002 - signature of the base class
        with (self.storage.root / "access.log").open("a") as log:
            log.write(f"{self.address_string()} {format % args}\n")

    # -- helpers -----------------------------------------------------------------

    def reply(self, status: int, body: bytes = b"", headers: dict | None = None) -> None:
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Docker-Distribution-API-Version", "registry/2.0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def error(self, status: int, code: str, message: str) -> None:
        body = json.dumps({"errors": [{"code": code, "message": message}]}).encode()
        self.reply(status, body, {"Content-Type": "application/json"})

    def read_body(self, sink) -> int:
        """Copy the request body to `sink`, plain or chunked. Returns bytes read."""
        total = 0
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                        pass
                    return total
                remaining = size
                while remaining:
                    data = self.rfile.read(min(CHUNK, remaining))
                    sink.write(data)
                    remaining -= len(data)
                total += size
                self.rfile.readline()
        remaining = int(self.headers.get("Content-Length", "0"))
        while remaining:
            data = self.rfile.read(min(CHUNK, remaining))
            if not data:
                break
            sink.write(data)
            remaining -= len(data)
            total += len(data)
        return total

    # -- methods -----------------------------------------------------------------

    def do_GET(self):  # noqa: N802 - name required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path
        if path in ("/v2/", "/v2"):
            return self.reply(HTTPStatus.OK, b"{}", {"Content-Type": "application/json"})
        match = ROUTE.match(path)
        if not match:
            return self.error(HTTPStatus.NOT_FOUND, "NAME_UNKNOWN", path)
        name, kind, ref = match["name"], match["kind"], match["ref"]
        if kind == "blobs":
            blob = self.storage.blob(ref)
            if not DIGEST.match(ref) or not blob.is_file():
                return self.error(HTTPStatus.NOT_FOUND, "BLOB_UNKNOWN", ref)
            size = blob.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Docker-Content-Digest", ref)
            self.end_headers()
            if self.command != "HEAD":
                with blob.open("rb") as handle:
                    shutil.copyfileobj(handle, self.wfile, CHUNK)
            return None
        found = self.storage.get_manifest(name, ref)
        if found is None:
            return self.error(HTTPStatus.NOT_FOUND, "MANIFEST_UNKNOWN", ref)
        body, media_type, digest = found
        return self.reply(
            HTTPStatus.OK, body, {"Content-Type": media_type, "Docker-Content-Digest": digest}
        )

    do_HEAD = do_GET  # noqa: N815

    def do_POST(self):  # noqa: N802
        path = urlsplit(self.path).path
        match = UPLOADS.match(path)
        if not match or match["id"]:
            return self.error(HTTPStatus.NOT_FOUND, "UNSUPPORTED", path)
        upload_id = str(uuid.uuid4())
        self.storage.upload(upload_id).touch()
        query = parse_qs(urlsplit(self.path).query)
        if "digest" in query:  # monolithic upload in one POST
            with self.storage.upload(upload_id).open("ab") as sink:
                self.read_body(sink)
            return self.complete_upload(match["name"], upload_id, query["digest"][0])
        with Path("/dev/null").open("wb") as discard:
            self.read_body(discard)
        location = f"/v2/{match['name']}/blobs/uploads/{upload_id}"
        return self.reply(
            HTTPStatus.ACCEPTED,
            headers={"Location": location, "Range": "0-0", "Docker-Upload-UUID": upload_id},
        )

    def do_PATCH(self):  # noqa: N802
        match = UPLOADS.match(urlsplit(self.path).path)
        if not match or not self.storage.upload(match["id"]).is_file():
            return self.error(HTTPStatus.NOT_FOUND, "BLOB_UPLOAD_UNKNOWN", self.path)
        upload = self.storage.upload(match["id"])
        with upload.open("ab") as sink:
            self.read_body(sink)
        size = upload.stat().st_size
        location = f"/v2/{match['name']}/blobs/uploads/{match['id']}"
        return self.reply(
            HTTPStatus.ACCEPTED,
            headers={"Location": location, "Range": f"0-{max(size - 1, 0)}"},
        )

    def do_PUT(self):  # noqa: N802
        parts = urlsplit(self.path)
        upload = UPLOADS.match(parts.path)
        if upload and upload["id"]:
            if not self.storage.upload(upload["id"]).is_file():
                return self.error(HTTPStatus.NOT_FOUND, "BLOB_UPLOAD_UNKNOWN", self.path)
            with self.storage.upload(upload["id"]).open("ab") as sink:
                self.read_body(sink)
            digest = parse_qs(parts.query).get("digest", [""])[0]
            return self.complete_upload(upload["name"], upload["id"], digest)
        match = ROUTE.match(parts.path)
        if not match or match["kind"] != "manifests":
            return self.error(HTTPStatus.NOT_FOUND, "UNSUPPORTED", parts.path)

        class Buffer:
            def __init__(self):
                self.data = bytearray()

            def write(self, chunk):
                self.data += chunk

        buffer = Buffer()
        self.read_body(buffer)
        media_type = self.headers.get("Content-Type", "application/vnd.oci.image.manifest.v1+json")
        try:
            digest = self.storage.put_manifest(
                match["name"], match["ref"], bytes(buffer.data), media_type
            )
        except ValueError as problem:
            return self.error(HTTPStatus.BAD_REQUEST, "DIGEST_INVALID", str(problem))
        location = f"/v2/{match['name']}/manifests/{digest}"
        return self.reply(
            HTTPStatus.CREATED, headers={"Location": location, "Docker-Content-Digest": digest}
        )

    def complete_upload(self, name: str, upload_id: str, digest: str):
        upload = self.storage.upload(upload_id)
        if not DIGEST.match(digest):
            return self.error(HTTPStatus.BAD_REQUEST, "DIGEST_INVALID", digest)
        hasher = hashlib.sha256()
        with upload.open("rb") as handle:
            for block in iter(lambda: handle.read(CHUNK), b""):
                hasher.update(block)
        if "sha256:" + hasher.hexdigest() != digest:
            upload.unlink()
            return self.error(HTTPStatus.BAD_REQUEST, "DIGEST_INVALID", "content mismatch")
        upload.replace(self.storage.blob(digest))
        return self.reply(
            HTTPStatus.CREATED,
            headers={"Location": f"/v2/{name}/blobs/{digest}", "Docker-Content-Digest": digest},
        )


class Registry:
    """The registry on 127.0.0.1:<port>, serving from a directory, in a thread."""

    def __init__(self, root: Path, port: int = 0):
        storage = Storage(root)
        handler = type("BoundHandler", (Handler,), {"storage": storage})
        self.server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> Registry:
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()
