"""Network baseline of the development variant: connectivity (V-10), firewall (V-11)
and auditing.

The tests need no internet access. Name resolution and the outbound fetch go to small
servers run by the harness (tests/vm/harness/servers.py). The firewall test starts a
listener inside the guest and probes it from outside, with a positive control.

Tests in this module run in order against one virtual machine.
"""

from __future__ import annotations

import re
import socket
import time
from pathlib import Path

import pytest
from harness.qemu import PROBE_GUEST_PORT
from harness.servers import GUEST_VIEW_OF_HOST, DnsResponder, MarkerHttpServer

SSH_DEADLINE_S = 120
RUNNING_DEADLINE_S = 180
BANNER = b"AEGIS-OPEN"
MARKER = "aegis-outbound-marker"
HARNESS_NAME = "harness.aegis-test.example"
GOLDEN_LISTENERS = Path(__file__).resolve().parents[1] / "golden" / "listening-sockets-dev.txt"


@pytest.fixture(scope="module")
def guest(vm):
    vm.start()
    vm.wait_for_ssh(SSH_DEADLINE_S)
    state = vm.ssh("systemctl is-system-running --wait", timeout=RUNNING_DEADLINE_S, check=False)
    assert state.stdout.strip() == "running", f"system state: {state.stdout.strip()}"
    return vm


@pytest.fixture(scope="module")
def harness_services():
    """An HTTP server and a DNS server on the host side, reachable from the guest."""
    http = MarkerHttpServer(MARKER).start()
    dns = DnsResponder({HARNESS_NAME: GUEST_VIEW_OF_HOST}).start()
    yield http, dns
    dns.stop()
    http.stop()


