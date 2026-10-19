"""
DSH Launcher — Decky Loader backend.

Starts the DeepSeek Harness (dsh) Web profile as a background process and hands
its authenticated URL to the frontend, so Gaming Mode can show the DSH GUI in
Steam's own built-in browser without switching to Desktop Mode.

Design constraints this file respects (verified against @deepseek-ai/dsh
0.2.1-rc.2 on the host, see README "Verified facts"):

* SteamOS/Bazzite-class systems ship a read-only (atomic) root filesystem, so
  Node.js normally lives under $HOME. The node executable is therefore
  discovered, never assumed.
* Gaming Mode has no desktop session, so ``xdg-open`` fails. dsh is always
  started with ``--no-open`` and the URL is captured from stdout, where the
  web-app glue prints ``dsh web: <authenticated-url>``.
* dsh authenticates the browser with a launch token in the query string and
  then mints an ``HttpOnly; SameSite=Strict`` cookie bound to that authority.
  Load-bearing consequence: the GUI must be opened as a top-level navigation
  in a real browser context (Steam's built-in browser), never inside an
  ``<iframe>`` — a same-site cross-origin frame would not carry the cookie.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import socket
import time
from typing import Any, Dict, List, Optional

import decky

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DEFAULT_PORT = 3080
DEFAULT_HOST = "127.0.0.1"

# ``dsh web: http://127.0.0.1:3080/?token=...`` — the only URL that carries the
# launch token. The web-app plugin prints exactly one such line per boot.
URL_LINE = re.compile(r"dsh web:\s*(https?://\S+)")

# Wall-clock budget for a cold boot: dependency resolution can be slow on a
# handheld, but a hung boot must not leave the panel spinning forever.
STARTUP_TIMEOUT_S = 180.0

# Where a userspace Node.js typically lands on an immutable-root distro.
NODE_CANDIDATES = [
    "~/.local/bin/node",
    "~/bin/node",
    "~/.nvm/versions/node/*/bin/node",
    "~/.local/share/nvm/versions/node/*/bin/node",
    "~/.local/share/fnm/node-versions/*/installation/bin/node",
    "/usr/local/bin/node",
    "/usr/bin/node",
]

# dsh entry points, in preference order.
DSH_CANDIDATES = [
    "~/.local/bin/dsh",
    "~/bin/dsh",
    "/usr/local/bin/dsh",
    "/usr/bin/dsh",
    "~/.dsh/bin/dsh",
]


class Plugin:
    """Decky plugin lifecycle object. Public methods are callable from the UI."""

    def __init__(self) -> None:
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.url: Optional[str] = None
        self.exit_code: Optional[int] = None
        self.last_error: Optional[str] = None
        self.started_at: Optional[float] = None
        self.log_lines: List[str] = []
        self._reader_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._config: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _main(self) -> None:
        self._config = self._load_config()
        self.exit_code = None
        if self._config.get("autostart"):
            decky.logger.info("autostart enabled; launching dsh")
            try:
                await self.start()
            except Exception as exc:  # noqa: BLE001 - never block plugin load
                decky.logger.error("autostart failed: %s", exc)

    async def _unload(self) -> None:
        # Deliberately does NOT stop the engine: a plugin reload (or Steam
        # resuming from suspend) must not kill an in-progress agent session.
        # Use the "Stop" button, or uninstall, to actually stop it.
        decky.logger.info("unloaded; dsh left running (use Stop to terminate)")

    async def _uninstall(self) -> None:
        await self.stop()

    async def _migration(self) -> None:
        decky.logger.info("migrating")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def _config_path(self) -> str:
        return os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "config.json")

    def _load_config(self) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {
            "node_path": "",
            "dsh_path": "",
            "port": DEFAULT_PORT,
            "workdir": "",
            "permission_mode": "",
            "extra_args": "",
            "autostart": False,
            "open_with": "external",
        }
        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                defaults.update(stored)
        except FileNotFoundError:
            pass
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("unreadable config, using defaults: %s", exc)
        return defaults

    def _save_config(self) -> None:
        os.makedirs(decky.DECKY_PLUGIN_SETTINGS_DIR, exist_ok=True)
        tmp = self._config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self._config, handle, indent=2, ensure_ascii=False)
        os.replace(tmp, self._config_path)

    async def get_config(self) -> Dict[str, Any]:
        """Current settings, plus the paths discovery actually resolved."""
        resolved = self._resolve_paths()
        return {
            "config": dict(self._config),
            "resolved": {
                "node": resolved.get("node"),
                "dsh": resolved.get("dsh"),
                "source": resolved.get("source"),
            },
            "home": decky.DECKY_USER_HOME,
        }

    async def set_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Merge a partial config. Applies on the next start."""
        allowed = {
            "node_path",
            "dsh_path",
            "port",
            "workdir",
            "permission_mode",
            "extra_args",
            "autostart",
            "open_with",
        }
        for key, value in (patch or {}).items():
            if key in allowed and value is not None:
                self._config[key] = value
        self._save_config()
        return await self.get_config()

    # ------------------------------------------------------------------
    # Path discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _expand(candidate: str) -> Optional[str]:
        """Expand ~ and globs, returning the first existing match."""
        import glob as _glob

        expanded = os.path.expanduser(candidate)
        if "*" in expanded:
            matches = sorted(_glob.glob(expanded))
            for match in matches:
                if os.access(match, os.X_OK):
                    return match
            return None
        return expanded if os.path.isfile(expanded) and os.access(expanded, os.X_OK) else None

    def _resolve_paths(self) -> Dict[str, Optional[str]]:
        node = self._config.get("node_path") or ""
        if node and os.access(os.path.expanduser(node), os.X_OK):
            node = os.path.expanduser(node)
        else:
            node = None

        if node is None:
            found = shutil.which("node")
            if found:
                node = found
        if node is None:
            for candidate in NODE_CANDIDATES:
                found = self._expand(candidate)
                if found:
                    node = found
                    break

        dsh = None
        configured = self._config.get("dsh_path") or ""
        if configured:
            candidate = self._expand(configured)
            if candidate:
                dsh = candidate
        source = "configured"
        if dsh is None:
            found = shutil.which("dsh")
            if found:
                dsh = found
                source = "PATH"
        if dsh is None:
            for candidate in DSH_CANDIDATES:
                found = self._expand(candidate)
                if found:
                    dsh = found
                    source = "well-known"
                    break
        if dsh is None:
            source = "missing"
        return {"node": node, "dsh": dsh, "source": source}

    # ------------------------------------------------------------------
    # Start / stop / status
    # ------------------------------------------------------------------

    async def _port_open(self, host: str, port: int, timeout: float = 0.4) -> bool:
        try:
            fut = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            del reader
            return True
        except Exception:  # noqa: BLE001
            return False

    def _build_argv(self, port: int) -> List[str]:
        """Assemble the dsh command line. Always --no-open (no desktop session)."""
        resolved = self._resolve_paths()
        argv: List[str] = []
        dsh = resolved.get("dsh")
        if dsh:
            argv = [dsh]
        else:
            node = resolved.get("node")
            if not node:
                raise RuntimeError(
                    "找不到 Node.js。SteamOS 根文件系统只读，请把 Node 装到 $HOME "
                    "(例如 nvm/fnm 或官方预编译包解到 ~/.local)，然后在设置里指定 node 路径。"
                )
            # Run the CLI entry directly from a global install.
            for guess in (
                "~/.local/lib/node_modules/@deepseek-ai/dsh/lib/bin.js",
                "/usr/lib/node_modules/@deepseek-ai/dsh/lib/bin.js",
                "/usr/local/lib/node_modules/@deepseek-ai/dsh/lib/bin.js",
            ):
                expanded = os.path.expanduser(guess)
                if os.path.isfile(expanded):
                    argv = [node, expanded]
                    break
            if not argv:
                raise RuntimeError(
                    "找不到 dsh 命令。请先安装 @deepseek-ai/dsh（npm i -g @deepseek-ai/dsh），"
                    "或在设置里填写 dsh 可执行文件路径。"
                )

        argv += ["--profile", "web", "--no-open", "--port", str(port)]
        extra = (self._config.get("extra_args") or "").strip()
        if extra:
            import shlex

            argv += shlex.split(extra)
        return argv

    def _build_env(self, resolved: Dict[str, Optional[str]]) -> Dict[str, str]:
        env = dict(os.environ)
        node = resolved.get("node")
        if node:
            # The engine resolves helper binaries from PATH; put the discovered
            # node first so subprocesses agree with the process that launched it.
            env["PATH"] = os.path.dirname(node) + os.pathsep + env.get("PATH", "")
        mode = (self._config.get("permission_mode") or "").strip()
        if mode:
            env["DSH_PERMISSION_MODE"] = mode
        return env

    async def start(self) -> Dict[str, Any]:
        """Boot dsh and return its authenticated URL. Idempotent."""
        async with self._lock:
            port = int(self._config.get("port") or DEFAULT_PORT)

            # Already booted by this plugin and still alive: reuse it.
            if self.proc is not None and self.proc.returncode is None and self.url:
                return {"ok": True, "url": self.url, "reused": True, "port": port}

            # Someone else (a systemd unit, a manual run) already serves this
            # port. Reusing it is right, but we cannot know its launch token;
            # an already-authenticated browser cookie is the only path in.
            if await self._port_open(DEFAULT_HOST, port):
                self.url = f"http://{DEFAULT_HOST}:{port}/"
                return {
                    "ok": True,
                    "url": self.url,
                    "reused": True,
                    "external": True,
                    "port": port,
                    "note": "端口已被另一个 dsh 实例占用；若浏览器未认证过，请在该实例启动后重新捕获 URL。",
                }

            resolved = self._resolve_paths()
            argv = self._build_argv(port)
            env = self._build_env(resolved)
            cwd = self._config.get("workdir") or decky.DECKY_USER_HOME
            cwd = os.path.expanduser(cwd)
            if not os.path.isdir(cwd):
                cwd = decky.DECKY_USER_HOME

            self.log_lines = []
            self.last_error = None
            self.url = None
            self.exit_code = None
            decky.logger.info("starting: %s (cwd=%s)", " ".join(argv), cwd)

            try:
                self.proc = await asyncio.create_subprocess_exec(
                    *argv,
                    cwd=cwd,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    # Own process group so stop() can take the whole tree with it.
                    start_new_session=True,
                )
            except FileNotFoundError as exc:
                self.last_error = f"无法执行 {argv[0]}：{exc}"
                raise RuntimeError(self.last_error) from exc

            self.started_at = time.time()
            url_future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._reader_task = asyncio.create_task(self._pump_output(url_future))

            # Wait for the URL line, the process dying, or the deadline.
            try:
                await asyncio.wait_for(url_future, timeout=STARTUP_TIMEOUT_S)
            except asyncio.TimeoutError:
                await self._stop_locked()
                self.last_error = f"启动超时（{int(STARTUP_TIMEOUT_S)}s）。最后输出：" + self._tail()
                raise RuntimeError(self.last_error)
            except RuntimeError as exc:
                await self._stop_locked()
                self.last_error = str(exc)
                raise

            # Confirm the listener actually accepts connections before handing
            # the URL to the browser: the printed line precedes the bind race.
            deadline = time.time() + 15.0
            while time.time() < deadline:
                if await self._port_open(DEFAULT_HOST, port):
                    break
                if self.proc.returncode is not None:
                    await self._stop_locked()
                    self.last_error = "引擎在监听前退出。输出：" + self._tail()
                    raise RuntimeError(self.last_error)
                await asyncio.sleep(0.25)

            decky.logger.info("dsh ready on port %d", port)
            return {"ok": True, "url": self.url, "reused": False, "port": port}

    async def _pump_output(self, url_future: asyncio.Future) -> None:
        """Drain stdout, capturing the token URL and keeping a bounded log tail."""
        assert self.proc is not None and self.proc.stdout is not None
        stream = self.proc.stdout
        try:
            while True:
                raw = await stream.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", errors="replace").rstrip("\n")
                if text:
                    self.log_lines.append(text)
                    # Bounded tail: enough to diagnose, never enough to grow.
                    if len(self.log_lines) > 400:
                        del self.log_lines[:200]
                    decky.logger.info("[dsh] %s", text)
                match = URL_LINE.search(text)
                if match and not url_future.done():
                    self.url = match.group(1)
                    url_future.set_result(self.url)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("output pump failed: %s", exc)
        finally:
            if self.proc is not None and not url_future.done():
                # stdout reaching EOF does not imply the process has been reaped
                # yet: `returncode` is still None at this point, so report the
                # real exit status rather than a misleading `exit=None`.
                code = self.proc.returncode
                if code is None:
                    try:
                        await asyncio.wait_for(self.proc.wait(), timeout=5.0)
                        code = self.proc.returncode
                    except (asyncio.TimeoutError, ProcessLookupError):
                        pass
                detail = "unknown" if code is None else str(code)
                url_future.set_exception(
                    RuntimeError(f"引擎在报告 URL 前退出（exit={detail}）。输出：{self._tail()}")
                )

    def _tail(self, lines: int = 25) -> str:
        return "\n".join(self.log_lines[-lines:]) or "(无输出)"

    async def stop(self) -> Dict[str, Any]:
        """Terminate the engine and its whole process group."""
        async with self._lock:
            return await self._stop_locked()

    async def _stop_locked(self) -> Dict[str, Any]:
        """stop() body; assumes ``self._lock`` is already held.

        ``start()`` must call this rather than ``stop()``: the lock is not
        reentrant, so re-acquiring it from inside the start critical section
        would deadlock the plugin against itself.
        """
        proc = self.proc
        if proc is None or proc.returncode is not None:
            self.proc = None
            self.url = None
            return {"ok": True, "stopped": False}

        decky.logger.info("stopping dsh (pid=%s)", proc.pid)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("SIGTERM failed: %s", exc)

        try:
            await asyncio.wait_for(proc.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            decky.logger.warning("graceful stop timed out; SIGKILL")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

        self.exit_code = proc.returncode
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
        self.proc = None
        self.url = None
        return {"ok": True, "stopped": True}

    async def status(self) -> Dict[str, Any]:
        """Is the engine up, and where is it reachable?"""
        port = int(self._config.get("port") or DEFAULT_PORT)
        mine_alive = self.proc is not None and self.proc.returncode is None
        port_open = await self._port_open(DEFAULT_HOST, port)
        resolved = self._resolve_paths()
        return {
            "running": mine_alive or port_open,
            "managed": mine_alive,
            "url": self.url if mine_alive else (f"http://{DEFAULT_HOST}:{port}/" if port_open else None),
            "port": port,
            "pid": self.proc.pid if mine_alive else None,
            "uptime_s": int(time.time() - self.started_at) if mine_alive and self.started_at else None,
            "exit_code": self.exit_code,
            "error": self.last_error,
            "resolved": {"node": resolved.get("node"), "dsh": resolved.get("dsh"), "source": resolved.get("source")},
        }

    async def get_log(self) -> Dict[str, Any]:
        """Bounded engine output tail for the settings panel."""
        return {"lines": self.log_lines[-120:]}

    # ------------------------------------------------------------------
    # Environment probes
    # ------------------------------------------------------------------

    async def probe(self) -> Dict[str, Any]:
        """Best-effort environment report.

        Every check is independent and non-fatal; a missing tool reads as
        ``None`` rather than blocking. This exists because a SteamOS-class
        system can look healthy while the sandbox refuses to run anything:
        dsh's Linux chain is ``bwrap`` then Landlock, and if neither is usable
        the command executor fails closed (it does not silently run
        unconfined).
        """
        resolved = self._resolve_paths()

        async def run(argv: List[str], timeout: float = 8.0) -> Dict[str, Any]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            except FileNotFoundError:
                return {"ok": False, "reason": "not found"}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "reason": str(exc)}
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                text = out.decode("utf-8", errors="replace").strip()
                return {"ok": proc.returncode == 0, "code": proc.returncode, "out": text[-600:]}
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
                return {"ok": False, "reason": "timeout"}

        node = resolved.get("node")
        report: Dict[str, Any] = {
            "node": {"path": node},
            "dsh": {"path": resolved.get("dsh"), "source": resolved.get("source")},
            "root_readonly": None,
            "bwrap": None,
            "landlock": None,
        }

        node_version = await run([node, "--version"]) if node else {"ok": False, "reason": "no node"}
        report["node"]["version"] = node_version.get("out") or node_version.get("reason")

        # Is / writable? The single most useful fact for "where do I install".
        # Read the mount table rather than only attempting a write: a write
        # failure cannot distinguish "read-only filesystem" (SteamOS) from
        # "not permitted as this user", and the two have different fixes.
        def root_is_readonly() -> Optional[bool]:
            try:
                with open("/proc/mounts", "r", encoding="utf-8") as handle:
                    for line in handle:
                        parts = line.split()
                        if len(parts) >= 4 and parts[1] == "/":
                            return "ro" in parts[3].split(",")
            except Exception:  # noqa: BLE001
                pass
            # Fallback: a direct write probe.
            probe_file = "/usr/.dsh-decky-write-probe"
            try:
                with open(probe_file, "w", encoding="utf-8") as handle:
                    handle.write("probe")
                os.remove(probe_file)
                return False
            except Exception:  # noqa: BLE001
                return True

        report["root_readonly"] = await asyncio.to_thread(root_is_readonly)

        # bwrap: dsh's first-choice Linux runner. The real question is not
        # "does the binary exist" but "does it enforce a profile", so probe it
        # EXACTLY as dsh does.
        #
        # These arguments mirror `bwrapProfileArgs()` in dsh-sandbox-local,
        # which builds the read-only profile as:
        #   --ro-bind / / --dev /dev --unshare-pid --proc /proc
        #   --die-with-parent -- true
        # A reduced probe (e.g. only `--ro-bind / / -- true`) would report
        # "usable" on hosts where `--unshare-pid` or `--proc` cannot work, and
        # the user would then hit a real failure inside dsh instead. Keep this
        # list in sync with that function.
        BWRAP_PROFILE_ARGS = [
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--unshare-pid",
            "--proc", "/proc",
            "--die-with-parent",
        ]
        bwrap = shutil.which("bwrap") or shutil.which("bubblewrap")
        if bwrap:
            result = await run([bwrap, *BWRAP_PROFILE_ARGS, "--", "true"])
            report["bwrap"] = {
                "path": bwrap,
                "usable": result.get("ok", False),
                "argv": ["bwrap", *BWRAP_PROFILE_ARGS, "--", "true"],
                "detail": result,
            }
        else:
            report["bwrap"] = {"path": None, "usable": False, "reason": "binary not on PATH"}

        # Landlock: dsh's second rung, shipped as a prebuilt launcher inside the
        # dsh install. Probe it exactly as dsh-sandbox-local does.
        launcher = None
        for base in (
            "~/.local/lib/node_modules/@deepseek-ai/dsh",
            "/usr/lib/node_modules/@deepseek-ai/dsh",
            "/usr/local/lib/node_modules/@deepseek-ai/dsh",
            os.path.expanduser(decky.DECKY_USER_HOME) + "/.dsh",
        ):
            candidate = os.path.join(
                os.path.expanduser(base),
                "node_modules/@deepseek-ai/node-addon-system-linux-x64/bin/landlock-run",
            )
            if os.path.isfile(candidate):
                launcher = candidate
                break
        if launcher:
            result = await run([launcher, "--probe"])
            out = result.get("out", "")
            verdict = "unusable"
            if result.get("code") == 0:
                verdict = "partial" if "partially enforced" in out else "full"
            report["landlock"] = {"path": launcher, "usable": verdict, "detail": result}
        else:
            report["landlock"] = {"path": None, "usable": "unusable", "reason": "launcher not found"}

        # Translate the two rungs into the consequence the user actually cares
        # about, so the panel can explain a "command refused" error.
        bwrap_ok = bool(report["bwrap"] and report["bwrap"].get("usable"))
        landlock = report["landlock"].get("usable") if report["landlock"] else "unusable"
        landlock_ok = landlock in ("full", "partial")
        if bwrap_ok or landlock_ok:
            report["sandbox_verdict"] = {
                "usable": True,
                "runner": "bwrap" if bwrap_ok else "landlock",
                "enforcement": "full" if bwrap_ok else landlock,
            }
        else:
            report["sandbox_verdict"] = {
                "usable": False,
                "advice": (
                    "bwrap 与 Landlock 都不可用：workspace-write/read-only 档位的命令会被 fail-closed 拒绝执行。"
                    "在设置里把 DSH_PERMISSION_MODE 设为 danger-full-access 可绕过沙箱"
                    "（该档位下 dsh-bash-sandbox 直接以非受限方式执行），或安装 bubblewrap。"
                ),
            }
        return report
