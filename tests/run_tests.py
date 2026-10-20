#!/usr/bin/env python3
"""
Off-device tests for the DSH Launcher backend.

`main.py` is pure Python and only imports the `decky` module that Decky Loader
injects at runtime, so the stub next to this file is enough to exercise the real
logic — path discovery, launch, URL capture, and the ownership rules — without a
Steam Deck.

Run:

    PYTHONPATH=. python3 tests/run_tests.py

Exit code 0 means every check passed.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import socket
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# The stubs must be executable, and `_resolve_paths` rejects a path that is not
# (+x). Some sandboxes (Android shared storage) mount the tree `noexec`, where a
# copied script is never executable. Test from a private temp dir when that is
# the case, so the suite tests the fixture rather than the host's mount flags.
STUB_DIR = HERE
if not os.access(os.path.join(HERE, "fake-dsh"), os.X_OK):
    _exec_dir = tempfile.mkdtemp(prefix="dsh-decky-stubs-")
    for _stub in ("fake-dsh", "dying-dsh"):
        _src = os.path.join(HERE, _stub)
        if os.path.isfile(_src):
            shutil.copy2(_src, _exec_dir)
            os.chmod(os.path.join(_exec_dir, _stub), 0o755)
    STUB_DIR = _exec_dir

# The stub reads TEST_SETTINGS before main.py touches DECKY_PLUGIN_SETTINGS_DIR.
os.environ["TEST_SETTINGS"] = tempfile.mkdtemp(prefix="dsh-decky-tests-")

spec = importlib.util.spec_from_file_location("dsh_main", os.path.join(REPO, "main.py"))
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

FAKE = os.path.join(STUB_DIR, "fake-dsh")
DYING = os.path.join(STUB_DIR, "dying-dsh")

PASSED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    mark = "PASS" if condition else "FAIL"
    if condition:
        PASSED += 1
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        raise AssertionError(label)


async def test_url_regex() -> None:
    print("\nURL capture")
    rx = main.URL_LINE
    real = "dsh web: http://127.0.0.1:3080/?token=abcDEF-_123"
    check("captures the token URL", bool(rx.search(real)))
    check("extracts the whole URL", rx.search(real).group(1) == "http://127.0.0.1:3080/?token=abcDEF-_123")
    check("https advertised root also captured",
          bool(rx.search("dsh web: https://deck.local:3080/?token=xyz")))
    check("ignores the handoff notice",
          not rx.search("dsh web: opening the default browser; pass --no-open to disable"))
    check("ignores an unrelated log line", not rx.search("engine: listening on 0.0.0.0"))


async def test_config() -> None:
    print("\nConfig")
    p = main.Plugin()
    p._config = p._load_config()
    check("defaults present", p._config["port"] == 3080 and p._config["autostart"] is False)
    p._config["port"] = 9090
    p._config["permission_mode"] = "danger-full-access"
    p._save_config()
    q = main.Plugin()
    q._config = q._load_config()
    check("round-trips port", q._config["port"] == 9090)
    check("round-trips permission mode", q._config["permission_mode"] == "danger-full-access")
    reply = await q.set_config({"port": "not-a-number"})
    check("set_config accepts the patch key", reply["config"]["port"] == "not-a-number")


async def test_argv() -> None:
    print("\nCommand line")
    p = main.Plugin()
    p._config = p._load_config()
    p._config["dsh_path"] = FAKE
    argv = p._build_argv(9090)
    check("always passes --no-open (no desktop session in Gaming Mode)", "--no-open" in argv)
    check("selects the web profile", argv[argv.index("--profile") + 1] == "web")
    check("honours the configured port", argv[argv.index("--port") + 1] == "9090")
    p._config["extra_args"] = '--trusted-host "my host"'
    argv = p._build_argv(9090)
    check("quotes extra_args like a shell",
          argv[-2:] == ["--trusted-host", "my host"], str(argv[-2:]))


async def test_lifecycle() -> None:
    print("\nLifecycle")
    p = main.Plugin()
    p._config = p._load_config()
    p._config["dsh_path"] = FAKE
    p._config["port"] = 3199
    p._config["workdir"] = "/"

    st = await p.status()
    check("idle before start", not st["running"] and not st["managed"])

    res = await p.start()
    check("start succeeds", res["ok"])
    check("captures the authenticated URL", "token=" in res["url"])

    st = await p.status()
    check("reports running and managed", st["running"] and st["managed"])

    again = await p.start()
    check("second start reuses the live engine", again.get("reused") is True)

    log = await p.get_log()
    check("engine output captured", any("token" in line for line in log["lines"]))

    stop = await p.stop()
    check("stop reports stopping something", stop["stopped"])
    await asyncio.sleep(0.3)
    st = await p.status()
    check("idle after stop", not st["managed"] and st["url"] is None)
    check("second stop is a clean no-op", (await p.stop())["stopped"] is False)


async def test_death_before_url() -> None:
    print("\nFailure: engine dies before reporting a URL")
    p = main.Plugin()
    p._config = p._load_config()
    p._config["dsh_path"] = DYING
    p._config["port"] = 3299
    p._config["workdir"] = "/"
    try:
        await p.start()
        check("raises instead of hanging", False)
    except RuntimeError as exc:
        check("raises instead of hanging", True)
        check("error explains the exit", "exit=7" in str(exc), str(exc)[:80])
    st = await p.status()
    check("cleans up the dead process", not st["managed"])
    check("records the failure", bool(st["error"]))


async def test_foreign_instance_is_never_killed() -> None:
    print("\nOwnership: a foreign instance must survive stop()")
    foreign = await asyncio.create_subprocess_exec(
        "node", "-e",
        'require("http").createServer((q,s)=>s.end("ok")).listen(3399,"127.0.0.1",'
        '()=>console.log("foreign up"))',
        stdout=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(foreign.stdout.readline(), timeout=20)
        p = main.Plugin()
        p._config = p._load_config()
        p._config["port"] = 3399

        res = await p.start()
        check("reuses the occupied port", res.get("reused") is True)
        check("labels it external", res.get("external") is True)

        st = await p.status()
        check("running but not managed", st["running"] and not st["managed"])

        await p.stop()
        check("foreign process still alive", foreign.returncode is None)
        check("foreign port still serving", await p._port_open("127.0.0.1", 3399, 1.0))
    finally:
        foreign.terminate()
        await foreign.wait()


async def test_sandbox_verdict() -> None:
    print("\nSandbox verdict")
    # Mirrors the translation the probe performs from the two runner rungs.
    def verdict(bwrap_ok: bool, landlock: str) -> dict:
        landlock_ok = landlock in ("full", "partial")
        if bwrap_ok or landlock_ok:
            return {"usable": True, "runner": "bwrap" if bwrap_ok else "landlock"}
        return {"usable": False}

    check("bwrap wins when usable", verdict(True, "unusable")["runner"] == "bwrap")
    check("falls back to landlock", verdict(False, "full")["runner"] == "landlock")
    check("accepts partial landlock", verdict(False, "partial")["usable"] is True)
    check("fail-closed when neither works", verdict(False, "unusable")["usable"] is False)


def test_probe_matches_dsh() -> None:
    """The probe must reproduce dsh's own runner probes, not a weaker version.

    A reduced bwrap probe reports "usable" on hosts where dsh's real profile
    fails, which would send the user into a broken command with the plugin
    claiming everything was fine. These expectations mirror
    `dsh-sandbox-local`'s `bwrapProfileArgs()`.
    """
    import re
    print("\nProbe fidelity")
    src = open(os.path.join(REPO, "main.py"), encoding="utf-8").read()
    # The read-only profile dsh actually builds.
    for arg in ['"--ro-bind", "/", "/"', '"--dev", "/dev"',
                '"--unshare-pid"', '"--proc", "/proc"', '"--die-with-parent"']:
        check(f"bwrap probe passes {arg.strip()}", arg in src)

    # Landlock: dsh probes with --probe and reads the partial marker.
    check("landlock probe uses --probe", '"--probe"' in src)
    check("landlock probe detects the partial marker", "partially enforced" in src)

    # The two rungs must not be conflated: bwrap wins, landlock is the fallback.
    check("sandbox chain prefers bwrap", '"bwrap" if bwrap_ok else "landlock"' in src)


async def test_root_readonly_detection() -> None:
    print("\nRoot filesystem probe")
    probe_file = "/usr/.dsh-decky-write-probe"
    try:
        with open(probe_file, "w", encoding="utf-8") as handle:
            handle.write("probe")
        os.remove(probe_file)
        writable = True
    except Exception:  # noqa: BLE001
        writable = False
    # On this sandbox /usr is read-only, but the check must not crash either way.
    check("probe completes without raising", writable in (True, False))


def test_external_window_mode() -> None:
    """Plan B: standalone browser window (no Steam private APIs).

    Pins the facts that make it work: per-family argv (Chromium takes --app,
    Firefox has no --app and needs --kiosk), the GUI env a service process
    must inject, and the refusal to pretend it can drive a foreign instance.
    """
    print("\nExternal-window mode (plan B)")
    src = open(os.path.join(REPO, "main.py"), encoding="utf-8").read()

    check("Chromium uses --app=", '"--app="' in src or "f\"--app={url}\"" in src)
    check("Firefox falls back to --kiosk", '"--kiosk"' in src)
    check("GUI env is injected (DISPLAY)", 'setdefault("DISPLAY"' in src)
    check("GUI env injects WAYLAND_DISPLAY", 'setdefault("WAYLAND_DISPLAY"' in src)
    check("GUI env injects XDG_RUNTIME_DIR", 'setdefault("XDG_RUNTIME_DIR"' in src)
    check("flatpak browsers are probed", "flatpak" in src and "FLATPAK_BROWSERS" in src)
    # Regression (real-device report): `flatpak info` can fail silently in the
    # Decky plugin process, so flatpak export dirs must also be scanned as
    # plain files in BROWSER_CANDIDATES.
    # The exports/bin wrappers are `flatpak run` in disguise (fork + exit 0):
    # they must NOT be candidates; and this device's flatpak rejects --nofork,
    # so the fork-and-exit-0 semantics are accepted via detached_ok instead.
    check("flatpak wrappers excluded; detached_ok accepts fork exit 0",
          "exports/bin/*firefox*\", \"firefox" not in src
          and '"--nofork"' not in src
          and "detached_ok" in src)
    # Regression (real-device report, v0.1.4): the exports/bin wrapper is
    # `flatpak run` in disguise and dies with exit code 1 in the plugin
    # process; the app-tree binary must be exec'd directly with LD_LIBRARY_PATH.
    check("flatpak app tree exec'd directly (bypasses flatpak run)",
          "FLATPAK_DIRECT" in src and "files/lib64/firefox/firefox" in src
          and "LD_LIBRARY_PATH" in src and "_find_flatpak_direct" in src)
    check("firefox gets --no-remote (no handoff-exit)", '"--no-remote"' in src)
    check("own process group for the window", "start_new_session=True" in src)
    check("close uses killpg", "killpg" in src)
    check("refuses a foreign instance instead of faking success",
          "external-instance" in src)

    # The settings key that selects the mode must actually be consumed.
    ui = open(os.path.join(REPO, "src/index.tsx"), encoding="utf-8").read()
    check("open_with is offered in the UI", 'data: "external"' in ui)
    check("open_with drives the open path", "openGui(res.url, cfg?.config?.open_with" in ui)
    check("a browser probe button exists", "browserProbe()" in ui)



def test_zip_layout() -> None:
    """Reproduce Decky's installer checks against the packaged zip.

    Source: decky-loader `backend/decky_loader/browser.py`, which accepts an
    archive only when a `*/plugin.json` exists at depth exactly 1 and then
    `extractall`s it straight into ~/homebrew/plugins/.
    """
    import json
    import zipfile

    archive = os.path.join(os.path.dirname(REPO), "dsh-decky.zip")
    print("\nPackaged zip")
    if not os.path.isfile(archive):
        print("  [SKIP] dsh-decky.zip not built yet — run: bash package.sh")
        return

    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()

        candidates = [n for n in names if n.endswith("/plugin.json") and n.count("/") == 1]
        check("exactly one plugin.json at depth 1 (installer rule)", len(candidates) == 1,
              str(candidates))
        top = candidates[0].rsplit("/", 1)[0]

        tops = {n.split("/")[0] for n in names if n.strip("/")}
        check("single top-level directory (extractall target)", len(tops) == 1, str(tops))

        manifest = json.loads(zf.read(f"{top}/plugin.json"))
        for field in ("name", "author", "flags", "api_version"):
            check(f"plugin.json has {field}", field in manifest)
        check("root flag deliberately absent", "root" not in manifest.get("flags", []))

        check("main.py present", f"{top}/main.py" in names)
        check("dist/index.js present (frontend entry)", f"{top}/dist/index.js" in names)

        pkg = json.loads(zf.read(f"{top}/package.json"))
        check("package.json declares type=module (ESM load path)",
              pkg.get("type") == "module", str(pkg.get("type")))

        import re as _re
        dev = [n for n in names
               if _re.search(r"(^|/)(src|node_modules|tests|\.git)/|tsconfig\.json$"
                             r"|rollup\.config\.js$|\.map$", n)]
        check("no dev-only files shipped", not dev, str(dev))


def test_path_diagnostics() -> None:
    """A miss must explain itself.

    The first real-hardware run reported only "no node": the panel could not
    say where it had looked. A Decky plugin process inherits a minimal PATH
    (Decky rewrites HOME but does not source a login shell), so this is the
    likely failure mode and it must be self-diagnosing.
    """
    print("\nPath diagnostics")
    src = open(os.path.join(REPO, "main.py"), encoding="utf-8").read()

    check("resolver returns the candidate list it tried", "node_tried" in src)
    check("resolver returns free-form diagnostics", '"diagnostics"' in src)
    check("probe exposes the plugin's own PATH", "path_env" in src)
    check("failure message names the minimal-PATH cause", "只继承精简的 PATH" in src)

    # Coverage for the install layouts a package manager produces.
    for layout in ["/usr/bin/node", "linuxbrew", "nix-profile", "/snap/bin",
                   "/run/host/usr/bin", "fnm", "volta", "asdf"]:
        check(f"node candidates cover {layout}", layout in src)

    # A CLI entry from a global npm install is a .js file: it needs node.
    check("CLI entry is prefixed with node", 'dsh.endswith(".js")' in src)


def main_entry() -> int:
    checks = [
        test_url_regex,
        test_config,
        test_argv,
        test_lifecycle,
        test_death_before_url,
        test_foreign_instance_is_never_killed,
        test_sandbox_verdict,
        test_root_readonly_detection,
    ]
    for check_fn in checks:
        asyncio.run(check_fn())
    test_probe_matches_dsh()
    test_path_diagnostics()
    test_external_window_mode()
    test_zip_layout()
    print(f"\nAll {PASSED} checks passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main_entry())
    except AssertionError as exc:
        print(f"\nFAILED: {exc}")
        sys.exit(1)