def read_from_outside(port: int, timeout: float = 5.0) -> bytes:
    """What a machine on the network receives from the guest port behind `port`."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            return sock.recv(64)
    except OSError:
        return b""  # refused, reset or timed out


def test_v10_address_and_route_come_from_dhcp(guest):
    """V-10: the interface has an address and a default route, managed by NetworkManager."""
    addresses = guest.ssh("ip -4 -o addr show scope global").stdout
    assert re.search(r"inet 10\.0\.2\.\d+/", addresses), addresses
    assert guest.ssh("ip -4 route show default").stdout.strip(), "no default route"
    devices = guest.ssh("nmcli -t -f DEVICE,STATE device").stdout
    assert re.search(r"^(?!lo:).+:connected$", devices, re.MULTILINE), devices


def test_v10_resolver_settings(guest):
    """V-10: opportunistic DNS-over-TLS; link-local name resolution is off."""
    assert "opportunistic" in guest.ssh("resolvectl dnsovertls").stdout.splitlines()[0]
    assert guest.ssh("resolvectl llmnr").stdout.splitlines()[0].split()[-1] == "no"
    assert guest.ssh("resolvectl mdns").stdout.splitlines()[0].split()[-1] == "no"


def test_v10_name_resolution_works(guest, harness_services):
    """V-10: a name is resolved through systemd-resolved and the DHCP-provided server."""
    _http, dns = harness_services
    result = guest.ssh(f"resolvectl query --legend=no {HARNESS_NAME}", timeout=60, check=False)
    assert GUEST_VIEW_OF_HOST in result.stdout, result.stdout + result.stderr
    assert HARNESS_NAME in dns.queries, f"the harness DNS server saw: {dns.queries}"
    # The ordinary libc path used by applications gives the same answer.
    assert GUEST_VIEW_OF_HOST in guest.ssh(f"getent ahostsv4 {HARNESS_NAME}").stdout


def test_v10_outbound_connection_works(guest, harness_services):
    """V-10: the guest fetches a page from a server outside, addressed by name."""
    http, _dns = harness_services
    url = f"http://{HARNESS_NAME}:{http.port}/marker"
    assert guest.ssh(f"curl -fsS --max-time 20 {url}", timeout=60).stdout == MARKER
    assert http.requests, "the harness HTTP server received no request"


def test_v10_listening_sockets_equal_the_golden_list(guest, logdir):
    """V-10: nothing listens on the network except what the reviewed list allows."""
    expected = [
        line.strip()
        for line in GOLDEN_LISTENERS.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    actual = guest.ssh("ss -Htuln | awk '{print $1, $5}' | LC_ALL=C sort -u").stdout.splitlines()
    (logdir / "network-listeners.txt").write_text("\n".join(actual) + "\n")
    assert actual == expected, f"listeners differ from tests/golden: {actual}"


def test_v11_firewalld_runs_with_the_aegis_zone(guest):
    """V-11: firewalld is active and the default zone is the AEGIS zone, target DROP."""
    assert guest.ssh("firewall-cmd --state").stdout.strip() == "running"
    assert guest.ssh("firewall-cmd --get-default-zone").stdout.strip() == "aegis"
    zone = guest.ssh("firewall-cmd --zone=aegis --list-all").stdout
    assert re.search(r"^\s*target: DROP$", zone, re.MULTILINE), zone
    services = re.search(r"^\s*services:(.*)$", zone, re.MULTILINE).group(1).split()
    assert sorted(services) == ["dhcpv6-client", "ssh"], services  # ssh: development only
    assert re.search(r"^\s*ports:\s*$", zone, re.MULTILINE), zone
    # The network interface is actually in that zone.
    active = guest.ssh("firewall-cmd --get-active-zones").stdout
    assert re.search(r"^aegis\b.*\n\s+interfaces: \S+", active, re.MULTILINE), active


def test_v11_kernel_ruleset_drops_unsolicited_input(guest, logdir):
    """V-11: in the rules loaded in the kernel, traffic sent to the zone ends in a drop."""
    ruleset = guest.ssh("nft list ruleset").stdout
    (logdir / "firewall-ruleset.txt").write_text(ruleset)
    assert "table inet firewalld" in ruleset
    chains = dict(re.findall(r"chain (\S+) \{(.*?)\n\t\}", ruleset, re.DOTALL))
    assert "filter_IN_aegis" in chains, f"zone chain missing; chains: {sorted(chains)}"
    # firewalld sends input to the zone chain from a dispatch chain and puts the zone's
    # target verdict right after that jump (or at the end of the zone chain itself).
    jump = re.compile(r"^.*jump filter_IN_aegis\s*$", re.MULTILINE)
    verdicts = []
    for name, body in chains.items():
        match = jump.search(body)
        if match:
            following = body[match.end() :].strip().splitlines()
            verdicts.append((name, following[0].strip() if following else ""))
    zone_tail = chains["filter_IN_aegis"].strip().splitlines()[-1].strip()
    dropped = zone_tail.endswith("drop") or any(rule.endswith("drop") for _, rule in verdicts)
    assert dropped, f"no drop after the zone: dispatch={verdicts}, zone chain ends '{zone_tail}'"


def test_firewall_blocks_an_unlisted_listener_from_outside(guest):
    """A service that is not in the zone is unreachable from the network.

    Positive controls: the listener answers on the guest's own loopback, and it becomes
    reachable from outside when its port is temporarily opened.
    """
    port = PROBE_GUEST_PORT
    guest.ssh(
        "systemd-run --quiet --unit=aegis-fw-probe "
        f"socat TCP-LISTEN:{port},fork,reuseaddr 'EXEC:echo {BANNER.decode()}'"
    )
    try:
        for _ in range(20):
            if guest.ssh(f"ss -Htln 'sport = :{port}'", check=False).stdout.strip():
                break
            time.sleep(0.5)
        local = guest.ssh(f"socat -u TCP:127.0.0.1:{port} -", check=False).stdout
        assert BANNER.decode() in local, "listener does not answer on the guest's loopback"

        assert BANNER not in read_from_outside(guest.cfg.probe_port), (
            "listener is reachable from outside although its port is not in the zone"
        )

        guest.ssh(f"firewall-cmd --zone=aegis --add-port={port}/tcp")
        opened = read_from_outside(guest.cfg.probe_port)
        guest.ssh(f"firewall-cmd --zone=aegis --remove-port={port}/tcp")
        assert BANNER in opened, "positive control failed: port opened but not reachable"

        assert BANNER not in read_from_outside(guest.cfg.probe_port), (
            "listener still reachable after the port was closed again"
        )
    finally:
        guest.ssh("systemctl stop aegis-fw-probe", check=False)


def test_audit_daemon_is_running(guest, logdir):
    """Security events are recorded by auditd: daemon attached, auditing on, log written."""
    assert guest.ssh("systemctl is-active auditd").stdout.strip() == "active"
    status = dict(
        line.split(None, 1)
        for line in guest.ssh("auditctl -s").stdout.splitlines()
        if len(line.split(None, 1)) == 2
    )
    assert status.get("enabled") in {"1", "2"}, f"auditing is not enabled: {status}"
    assert int(status.get("pid", "0")) > 0, f"no audit daemon attached to the kernel: {status}"
    assert guest.ssh("test -s /var/log/audit/audit.log", check=False).returncode == 0
    # Which kinds of event reached the log since boot (for the record, not asserted).
    kinds = guest.ssh(
        "ausearch -ts boot --raw 2>/dev/null | grep -o '^type=[A-Z_0-9]*' | sort | uniq -c"
        " | sort -rn | head -n 25",
        check=False,
    ).stdout
    (logdir / "audit-event-types.txt").write_text(kinds)


def test_shut_down(guest):
    guest.ssh("systemctl poweroff", check=False)
    assert guest.wait_for_exit(60) == 0
