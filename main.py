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
import subprocess
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

# Browsers usable for the "external window" mode, as (path, family) pairs.
# `family` decides the argv: Chromium-family takes `--app=<url>` for a
# standalone window; Firefox-family has no --app and needs `--kiosk <url>`.
BROWSER_CANDIDATES = [
    ("/usr/bin/chromium", "chromium"),
    ("/usr/bin/chromium-browser", "chromium"),
    ("/usr/bin/google-chrome-stable", "chromium"),
    ("/usr/bin/google-chrome", "chromium"),
    ("/usr/bin/microsoft-edge-stable", "chromium"),
    ("/usr/bin/brave-browser", "chromium"),
    ("/usr/bin/vivaldi-stable", "chromium"),
    ("/home/linuxbrew/.linuxbrew/bin/chromium", "chromium"),
    ("~/.local/bin/chromium", "chromium"),
    ("/nix/var/nix/profiles/default/bin/chromium", "chromium"),
    ("/snap/bin/chromium", "chromium"),
    ("/usr/bin/firefox", "firefox"),
    ("/usr/bin/librewolf", "firefox"),
    ("/usr/bin/firefox-esr", "firefox"),
    # Flatpak export dirs: a browser installed with `flatpak install` lands
    # here, never in /usr/bin. Checking the filesystem directly beats the
    # `flatpak info` round-trip, which can fail silently in a Decky plugin
    # process (minimal PATH, no session bus) — the root cause of "installed
    # but not detected" reports. Globs are expanded by _expand().
    ("/var/lib/flatpak/exports/bin/*firefox*", "firefox"),
    ("/var/lib/flatpak/exports/bin/*chrom*", "chromium"),
    ("/var/lib/flatpak/exports/bin/*librewolf*", "firefox"),
    ("~/.local/share/flatpak/exports/bin/*firefox*", "firefox"),
    ("~/.local/share/flatpak/exports/bin/*chrom*", "chromium"),
    ("~/.local/share/flatpak/exports/bin/*librewolf*", "firefox"),
    ("~/.local/bin/firefox", "firefox"),
]

# Flatpak app ids, tried when no native browser was found. SteamOS ships
# flatpak and many users install a browser that way.
FLATPAK_BROWSERS = [
    ("org.chromium.Chromium", "chromium"),
    ("com.google.Chrome", "chromium"),
    ("org.mozilla.firefox", "firefox"),
    ("io.gitlab.librewolf-community", "firefox"),
]

# Where a Node.js may land on a SteamOS-class system. Ordered by likelihood:
# a distro/Homebrew install beats a per-user version manager, because the
# Decky plugin process inherits only a minimal service PATH.
NODE_CANDIDATES = [
    # distro packages (ostree/overlay images) and /usr/local installs
    "/usr/bin/node",
    "/usr/local/bin/node",
    "/bin/node",
    # Homebrew on Linux — the usual "package manager" answer on Bazzite/SteamOS
    "/home/linuxbrew/.linuxbrew/bin/node",
    "~/.linuxbrew/bin/node",
    # nix
    "~/.nix-profile/bin/node",
    "/nix/var/nix/profiles/default/bin/node",
    # snap
    "/snap/bin/node",
    # distrobox exposes the host filesystem here, not the other way round
    "/run/host/usr/bin/node",
    # per-user version managers
    "~/.local/bin/node",
    "~/bin/node",
    "~/.nvm/versions/node/*/bin/node",
    "~/.local/share/nvm/versions/node/*/bin/node",
    "~/.local/share/fnm/node-versions/*/installation/bin/node",
    "~/.volta/bin/node",
    "~/.asdf/shims/node",
]

# dsh entry points. A global npm install usually has no `dsh` on PATH at all,
# so the CLI entry (lib/bin.js) is resolved per Node prefix instead.
DSH_CANDIDATES = [
    "/usr/bin/dsh",
    "/usr/local/bin/dsh",
    "/home/linuxbrew/.linuxbrew/bin/dsh",
    "~/.linuxbrew/bin/dsh",
    "~/.local/bin/dsh",
    "~/bin/dsh",
    "/snap/bin/dsh",
    "/run/host/usr/bin/dsh",
    "~/.dsh/bin/dsh",
]

