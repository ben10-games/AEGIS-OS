"""The test registry speaks enough of the OCI distribution protocol for skopeo and bootc."""

import hashlib
import http.client
import json

import pytest
from harness.registry import Registry


@pytest.fixture
def registry(tmp_path):
    with Registry(tmp_path / "registry") as running:
        yield running


def request(registry, method, path, body=None, headers=None, chunked=False):
    connection = http.client.HTTPConnection("127.0.0.1", registry.port, timeout=10)
    if chunked:
        connection.putrequest(method, path)
        for key, value in (headers or {}).items():
            connection.putheader(key, value)
        connection.putheader("Transfer-Encoding", "chunked")
        connection.endheaders()
        for start in range(0, len(body), 7):
            piece = body[start : start + 7]
            connection.send(b"%x\r\n%s\r\n" % (len(piece), piece))
        connection.send(b"0\r\n\r\n")
    else:
        connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response, data


def digest_of(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def test_version_check(registry):
    response, _ = request(registry, "GET", "/v2/")
    assert response.status == 200


def test_chunked_upload_then_download(registry):
    blob = b"layer content " * 100
    response, _ = request(registry, "POST", "/v2/aegis-os/aegis-dev/blobs/uploads/")
    assert response.status == 202
    location = response.getheader("Location")
    response, _ = request(registry, "PATCH", location, body=blob, chunked=True)
    assert response.status == 202
    response, _ = request(registry, "PUT", f"{location}?digest={digest_of(blob)}")
    assert response.status == 201
    response, data = request(registry, "GET", f"/v2/aegis-os/aegis-dev/blobs/{digest_of(blob)}")
    assert response.status == 200 and data == blob
    response, data = request(registry, "HEAD", f"/v2/aegis-os/aegis-dev/blobs/{digest_of(blob)}")
    assert response.status == 200 and data == b""
    assert response.getheader("Content-Length") == str(len(blob))


def test_wrong_digest_is_refused(registry):
    response, _ = request(registry, "POST", "/v2/aegis-os/x/blobs/uploads/")
    location = response.getheader("Location")
    request(registry, "PATCH", location, body=b"abc", headers={"Content-Length": "3"})
    response, _ = request(registry, "PUT", f"{location}?digest={digest_of(b'other')}")
    assert response.status == 400
    response, _ = request(registry, "GET", f"/v2/aegis-os/x/blobs/{digest_of(b'abc')}")
    assert response.status == 404


def test_manifest_by_tag_and_digest(registry):
    manifest = json.dumps({"schemaVersion": 2, "layers": []}).encode()
    media = "application/vnd.oci.image.manifest.v1+json"
    response, _ = request(
        registry, "PUT", "/v2/aegis-os/aegis-dev/manifests/v2", body=manifest,
        headers={"Content-Type": media},
    )  # fmt: skip
    assert response.status == 201
    digest = response.getheader("Docker-Content-Digest")
    assert digest == digest_of(manifest)
    for reference in ("v2", digest):
        response, data = request(registry, "GET", f"/v2/aegis-os/aegis-dev/manifests/{reference}")
        assert response.status == 200 and data == manifest
        assert response.getheader("Content-Type") == media
    response, _ = request(registry, "GET", "/v2/aegis-os/aegis-dev/manifests/v9")
    assert response.status == 404
