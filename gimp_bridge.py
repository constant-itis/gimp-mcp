"""
gimp_bridge — thin client for GIMP's built-in Script-Fu TCP server.

Wire protocol (confirmed against GIMP 2.10.30):
  Request:  b'G' + uint16_be(len) + scheme_command_utf8
  Response: b'G' + err_byte + uint16_be(len) + body_utf8
            err_byte: 0 = success, 1 = scheme/PDB error

The Script-Fu server executes any Scheme expression against GIMP's full PDB,
so this one transport reaches every filter, layer op, and file exporter GIMP has.
Zero third-party deps — stdlib socket/struct only.
"""

import socket
import struct
import threading

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10008
MAGIC = b"G"


class GimpError(RuntimeError):
    """Raised when the Script-Fu server reports an evaluation error."""


class GimpBridge:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=60):
        self.host = host
        self.port = port
        self.timeout = timeout
        # GIMP's Script-Fu server is single-threaded. Serialize eval so two concurrent
        # callers never open competing connections (which the server would queue/refuse
        # and could interleave on the wire). Note: this makes each eval atomic, not a
        # whole multi-eval tool sequence — MCP requests are processed serially anyway.
        self._lock = threading.Lock()

    def eval(self, command: str) -> str:
        """Send one Scheme expression, return its printed result.

        Raises GimpError on a server-reported evaluation error,
        ConnectionError if the server isn't reachable.
        """
        payload = command.encode("utf-8")
        if len(payload) > 0xFFFF:
            raise ValueError("command too long for Script-Fu protocol (>65535 bytes)")
        try:
            with self._lock, socket.create_connection((self.host, self.port), self.timeout) as s:
                s.settimeout(self.timeout)
                s.sendall(MAGIC + struct.pack(">H", len(payload)) + payload)
                hdr = self._recv_exact(s, 4)
                if hdr[:1] != MAGIC:
                    raise GimpError(f"bad response magic: {hdr[:1]!r}")
                err = hdr[1]
                length = struct.unpack(">H", hdr[2:4])[0]
                body = self._recv_exact(s, length).decode("utf-8", "replace")
        except (ConnectionRefusedError, OSError) as e:
            raise ConnectionError(
                f"cannot reach GIMP Script-Fu server at {self.host}:{self.port} "
                f"({e}). Start it with start-gimp-server.sh."
            ) from e
        if err:
            raise GimpError(body.strip())
        return body

    @staticmethod
    def _recv_exact(s, n):
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("connection closed mid-response")
            buf += chunk
        return buf

    def ping(self) -> bool:
        try:
            self.eval("(car (gimp-version))")
            return True
        except (ConnectionError, GimpError):
            return False


if __name__ == "__main__":
    import sys
    b = GimpBridge()
    expr = sys.argv[1] if len(sys.argv) > 1 else "(gimp-version)"
    print(b.eval(expr))
