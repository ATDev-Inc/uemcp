"""Wire protocol tests against a fake editor over real sockets. No Unreal needed."""

import json
import socket
import threading

import pytest

from uemcp.remote_exec import (
    PROTOCOL_MAGIC,
    PROTOCOL_VERSION,
    TYPE_COMMAND,
    TYPE_COMMAND_RESULT,
    CommandChannel,
    RemoteExecutionClient,
    RemoteExecutionConfig,
    RemoteExecutionError,
    UnrealInstance,
    make_message,
    parse_message,
)


def test_message_roundtrip():
    raw = make_message(TYPE_COMMAND, "node-a", dest="node-b", data={"command": "x"})
    message = parse_message(raw)
    assert message is not None
    assert message["version"] == PROTOCOL_VERSION
    assert message["magic"] == PROTOCOL_MAGIC
    assert message["source"] == "node-a"
    assert message["dest"] == "node-b"
    assert message["data"] == {"command": "x"}


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b'"a string"',
        b'{"version": 99, "magic": "ue_py", "source": "x", "type": "ping"}',
        b'{"version": 1, "magic": "wrong", "source": "x", "type": "ping"}',
        b'{"version": 1, "magic": "ue_py", "type": "ping"}',
    ],
)
def test_parse_message_rejects_garbage(payload):
    assert parse_message(payload) is None


def _fake_editor(sock: socket.socket, response_chunks: list[bytes]):
    """Read one command, then reply in the given chunks (to exercise framing)."""
    buffer = b""
    while True:
        chunk = sock.recv(65536)
        buffer += chunk
        try:
            message = json.loads(buffer.decode("utf-8"))
            break
        except json.JSONDecodeError:
            continue
    assert message["type"] == TYPE_COMMAND
    for piece in response_chunks:
        sock.sendall(piece)


def _run_channel_against(response_chunks: list[bytes]):
    client_sock, editor_sock = socket.socketpair()
    thread = threading.Thread(
        target=_fake_editor, args=(editor_sock, response_chunks), daemon=True
    )
    thread.start()
    channel = CommandChannel(client_sock, "client-node", "editor-node")
    try:
        return channel.run_command("print('hi')", timeout=5.0)
    finally:
        channel.close()
        editor_sock.close()
        thread.join(timeout=2)


def _result_message(**data) -> bytes:
    return make_message(TYPE_COMMAND_RESULT, "editor-node", dest="client-node", data=data)


def test_command_result_single_send():
    output = [{"type": "Info", "output": "hi"}]
    payload = _result_message(success=True, result="None", output=output)
    result = _run_channel_against([payload])
    assert result.success is True
    assert result.output_text() == "hi"


def test_command_result_split_across_tcp_segments():
    big_output = [{"type": "Info", "output": f"line {i}"} for i in range(200)]
    payload = _result_message(success=True, result="None", output=big_output)
    midpoint = len(payload) // 2
    result = _run_channel_against([payload[:midpoint], payload[midpoint:]])
    assert result.success is True
    assert "line 199" in result.output_text()


def test_command_failure_propagates():
    payload = _result_message(success=False, result="SyntaxError", output=[])
    result = _run_channel_against([payload])
    assert result.success is False
    assert result.result == "SyntaxError"


def test_closed_connection_raises():
    client_sock, editor_sock = socket.socketpair()
    editor_sock.close()
    channel = CommandChannel(client_sock, "client-node", "editor-node")
    with pytest.raises(RemoteExecutionError):
        channel.run_command("print('hi')", timeout=2.0)
    channel.close()


def test_discover_with_retries_stops_on_first_hit(monkeypatch):
    client = RemoteExecutionClient(RemoteExecutionConfig(discovery_attempts=3))
    found = UnrealInstance(node_id="n1", project_name="Demo")
    calls = {"n": 0}

    def fake_discover():
        calls["n"] += 1
        return [found] if calls["n"] >= 2 else []  # miss once, then hit

    monkeypatch.setattr(client, "discover", fake_discover)
    assert client.discover_with_retries() == [found]
    assert calls["n"] == 2  # stopped as soon as an editor answered


def test_discover_with_retries_exhausts_attempts(monkeypatch):
    client = RemoteExecutionClient(RemoteExecutionConfig(discovery_attempts=3))
    calls = {"n": 0}

    def fake_discover():
        calls["n"] += 1
        return []

    monkeypatch.setattr(client, "discover", fake_discover)
    assert client.discover_with_retries() == []
    assert calls["n"] == 3  # tried the full budget before giving up


def test_discovery_attempts_from_env(monkeypatch):
    monkeypatch.setenv("UEMCP_DISCOVERY_ATTEMPTS", "5")
    assert RemoteExecutionConfig.from_env().discovery_attempts == 5


def test_discovery_attempts_bad_env_keeps_default(monkeypatch):
    monkeypatch.setenv("UEMCP_DISCOVERY_ATTEMPTS", "notanumber")
    assert RemoteExecutionConfig.from_env().discovery_attempts == 3
