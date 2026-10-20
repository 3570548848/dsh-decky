# DSH Launcher

**Run the DSH web agent inside Steam Gaming Mode — without switching to Desktop Mode.**

[![Decky](https://img.shields.io/badge/Decky-Loader-1a9fff)](https://github.com/SteamDeckHomebrew/decky-loader)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

English | [简体中文](README.md)

![Two ways to open the GUI](docs/ab-demo.gif)

---

## What this is

[DeepSeek Harness (`dsh`)](https://github.com/deepseek-ai/DeepSeek-Harness) is a capable agent
runtime, but you drive it through a browser UI. In **Gaming Mode** on a SteamOS handheld there is
no desktop session — no browser to open, and dsh's default `xdg-open` hand-off has nothing to talk
to.

This plugin closes exactly that gap: **start dsh in Gaming Mode and get its UI in front of you.**

- Start/stop the engine from the Quick Access Menu (QAM)
- Environment probe: shows where Node/dsh are and whether the sandbox works
- Two ways to open the GUI, switchable in settings
- Stops are explicit — a plugin reload will not kill your session

> **Is this a DSH plugin?** No. It is a **Decky Loader** plugin — two different plugin ecosystems.
> Also note the **`dsh` engine itself needs no port**: it is plain JavaScript with no `os`/`cpu`
> restrictions, and its Linux x64/arm64 prebuilds are already on npm. A SteamOS system is missing
> only a **launcher/adaptation layer**, which is what this is.

## Two ways to open the GUI

Both are **top-level navigations**, so both satisfy dsh's `SameSite=Strict` cookie requirement.

| | Mode A · Steam's browser (default) | Mode B · External browser window |
|---|---|---|
| How | `Navigation.NavigateToExternalWeb(url)` into Steam's own browser | Plugin launches a real browser: Chromium `--app=<url>`, Firefox `--kiosk <url>` |
| Shape | Opens in Steam's browser | Chrome-less window **overlaid on Gaming Mode** |
| Depends on | Steam private APIs (`CreateBrowserView`, …) | **No Steam private API at all** |
| Update-proof | Weaker (a Steam upgrade can break it) | **Stronger** (standard browser) |
| Requires | Steam's browser available | A browser on the device (incl. flatpak) |

Mode B discovers a browser automatically: native paths (`/usr/bin`, Homebrew, nix, snap) → flatpak.
The panel has a **"Detect browser"** button so you can see which one it will use.

> **Why not an `<iframe>`?**
> dsh's session cookie is `HttpOnly; SameSite=Strict` and bound to the exact authority. An iframe is
> same-site cross-origin, so it arrives **without the cookie** and the UI never loads.

## Install

### 1. Get Node.js and dsh onto the device

> The root filesystem is usually read-only (an overlay may make `/` look writable while `/usr` stays
> unwritable and reverts on reboot). **Install under `$HOME`.**

```sh
# Install nvm — do NOT hardcode a version; ask for the latest tag
NVM_VER=$(curl -s https://api.github.com/repos/nvm-sh/nvm/releases/latest \
  | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4)
curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VER/install.sh" | bash

# Close and reopen the terminal (so nvm's environment loads), then:
nvm install --lts && nvm use --lts
node -v

npm i -g @deepseek-ai/dsh
dsh --version
```

If `raw.githubusercontent.com` is unreachable, install via git:
```sh
git clone --depth 1 https://github.com/nvm-sh/nvm.git ~/.nvm && cd ~/.nvm && ./install.sh
```

> ⚠️ **Record `which node`** (e.g. `/home/deck/.nvm/versions/node/v24.x.x/bin/node`).
> A Decky plugin is a service process that **inherits only a minimal PATH and cannot see an nvm
> from your login shell**. If the probe reports no Node, put that path into the plugin's Advanced
> settings.

### 2. Install the plugin

```sh
curl -L -o dsh-decky.zip \
  https://github.com/3570548848/dsh-decky/releases/download/v0.1.2/dsh-decky.zip
```

- **Decky UI**: Settings → Developer → Install plugin from zip → reload the loader
- **Manually**: `unzip dsh-decky.zip -d ~/homebrew/plugins/`

> Use **v0.1.2 explicitly**, not `/releases/latest`: `latest` currently resolves to v0.1.1 (no Mode
> B) because v0.1.2 is marked prerelease and therefore skipped.

The archive must contain **exactly one top-level directory** (`dsh-decky/plugin.json`) — a hard
requirement of Decky's installer, which does `extractall` straight into `~/homebrew/plugins/`.
`package.sh` guarantees it and the test suite checks it.

### 3. First run

1. QAM → **DSH Launcher**
2. Press **Environment probe** and read three things:
   - **Node.js / dsh** — resolved paths; if "not found", set them in Advanced settings
   - **bwrap / Landlock** — if both are unusable, set the permission preset to `danger-full-access`
     (and understand what that means), or install `bubblewrap`
   - **Is `/` read-only** — tells you where to install
3. Press **Start and open DSH**. A first cold boot takes ~1–3 minutes; engine output is visible
   under Advanced → View engine output.

## Security

- **No `root` flag.** The plugin runs the engine as the normal user. Decky can run a backend as
  root, but that leaves root-owned files in your home directory — third-party plugins should use
  the least privilege that works.
- **No credentials read or stored.** The plugin never opens `~/.dsh` secrets; the launch token is
  simply parsed from the engine's stdout and handed to the browser.
- **`danger-full-access` is a documented escape hatch**, not a default. It removes file confinement
  for every command the agent runs; enable it only when no sandbox runner is usable.

## Version history

### v0.1.15 — the engine environment is no longer shadowed by PyInstaller

**Symptom**: the dsh engine boots and the GUI opens, but config **sync** fails —

```
reading the remote snapshot failed: git clone https://github.com/<user>/<repo>.git failed (exit 128)
… /_MEI0000054cWWSwqE/libssl.so.3: version `OPENSSL_3.5.0' not found
   (required by /usr/lib/libcurl.so.4) …
fatal: remote helper 'https' aborted session
```

**Cause**: SteamOS ships `/usr/bin/flatpak` as a PyInstaller one-file binary; it unpacks its bundled (older) OpenSSL into `$TMPDIR/_MEIxxxxxx/`. The Decky service process's `LD_LIBRARY_PATH` points into such a directory, so **every child process** (node, git, git-remote-https) resolves libssl from there and aborts on the version check. v0.1.6 already fixed exactly this trap — but only for the **browser** spawn (`_gui_env`); the **engine** spawn (`_build_env`) still copied `os.environ` verbatim. The engine lived, and the git underneath it died.

**Fix**: sanitising moved to the outermost boundary, `_sanitize_inherited_env()`, used by both spawn paths. It is both narrower and more thorough than v0.1.6:

- inside `LD_LIBRARY_PATH` / `LD_PRELOAD` it removes **only** entries pointing at `_MEI…` and directories that no longer exist — a value you set deliberately survives (v0.1.6 dropped the whole variable);
- if nothing is left, the variable is **removed** rather than left empty (an empty entry means "current directory" to the loader);
- `TMPDIR` is replaced with `/tmp` only when it is a `_MEI` dir, unwritable, or missing.

**If you are stuck right now**: upgrade the plugin and restart the engine (the plugin changes the launch environment; it cannot take effect without a restart). As a manual stopgap:

```bash
env -u LD_LIBRARY_PATH TMPDIR=/tmp <your usual dsh command> --profile web --no-open --port 3080
```

or switch the config manager's sync transport from **Git** to **Gist / WebDAV** — those go through Node's HTTPS and never spawn `git`, sidestepping the dynamic loader entirely.

## Known limits

- **The UI is not rendered inside the Decky panel** (neither mode embeds it) — `SameSite=Strict`
  rules out iframes. This follows from dsh's auth model.
- **Mode B is not yet verified on hardware**: `--app`/`--kiosk` launching, GUI environment
  injection, and whether the window actually appears in Gaming Mode have not been run on a device.
- **Cold boot is slow**: the first run resolves a large dependency graph; the timeout is 180 s.
- **Port reuse cannot recover the token**: if the port is already served by *another* dsh instance,
  the plugin cannot obtain its launch token (it is random and in-memory only), so a browser cannot
  authenticate. **Change the port** (e.g. to 3081) to get around it.
- **Gamepad input** inside Steam's browser is managed by Steam; this plugin adds no bindings or
  virtual keyboard.
- Engine-side end-to-end (executing commands under Gaming Mode, long sessions, resume from suspend)
  is **still not fully verified**.

## Design notes and evidence

Everything below was read from real package sources, not recalled. Sources:
`@deepseek-ai/dsh` 0.2.1-rc.2, `@decky/ui` 4.15.1, `@decky/api` 1.1.3, the official
`decky-plugin-template`, and [jessebofill/DeckWebBrowser](https://github.com/jessebofill/DeckWebBrowser).

<details>
<summary><b>Verified facts and evidence (click to expand)</b></summary>

| Fact | Consequence | Evidence |
|---|---|---|
| `@deepseek-ai/dsh` declares no `os`/`cpu`; deps include `node-addon-system-linux-x64` | No kernel port needed | `0.2.1-rc.2` npm metadata |
| `dsh web` prints `dsh web: <url>` to stdout | The launch token appears only there | `dsh-web-app/lib/index.js:162` |
| Auth via `?token=`, then an `HttpOnly; SameSite=Strict` cookie **bound to the authority** | The UI **must** be a top-level navigation; an iframe gets no cookie | `dsh-client-connection/lib/index.js:348` |
| Browser hand-off uses `open` → `xdg-open`; `--no-open` skips it | Gaming Mode has no desktop session, so **always `--no-open`** | `dsh-web-app/lib/index.js:156-169` |
| Linux sandbox chain `bwrap` → `landlock`; if both fail it **fails closed** | A healthy-looking handheld may refuse every command | `dsh-sandbox-local`: `PLATFORM_CHAINS.linux` |
| `danger-full-access` bypasses `ctx.sandbox` entirely | Escape hatch when no runner exists | `dsh-bash-sandbox/lib/index.js:68` |
| On Linux node-pty uses `forkpty()` (`spawn-helper` is macOS-only) | No extra shim needed on Linux | `node-pty/src/unix/pty.cc:393` |
| `koffi` loads lazily on the Win32 path only | No FFI build off-Windows | `dsh-win32-process/lib/index.js:25` |
| Decky `flags` may include `root` → backend runs as root | **Deliberately unused here** | `decky.pyi` 29/37 |

</details>

<details>
<summary><b>Launch and open internals (click to expand)</b></summary>

**Launch.** The backend spawns `dsh --profile web --no-open --port <N>` in its **own process group**,
drains stdout and resolves the tokenised URL. It then **waits for the port to actually accept a
connection** before handing the URL on — the printed line precedes the bind, so acting on it alone
would race.

**Open.** See the two modes above. Mode B discovery order is native paths → flatpak (probe with
`flatpak info`, run with `flatpak run`), and it **injects the GUI environment explicitly**
(`DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`) — a plugin is a service process and usually does
not inherit them, so without this the browser fails to start or stays invisible.

**Survive.** `_unload` deliberately does **not** stop the engine. A plugin reload, or Steam resuming
from suspend, must not kill an in-flight agent session. Stopping is an explicit user action.

**Never overreach.** When the port is already served by another instance, the plugin reports it as
an **external** instance, marks `managed: false`, and **`stop()` will not kill it** — covered by a
test.

</details>

## Development

```sh
pnpm install
pnpm run build      # build src/index.tsx → dist/index.js
bash package.sh     # package in the Decky-required layout → ../dsh-decky.zip
PYTHONPATH=tests python3 tests/run_tests.py    # 80 offline checks, no handheld needed
```

The backend is pure Python and only needs a stubbed `decky` module, so its **logic is testable off
device**.

Covered: URL capture, repeated starts, URL-line filtering ("opening the default browser" is
correctly **excluded**), config round-trip, `--no-open` always present, `extra_args` argv handling,
clean failure when the process dies before reporting a URL, `stop()` never killing a foreign
instance, the zip's Decky layout rules, and Mode B's launch arguments and GUI environment injection.

**Real defects found by these tests** (not by eyeballing):

1. **Deadlock** — `start()` called `stop()`, re-entering a non-reentrant `asyncio.Lock`
2. **Misleading exit code** — the stdout pump reported `exit=None`, because EOF arrives before the
   process is reaped
3. **1.4 MB sourcemap** — `@decky/rollup` resolves option conflicts in favour of its defaults, so
   the returned config must be mutated rather than passed options
4. **Attribute shadowing a method** — `self._browser_argv` hid the method of the same name, raising
   `NoneType not callable`
5. **Dead config** — `open_with` was declared but never read by the backend, advertising an option
   that did not exist

## Files

| Path | Role |
|---|---|
| `plugin.json` | Decky manifest (no `root` flag) |
| `main.py` | Backend: discovery, launch, URL capture, probe, settings, external window |
| `src/index.tsx` | QAM panel UI |
| `dist/index.js` | Built bundle (committed) |
| `tests/run_tests.py` | 80 offline checks |
| `package.sh` | Packages in the Decky-required layout |
| `docs/ab-demo.gif` | Demo of the two ways to open the GUI |

## License

MIT. Not affiliated with Valve, Decky, or DeepSeek.
