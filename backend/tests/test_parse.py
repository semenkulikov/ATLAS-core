"""Parsers stay boring on broken input and exact on the cases inventory depends on."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from atlas.collectors.parse import (
    fingerprint_authorized_keys,
    is_exposed_address,
    listen_exposure,
    parse_crontab,
    parse_nginx,
    parse_os_release,
    parse_passwd,
    parse_proc_net,
    parse_ss_listeners,
    parse_systemctl_show,
    parse_unit,
    port_from_proxy,
)
from atlas.redact import mask_secrets

TCP = (
    "   0: 00000000:0050 00000000:0000 0A 00000000:00000000 00:00000000 "
    "00000000     0        0 12345 1 0000000000000000 100 0 0 10 0\n"
    "   1: 0100007F:1F40 00000000:0000 0A 00000000:00000000 00:00000000 "
    "00000000  1000        0 99999 1 0000000000000000 100 0 0 10 0\n"
)


def test_ss_names_the_process_when_proc_hides_the_inode() -> None:
    text = (
        'tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=1474660,fd=3))\n'
        'tcp LISTEN 0 511 [::]:80 [::]:* users:(("nginx",pid=1480320,fd=6))\n'
    )
    found = parse_ss_listeners(text)
    assert found[("tcp", "0.0.0.0", 22)] == (1474660, "sshd")
    assert found[("tcp", "::", 80)] == (1480320, "nginx")


def test_proc_net_decodes_listen_addresses() -> None:
    ports = parse_proc_net(TCP, "tcp")
    assert [(item.address, item.port, item.inode) for item in ports] == [
        ("0.0.0.0", 80, "12345"),
        ("127.0.0.1", 8000, "99999"),
    ]
    assert is_exposed_address("0.0.0.0") is True
    assert is_exposed_address("127.0.0.1") is False
    assert is_exposed_address("::1") is False
    assert listen_exposure("127.0.0.53") == "local"
    assert listen_exposure("127.0.1.1") == "local"
    assert listen_exposure("::1") == "local"
    assert listen_exposure("0.0.0.0") == "external"
    assert listen_exposure("::") == "external"
    assert listen_exposure("10.0.0.5") == "lan"


def test_nginx_proxy_and_cron_and_unit_lines() -> None:
    sites = parse_nginx(
        "/etc/nginx/sites-enabled/shop.conf",
        "server {\n    listen 80;\n    server_name shop.example.com;\n"
        "    proxy_pass http://127.0.0.1:8000;\n}\n",
    )
    assert sites[0].names == [(3, "shop.example.com")]
    assert port_from_proxy(sites[0].proxies[0][1]) == 8000
    jobs = parse_crontab(
        "/etc/cron.d/shop", "15 3 * * * deploy /opt/shop/backup.sh\n", has_user_field=True
    )
    assert jobs[0].user == "deploy"
    assert jobs[0].command == "/opt/shop/backup.sh"
    unit = parse_unit("/etc/systemd/system/shop.service", "[Service]\nWorkingDirectory=/opt/shop\n")
    assert unit.working_directory == "/opt/shop"
    assert unit.working_line == 2


def test_sshd_pubkey_fingerprint_is_stable() -> None:
    line = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILbDoBmwevNntyUuDZtjQ1+/kPcnA5Ab6oFUYc4nIkzI deploy@web-1"
    parsed = fingerprint_authorized_keys(line)
    assert len(parsed) == 1
    assert parsed[0][1] == "ssh-ed25519"
    assert parsed[0][2].startswith("SHA256:")
    assert parsed[0][3] == "deploy@web-1"


def test_systemctl_show_splits_units() -> None:
    text = "Id=nginx.service\nActiveState=active\n\nId=shop.service\nActiveState=inactive\n"
    shown = parse_systemctl_show(text)
    assert shown["nginx.service"]["ActiveState"] == "active"
    assert shown["shop.service"]["ActiveState"] == "inactive"


def test_passwd_skips_malformed_lines() -> None:
    users = parse_passwd("root:x:0:0:root:/root:/bin/bash\nbroken\n# comment\n")
    assert [user.name for user in users] == ["root"]


@settings(max_examples=40, deadline=None)
@given(st.text(max_size=2000))
def test_parsers_accept_arbitrary_text(text: str) -> None:
    parse_os_release(text)
    parse_passwd(text)
    parse_crontab("/etc/crontab", text, has_user_field=True)
    parse_nginx("/etc/nginx/x", text)
    parse_proc_net(text, "tcp")
    parse_unit("/x.service", text)
    parse_systemctl_show(text)
    mask_secrets(text)
