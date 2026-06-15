"""Client for Unreal Engine's built-in Python remote execution protocol.

Unreal's "Python Editor Script Plugin" ships with a remote execution feature:
the editor joins a UDP multicast group and answers discovery pings, then
connects back to a TCP command endpoint that the client hosts. Commands and
results are single JSON objects.

This module is a small, dependency-free implementation of that protocol, so
UEMCP can talk to a completely vanilla editor. Nothing has to be installed or
compiled inside Unreal.
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import dataclass, field

PROTOCOL_VERSION = 1
PROTOCOL_MAGIC = "ue_py"

TYPE_PING = "ping"
TYPE_PONG = "pong"
TYPE_OPEN_CONNECTION = "open_connection"
TYPE_CLOSE_CONNECTION = "close_connection"
TYPE_COMMAND = "command"
TYPE_COMMAND_RESULT = "command_result"

MODE_EXEC_FILE = "ExecuteFile"
MODE_EXEC_STATEMENT = "ExecuteStatement"
MODE_EVAL_STATEMENT = "EvaluateStatement"

_RECV_BUFFER = 65536


class RemoteExecutionError(RuntimeError):
    """Raised when the editor cannot be reached or a command fails to transport."""


@dataclass
class RemoteExecutionConfig:
    multicast_group: str = "239.0.0.1"
    multicast_port: int = 6766
    multicast_bind: str = "0.0.0.0"
    multicast_ttl: int = 0
    command_host: str = "127.0.0.1"
    command_port: int = 0  # 0 means let the OS pick a free port
    discovery_timeout: float = 2.0
    discovery_attempts: int = 3  # discovery is one UDP round-trip; retry before giving up
    command_timeout: float = 120.0
    project_name: str | None = None  # prefer this project when several editors run

    @classmethod
    def from_env(cls) -> RemoteExecutionConfig:
        cfg = cls()
        cfg.multicast_group = os.environ.get("UEMCP_MULTICAST_GROUP", cfg.multicast_group)
        cfg.multicast_port = int(os.environ.get("UEMCP_MULTICAST_PORT", cfg.multicast_port))
        cfg.multicast_bind = os.environ.get("UEMCP_MULTICAST_BIND", cfg.multicast_bind)
        cfg.command_host = os.environ.get("UEMCP_COMMAND_HOST", cfg.command_host)
        cfg.command_port = int(os.environ.get("UEMCP_COMMAND_PORT", cfg.command_port))
        cfg.discovery_timeout = float(
            os.environ.get("UEMCP_DISCOVERY_TIMEOUT", cfg.discovery_timeout)
        )
        try:
            cfg.discovery_attempts = int(
                os.environ.get("UEMCP_DISCOVERY_ATTEMPTS", cfg.discovery_attempts)
            )
        except ValueError:
            pass  # keep the default on a malformed value instead of crashing startup
        cfg.command_timeout = float(os.environ.get("UEMCP_COMMAND_TIMEOUT", cfg.command_timeout))
        cfg.project_name = os.environ.get("UEMCP_PROJECT", cfg.project_name)
        return cfg


@dataclass
class UnrealInstance:
    node_id: str
    engine_version: str = ""
    project_name: str = ""
    project_root: str = ""
    machine: str = ""
    user: str = ""

    @classmethod
    def from_pong(cls, message: dict) -> UnrealInstance:
        data = message.get("data") or {}
        return cls(
            node_id=message["source"],
            engine_version=data.get("engine_version", ""),
            project_name=data.get("project_name", ""),
            project_root=data.get("project_root", ""),
            machine=data.get("machine", ""),
            user=data.get("user", ""),
        )


@dataclass
class CommandResult:
    success: bool
    result: str = ""
    output: list[dict] = field(default_factory=list)

    def output_text(self) -> str:
        return "\n".join(entry.get("output", "").rstrip("\n") for entry in self.output)


def make_message(
    msg_type: str, source: str, dest: str | None = None, data: dict | None = None
) -> bytes:
    message: dict = {
        "version": PROTOCOL_VERSION,
        "magic": PROTOCOL_MAGIC,
        "source": source,
        "type": msg_type,
    }
    if dest is not None:
        message["dest"] = dest
    if data is not None:
        message["data"] = data
    return json.dumps(message).encode("utf-8")


def parse_message(payload: bytes) -> dict | None:
    """Decode a protocol message, returning None for anything malformed or foreign."""
    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(message, dict):
        return None
    if message.get("version") != PROTOCOL_VERSION or message.get("magic") != PROTOCOL_MAGIC:
        return None
    if "source" not in message or "type" not in message:
        return None
    return message


class CommandChannel:
    """The TCP side of the protocol: one JSON command out, one JSON result back."""

    def __init__(self, sock: socket.socket, node_id: str, remote_node_id: str):
        self._sock = sock
        self._node_id = node_id
        self._remote_node_id = remote_node_id

    def run_command(
        self,
        command: str,
        exec_mode: str = MODE_EXEC_FILE,
        unattended: bool = True,
        timeout: float = 120.0,
    ) -> CommandResult:
        payload = make_message(
            TYPE_COMMAND,
            self._node_id,
            dest=self._remote_node_id,
            data={"command": command, "unattended": unattended, "exec_mode": exec_mode},
        )
        try:
            self._sock.sendall(payload)
        except OSError as exc:
            raise RemoteExecutionError(f"Could not send command to Unreal: {exc}") from exc
        message = self._receive(timeout)
        data = message.get("data") or {}
        return CommandResult(
            success=bool(data.get("success")),
            result=str(data.get("result", "")),
            output=list(data.get("output") or []),
        )

    def _receive(self, timeout: float) -> dict:
        """Accumulate bytes until a full command_result JSON object parses."""
        self._sock.settimeout(timeout)
        buffer = b""
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() > deadline:
                raise RemoteExecutionError("Timed out waiting for a result from Unreal")
            try:
                chunk = self._sock.recv(_RECV_BUFFER)
            except TimeoutError as exc:
                raise RemoteExecutionError("Timed out waiting for a result from Unreal") from exc
            except OSError as exc:
                raise RemoteExecutionError(f"Command connection failed: {exc}") from exc
            if not chunk:
                raise RemoteExecutionError("Unreal closed the command connection")
            buffer += chunk
            try:
                message = json.loads(buffer.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue  # partial message, keep reading
            if message.get("type") == TYPE_COMMAND_RESULT:
                return message
            buffer = b""  # unrelated message, discard and keep waiting

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()


class RemoteExecutionClient:
    """Discovers running editors over multicast and runs Python in one of them."""

    def __init__(self, config: RemoteExecutionConfig | None = None):
        self.config = config or RemoteExecutionConfig()
        self.node_id = str(uuid.uuid4())
        self._channel: CommandChannel | None = None
        self._instance: UnrealInstance | None = None

    @property
    def is_connected(self) -> bool:
        return self._channel is not None

    @property
    def instance(self) -> UnrealInstance | None:
        return self._instance

    def _open_multicast_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        sock.bind((self.config.multicast_bind, self.config.multicast_port))
        membership = socket.inet_aton(self.config.multicast_group) + socket.inet_aton(
            self.config.multicast_bind
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.config.multicast_ttl)
        return sock

    def discover(self, timeout: float | None = None) -> list[UnrealInstance]:
        """Ping the multicast group and collect every editor that answers."""
        timeout = timeout if timeout is not None else self.config.discovery_timeout
        group = (self.config.multicast_group, self.config.multicast_port)
        sock = self._open_multicast_socket()
        instances: dict[str, UnrealInstance] = {}
        try:
            sock.sendto(make_message(TYPE_PING, self.node_id), group)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    payload, _addr = sock.recvfrom(_RECV_BUFFER)
                except TimeoutError:
                    break
                message = parse_message(payload)
                if message is None or message["type"] != TYPE_PONG:
                    continue
                if message.get("dest") not in (None, self.node_id):
                    continue
                instance = UnrealInstance.from_pong(message)
                instances[instance.node_id] = instance
        finally:
            sock.close()
        return list(instances.values())

    def discover_with_retries(self) -> list[UnrealInstance]:
        """Discovery is a single UDP round-trip that can be dropped (loopback-only
        setups, busy networks, VPN adapters). Retry a few times before giving up."""
        instances: list[UnrealInstance] = []
        for _ in range(max(1, self.config.discovery_attempts)):
            instances = self.discover()
            if instances:
                break
        return instances

    def connect(self, node_id: str | None = None) -> UnrealInstance:
        """Open a command channel to one editor, discovering it first if needed."""
        self.close()
        instances = self.discover_with_retries()
        if not instances:
            raise RemoteExecutionError(
                "No Unreal Editor instances found on the network. Make sure the editor is "
                "running, the 'Python Editor Script Plugin' is enabled, and 'Enable Remote "
                "Execution' is checked under Project Settings > Plugins > Python."
            )
        target = self._pick_instance(instances, node_id)

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.config.command_host, self.config.command_port))
        listener.listen(1)
        host, port = listener.getsockname()[:2]

        group = (self.config.multicast_group, self.config.multicast_port)
        mcast = self._open_multicast_socket()
        try:
            mcast.sendto(
                make_message(
                    TYPE_OPEN_CONNECTION,
                    self.node_id,
                    dest=target.node_id,
                    data={"command_ip": host, "command_port": port},
                ),
                group,
            )
            listener.settimeout(self.config.discovery_timeout + 3.0)
            try:
                conn, _addr = listener.accept()
            except TimeoutError as exc:
                raise RemoteExecutionError(
                    f"Unreal ({target.project_name or target.node_id}) did not connect back "
                    "to the command endpoint. Check firewall rules for the editor process."
                ) from exc
        finally:
            mcast.close()
            listener.close()

        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._channel = CommandChannel(conn, self.node_id, target.node_id)
        self._instance = target
        return target

    def _pick_instance(
        self, instances: list[UnrealInstance], node_id: str | None
    ) -> UnrealInstance:
        if node_id:
            for instance in instances:
                if instance.node_id == node_id:
                    return instance
            raise RemoteExecutionError(f"No Unreal instance with node id {node_id}")
        if self.config.project_name:
            for instance in instances:
                if instance.project_name.lower() == self.config.project_name.lower():
                    return instance
            names = ", ".join(i.project_name or i.node_id for i in instances)
            raise RemoteExecutionError(
                f"No Unreal instance for project '{self.config.project_name}'. Found: {names}"
            )
        return instances[0]

    def run_command(
        self,
        command: str,
        exec_mode: str = MODE_EXEC_FILE,
        unattended: bool = True,
        timeout: float | None = None,
    ) -> CommandResult:
        if self._channel is None:
            raise RemoteExecutionError("Not connected to an Unreal Editor instance")
        timeout = timeout if timeout is not None else self.config.command_timeout
        return self._channel.run_command(command, exec_mode, unattended, timeout)

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        self._instance = None
