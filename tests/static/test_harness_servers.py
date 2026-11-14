"""Unit tests for the harness DNS and HTTP servers (run anywhere, no privileges)."""

import socket
import struct
import urllib.request

from harness.servers import DnsResponder, MarkerHttpServer, build_response, parse_question


def query(name: str, qtype: int = 1, query_id: int = 0x1234) -> bytes:
    header = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    labels = b"".join(bytes([len(part)]) + part.encode() for part in name.split("."))
    return header + labels + b"\x00" + struct.pack("!HH", qtype, 1)


def test_parse_question():
    name, qtype, end = parse_question(query("Harness.Example"))
    assert (name, qtype) == ("harness.example", 1)
    assert end == len(query("harness.example"))


def test_known_name_gets_an_a_record():
    response = build_response(query("harness.example"), {"harness.example": "10.0.2.2"})
    query_id, flags, questions, answers = struct.unpack("!HHHH", response[:8])
    assert query_id == 0x1234
    assert flags & 0x8000, "not marked as a response"
    assert flags & 0x000F == 0, "unexpected error code"
    assert (questions, answers) == (1, 1)
    assert response.endswith(socket.inet_aton("10.0.2.2"))


def test_unknown_name_does_not_exist():
    response = build_response(query("other.example"), {"harness.example": "10.0.2.2"})
    _id, flags, _questions, answers = struct.unpack("!HHHH", response[:8])
    assert flags & 0x000F == 3  # NXDOMAIN
    assert answers == 0


def test_other_record_types_get_an_empty_answer():
    response = build_response(query("harness.example", qtype=28), {"harness.example": "10.0.2.2"})
    _id, flags, _questions, answers = struct.unpack("!HHHH", response[:8])
    assert flags & 0x000F == 0
    assert answers == 0


def test_responder_answers_over_udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    responder = DnsResponder({"harness.example": "10.0.2.2"}, port=port).start()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(5)
            client.sendto(query("harness.example"), ("127.0.0.1", port))
            response, _ = client.recvfrom(512)
        assert response.endswith(socket.inet_aton("10.0.2.2"))
        assert responder.queries == ["harness.example"]
    finally:
        responder.stop()


def test_http_server_serves_the_marker():
    server = MarkerHttpServer("aegis-marker").start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/marker", timeout=5) as reply:  # noqa: S310
            assert reply.read() == b"aegis-marker"
        assert server.requests == [f"127.0.0.1:{server.port}"]
    finally:
        server.stop()