# npm global prefixes to look for the CLI entry under, per Node install root.
NODE_GLOBAL_PREFIXES = [
    "/usr/lib/node_modules/@deepseek-ai/dsh",
    "/usr/local/lib/node_modules/@deepseek-ai/dsh",
    "/home/linuxbrew/.linuxbrew/lib/node_modules/@deepseek-ai/dsh",
    "~/.linuxbrew/lib/node_modules/@deepseek-ai/dsh",
    "~/.local/lib/node_modules/@deepseek-ai/dsh",
    "~/.nvm/versions/node/*/lib/node_modules/@deepseek-ai/dsh",
    "~/.local/share/nvm/versions/node/*/lib/node_modules/@deepseek-ai/dsh",
    "~/.local/share/fnm/node-versions/*/installation/lib/node_modules/@deepseek-ai/dsh",
    "~/.volta/tools/image/packages/@deepseek-ai/dsh/lib/node_modules/@deepseek-ai/dsh",
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
        # Plan B: the browser window this plugin opened, so it can be closed.
        self._browser_proc: Optional[asyncio.subprocess.Process] = None
        self._browser_argv: Optional[List[str]] = None

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
        """Locate node and dsh.

        Returns the resolved pair plus the *diagnostics* needed to explain a
        miss. A Decky plugin runs from a service process that inherits only a
        minimal PATH (Decky rewrites HOME but does not source a login shell),
        so "node is not found" is common and previously opaque — the panel
        could only say "no node" without saying where it had looked.
        """
        diag: List[str] = []
        tried: List[Dict[str, str]] = []

        node = self._config.get("node_path") or ""
        node_src = None
        if node and os.access(os.path.expanduser(node), os.X_OK):
            node = os.path.expanduser(node)
            node_src = "configured"
        else:
            if node:
                diag.append(f"配置的 node 路径不可执行：{node}")
            node = None

        if node is None:
            found = shutil.which("node")
            if found:
                node, node_src = found, "PATH"

        if node is None:
            for candidate in NODE_CANDIDATES:
                found = self._expand(candidate)
                tried.append({"path": candidate, "found": found or ""})
                if found:
                    node, node_src = found, "well-known"
                    break

        dsh = None
        source = "configured"
        configured = self._config.get("dsh_path") or ""
        if configured:
            candidate = self._expand(configured)
            if candidate:
                dsh = candidate
            else:
                diag.append(f"配置的 dsh 路径不可执行：{configured}")

        if dsh is None:
            found = shutil.which("dsh")
            if found:
                dsh, source = found, "PATH"

        if dsh is None:
            for candidate in DSH_CANDIDATES:
                found = self._expand(candidate)
                if found:
                    dsh, source = found, "well-known"
                    break

        # A global npm install often exposes no `dsh` on PATH; resolve the CLI
        # entry under a known npm prefix instead. The entry is a JavaScript
        # file, so `_build_argv` must prefix it with the node we found.
        if dsh is None:
            import glob as _glob

            for prefix in NODE_GLOBAL_PREFIXES:
                expanded = os.path.expanduser(prefix)
                matches = sorted(_glob.glob(expanded)) if "*" in expanded else (
                    [expanded] if os.path.isdir(expanded) else []
                )
                for base in matches:
                    entry = os.path.join(base, "lib", "bin.js")
                    if os.path.isfile(entry):
                        dsh, source = entry, "npm-global"
                        diag.append(f"找到 npm 全局 CLI 入口：{entry}")
                        break
                if source == "npm-global":
                    break

        if dsh is None:
            source = "missing"

        return {
            "node": node,
            "dsh": dsh,
            "source": source,
            "node_source": node_src,
            "diagnostics": diag,
            "node_tried": tried,
        }

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
        node = resolved.get("node")
        dsh = resolved.get("dsh")

        if dsh and dsh.endswith(".js"):
            # npm-global resolution yields the CLI *entry*, which needs an
            # interpreter. Without node we cannot run it.
            if not node:
                raise RuntimeError(
                    "找到了 dsh 的 CLI 入口，但没有可用的 Node.js 来解释它：" + dsh
                    + "。请在高级设置里手动填写 Node 路径。"
                )
            argv = [node, dsh]
        elif dsh:
            # A real executable: it either carries a shebang or is a wrapper.
            argv = [dsh]
        else:
            missing = resolved.get("diagnostics") or []
            detail = ("\n" + "\n".join(missing)) if missing else ""
            if node:
                raise RuntimeError(
                    "找到了 Node（" + node + "），但找不到 dsh 命令。请先安装：\n"
                    "  npm i -g @deepseek-ai/dsh\n"
                    "或在高级设置里填写 dsh 路径。" + detail
                )
            raise RuntimeError(
                "找不到 Node.js，也找不到 dsh。Decky 插件进程只继承精简的 PATH，"
                "不会加载你登录 shell 的环境——即使桌面模式里能跑 node，这里也可能看不到。\n"
                "请先确认 Node 装在哪（发行版包通常是 /usr/bin/node，Homebrew 是 "
                "/home/linuxbrew/.linuxbrew/bin/node），然后在高级设置里手动填写路径。"
                + detail
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
    # External-window mode (plan B)
    # ------------------------------------------------------------------

    def _find_browser(self) -> Optional[Dict[str, str]]:
        """Locate a browser for standalone-window mode.

        Returns ``{"argv": [...], "label": ...}`` where argv is the command
        prefix (without the URL), or None when nothing usable was found.
        """
        for candidate, family in BROWSER_CANDIDATES:
            found = self._expand(candidate)
            if found:
                return {"argv": [found], "family": family, "label": found}
        # Flatpak fallback: `flatpak run <app-id>` exists only if flatpak does.
        flatpak = shutil.which("flatpak")
        if flatpak:
            for app_id, family in FLATPAK_BROWSERS:
                probe = subprocess.run(  # noqa: S603 - fixed argv, no shell
                    [flatpak, "info", app_id],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                )
                if probe.returncode == 0:
                    return {"argv": [flatpak, "run", app_id], "family": family, "label": f"flatpak:{app_id}"}
        return None

    def _browser_command(self, browser: Dict[str, str], url: str) -> List[str]:
        """Build the argv that opens `url` in a standalone window."""
        if browser.get("family") == "firefox":
            # Firefox has no --app; --kiosk gives a chrome-less fullscreen window.
            return [*browser["argv"], "--kiosk", url]
        # Chromium family: --app=<url> is the documented standalone-window form.
        return [*browser["argv"], f"--app={url}", "--start-maximized"]

    @staticmethod
    def _gui_env() -> Dict[str, str]:
        """Environment for a GUI process launched from a service context.

        A Decky plugin runs as a service process. On a SteamOS-class system the
        display variables may not be inherited, and without them the browser
        starts headless-invisible or dies. Fill in the conventional Gaming Mode
        values when they are absent.
        """
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        # Gamescope exposes this in Gaming Mode; setting it is harmless when
        # there is no gamescope and helpful when there is.
        env.setdefault("WAYLAND_DISPLAY", "gamescope-0")
        return env

    async def open_external(self) -> Dict[str, Any]:
        """Open the running engine's URL in a standalone browser window.

        Plan B: rather than routing into Steam's built-in CEF, start a real
        browser with a chrome-less window. That keeps the plugin off Steam's
        private APIs. The window is a normal top-level navigation, so the
        engine's `SameSite=Strict` cookie still works.
        """
        url = self.url
        if not url:
            port = int(self._config.get("port") or DEFAULT_PORT)
            if await self._port_open(DEFAULT_HOST, port):
                return {
                    "ok": False,
                    "reason": "external-instance",
                    "advice": (
                        "当前端口上运行的是插件之外启动的引擎，插件拿不到它的启动令牌，"
                        "外部浏览器也无法完成鉴权。请改用插件自己启动引擎（换一个端口，"
                        "例如 3081），或先停掉那个实例。"
                    ),
                }
            return {"ok": False, "reason": "not-running", "advice": "引擎尚未运行，请先点「启动并打开 DSH」。"}

        browser = self._find_browser()
        if browser is None:
            return {
                "ok": False,
                "reason": "no-browser",
                "advice": (
                    "没有找到可用的浏览器。请安装一个（Chromium/Chrome/Firefox，"
                    "或 flatpak 版），或先用「内置浏览器」方式打开。"
                ),
            }

        argv = self._browser_command(browser, url)
        decky.logger.info("opening external window: %s", " ".join(argv))
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                env=self._gui_env(),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            return {"ok": False, "reason": "spawn-failed", "advice": f"无法执行 {argv[0]}：{exc}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": "spawn-failed", "advice": str(exc)}

        # Keep the handle so a later close can reach it, but do not block on it:
        # the browser runs for as long as the user keeps the window open.
        self._browser_proc = proc
        self._browser_argv = argv  # recorded for logging/close
        return {"ok": True, "argv": argv, "browser": browser.get("label")}

    async def browser_probe(self) -> Dict[str, Any]:
        """Report which browser would be used, for the settings panel."""
        browser = self._find_browser()
        if browser is None:
            return {
                "found": False,
                "candidates": [c for c, _ in BROWSER_CANDIDATES],
                "flatpak": shutil.which("flatpak") is not None,
            }
        return {
            "found": True,
            "label": browser.get("label"),
            "family": browser.get("family"),
            "argv": browser.get("argv"),
        }

    async def close_external(self) -> Dict[str, Any]:
        """Terminate the browser window this plugin opened, if any."""
        proc = getattr(self, "_browser_proc", None)
        if proc is None or proc.returncode is not None:
            self._browser_proc = None
            return {"ok": True, "closed": False}
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
        self._browser_proc = None
        return {"ok": True, "closed": True}

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
            "node": {
                "path": node,
                "source": resolved.get("node_source"),
                "tried": resolved.get("node_tried"),
            },
            "dsh": {"path": resolved.get("dsh"), "source": resolved.get("source")},
            "diagnostics": resolved.get("diagnostics") or [],
            "path_env": os.environ.get("PATH", ""),
            "cwd": os.getcwd(),
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
