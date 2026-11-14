"""Tiny HTTP and DNS servers run by the test harness on the host side.

The guest reaches the host's loopback interface through QEMU's user network: 10.0.2.2
is the host, and 10.0.2.3 is QEMU's DNS forwarder, which sends queries to the host's
resolver (loopback when the host has none). With these two servers the network tests
need no internet access and give the same result every time.
"""

from __future__ import annotations

import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GUEST_VIEW_OF_HOST = "10.0.2.2"
TYPE_A = 1
CLASS_IN = 1


class MarkerHttpServer:
    """Serves one fixed body at /marker and remembers the Host header of each request."""

    def __init__(self, marker: str):
        self.requests: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append(self.headers.get("Host", ""))
                if self.path != "/marker":
                    self.send_error(404)
                    return
                body = marker.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> MarkerHttpServer:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def parse_question(packet: bytes) -> tuple[str, int, int]:
    """Return (name, type, end offset of the question) of the first question in a query."""
    labels = []
    offset = 12
    while True:
        length = packet[offset]
        offset += 1
        if length == 0:
            break
        labels.append(packet[offset : offset + length].decode("ascii"))
        offset += length
    qtype, _qclass = struct.unpack("!HH", packet[offset : offset + 4])
    return ".".join(labels).lower(), qtype, offset + 4


def build_response(packet: bytes, records: dict[str, str]) -> bytes:
    """Answer A queries for known names; unknown names do not exist."""
    query_id, flags, _qd, _an, _ns, _ar = struct.unpack("!HHHHHH", packet[:12])
    name, qtype, question_end = parse_question(packet)
    question = packet[12:question_end]
    response_flags = 0x8480 | (flags & 0x0100)  # response, authoritative, recursion available
    if name not in records:
        header = struct.pack("!HHHHHH", query_id, response_flags | 3, 1, 0, 0, 0)  # NXDOMAIN
        return header + question
    if qtype != TYPE_A:
        return struct.pack("!HHHHHH", query_id, response_flags, 1, 0, 0, 0) + question
    answer = struct.pack("!HHHIH", 0xC00C, TYPE_A, CLASS_IN, 30, 4) + socket.inet_aton(
        records[name]
    )
    return struct.pack("!HHHHHH", query_id, response_flags, 1, 1, 0, 0) + question + answer


class DnsResponder:
    """Answers A queries from a fixed table over UDP and remembers the names asked for."""

    def __init__(self, records: dict[str, str], address: str = "127.0.0.1", port: int = 53):
        self.records = {name.lower().rstrip("."): ip for name, ip in records.items()}
        self.queries: list[str] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((address, port))
        self._sock.settimeout(0.5)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                packet, peer = self._sock.recvfrom(4096)
            except TimeoutError:
                continue
            except OSError:
                return
            try:
                self.queries.append(parse_question(packet)[0])
                self._sock.sendto(build_response(packet, self.records), peer)
            except (IndexError, struct.error, UnicodeDecodeError):
                continue  # not a DNS query we understand; ignore it

    def start(self) -> DnsResponder:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._sock.close()
