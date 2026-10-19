# DSH Launcher — a Decky Loader plugin for SteamOS-class handhelds

English | [简体中文](README.md)

Run the **DeepSeek Harness (`dsh`)** web agent inside **Steam Gaming Mode** and open its GUI in
Steam's own built-in browser — no trip to Desktop Mode, no `xdg-open`.

Companion question answered: *"can you make a dsh plugin for SteamOS?"* — The `dsh` engine itself
needs **no port**; it is plain JavaScript with no `os`/`cpu` restrictions and its Linux x64/arm64
prebuilds all publish to npm. What SteamOS actually needs is a **launcher/adaptation layer**, which
is what this plugin is. (A *DSH* plugin and a *Decky* plugin are two different plugin ecosystems:
this repo is a **Decky** plugin.)

---

## Verified facts

Everything below was read out of the real packages, not recalled. Sources: `@deepseek-ai/dsh`
0.2.1-rc.2, `@decky/ui` 4.15.1, `@decky/api` 1.1.3, the official `decky-plugin-template`, and
[jessebofill/DeckWebBrowser](https://github.com/jessebofill/DeckWebBrowser).

| Fact | Consequence | Evidence |
|---|---|---|
| `@deepseek-ai/dsh` declares no `os`/`cpu`; deps include `@deepseek-ai/node-addon-system-linux-x64` | **No DSH kernel port needed.** Linux x64 is a supported target | npm metadata for `0.2.1-rc.2` |
| `dsh web` prints `dsh web: <authenticated-url>` to stdout | That one line is the only place the launch token appears; parse it | `dsh-web-app/lib/index.js:162` |
| `dsh` authenticates via `?token=`, then sets `HttpOnly; SameSite=Strict` cookie **bound to the authority** | The GUI **must** be a top-level navigation in a real browsing context. An `<iframe>` would be same-site-cross-origin and arrive **unauthenticated** | `dsh-client-connection/lib/index.js:348` (`sessionCookie`) |
| `dsh web` hand-off uses the `open` package → `xdg-open`; with `--no-open` it is skipped | Gaming Mode has no desktop session, so **always start with `--no-open`** and open the URL yourself | `dsh-web-app/lib/index.js:156-169` |
| Linux sandbox chain is `bwrap` → `landlock`; if **both** probes fail the run **fails closed** (`SANDBOX_UNAVAILABLE`), it does not silently run unconfined | A healthy-looking Deck can still refuse every command. Probe both, and explain the fix | `dsh-sandbox-local`: `PLATFORM_CHAINS.linux = ["bwrap","landlock"]` |
| `danger-full-access` **bypasses `ctx.sandbox` entirely** (`super.execute`, `denied: false`) | The escape hatch when no sandbox runner exists on the machine | `dsh-bash-sandbox/lib/index.js:68`; its README line 173 |
| node-pty on Linux uses `forkpty()`; `spawn-helper` is `#if defined(__APPLE__)` only | PTY needs **no** extra shim on Linux; `prebuilds/linux-x64/pty.node` ships | `node-pty/src/unix/pty.cc:393` |
| `koffi` (FFI) is reached through `createLazyRequire` on the Win32 path only | Non-Windows never loads it; no FFI build needed | `dsh-win32-process/lib/index.js:25` |
| Decky `plugin.json` `flags` may include `root`, which runs the **backend as root** | **This plugin deliberately does not use it** — see Security below | `decky.pyi` lines 29/37 |

## Design, and why

**Launch.** The backend spawns `dsh --profile web --no-open --port <N>` in its **own process group**,
drains stdout, and resolves the printed token URL. It then waits for the port to actually accept a
connection before handing the URL onward — the printed line precedes the bind, so opening on the
line alone would race.

**Open.** The frontend calls `Navigation.NavigateToExternalWeb(url)` (`@decky/ui`), which routes the
URL into Steam's built-in browser. The `SameSite=Strict` cookie is exactly why this is the only
working route: it must be a top-level navigation, not a frame.

**Survive.** `_unload` deliberately does **not** stop the engine. A plugin reload, or Steam resuming
from suspend, must not kill an in-flight agent session. Stopping is an explicit user action.

**Never overreach.** If the port is already serving (a systemd unit, a manual run), the plugin
reports it as an **external** instance, marks `managed: false`, and **`stop()` will not kill it** —
verified by test.

## Security

- **No `root` flag.** The plugin runs the engine as the normal user and touches nothing privileged.
  Running the agent as root would mean root-owned files quietly appearing in your home directory,
  and Decky plugins are third-party code — the least privilege that works is the right choice.
- **No credentials read or stored.** The plugin never opens `~/.dsh` secrets; the launch token is
  parsed from the engine's own stdout and passed straight to Steam's browser.
- `danger-full-access` is offered as a **documented escape hatch**, not a default. It disables file
  confinement for every command the agent runs. Enable it only if the environment probe says both
  sandbox runners are unusable and you accept unconfined execution.

## Install

### 1. Get Node.js and dsh onto the device (once)

The root filesystem is read-only (an overlay may make `/` look writable while `/usr` stays
unwritable and reverts on reboot), so `apt`/`dnf`/`pacman` are not reliable. **Install into `$HOME`**:

```bash
# Option A: nvm -- do NOT hardcode a version; ask for the latest tag first
NVM_VER=$(curl -s https://api.github.com/repos/nvm-sh/nvm/releases/latest \
  | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4)
echo "installing nvm $NVM_VER"
curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VER/install.sh" | bash

# Close and reopen the terminal (so nvm's environment is loaded), then:
nvm install --lts        # dsh wants Node >= 20; LTS is the stable line
nvm use --lts
node -v

npm i -g @deepseek-ai/dsh
dsh --version             # confirm it runs
```

> If `raw.githubusercontent.com` is unreachable (some networks block it), install via git:
> ```bash
> git clone --depth 1 https://github.com/nvm-sh/nvm.git ~/.nvm && cd ~/.nvm && ./install.sh
> ```

> **Record the output of `which node`** (e.g. `/home/deck/.nvm/versions/node/v24.x.x/bin/node`).
> A Decky plugin process inherits only a minimal PATH and **cannot see an nvm from your login
> shell**; if the probe reports no Node, put that path into the plugin's Advanced settings.

> Option B: fnm, or unpack an official prebuilt tarball into `~/.local`. A distro package is fine
> too if your system really persists writes to `/usr` — the plugin discovers paths on its own and
> lets you override them explicitly.

> If your system reports `/usr` as writable, a distro package is fine too — the plugin discovers
> whatever it can and lets you override the paths explicitly.

### 2. Package the plugin

A ready-to-install archive is produced by the packaging script:

```bash
bash package.sh          # writes ../dsh-decky.zip
```

`dist/index.js` must exist first. It is committed in this repo, but to rebuild it from
`src/index.tsx` you need a host where `@decky/rollup` can run:

```bash
pnpm install
pnpm run build
```

> `@rollup/rollup-linux-x64-musl` is pinned as a dev dependency because Decky's build normally runs
> on Linux x64; on other hosts that optional dep is skipped. It has nevertheless been built and
> verified on `linux/android arm64` (`@rollup/rollup-android-arm64`).

### 3. Deploy into Decky

Decky's own installer does `ZipFile(...).extractall(~/homebrew/plugins)`, so the zip must contain
**exactly one top-level directory** with `plugin.json` at depth 1 — `package.sh` guarantees this
and the README's test suite checks it.

```bash
# via Decky's UI: Settings → Developer → Install plugin from zip, pick dsh-decky.zip
# then reload the loader.

# or manually:
unzip dsh-decky.zip -d ~/homebrew/plugins/
# → ~/homebrew/plugins/dsh-decky/{plugin.json,package.json,main.py,dist/index.js,py_modules/}
```

### 4. First run

1. Open the Quick Access Menu → **DSH Launcher**.
2. Press **环境自检 (environment probe)** and read the table:
   - **Node.js / dsh** — resolved paths. If either is "not found", set them in Advanced.
   - **/ read-only** — expected `true` on SteamOS; tells you where to install.
   - **bwrap / Landlock** — if both are unusable, set the permission preset to
     `danger-full-access` (and understand what that means), or install `bubblewrap`.
3. Press **启动并打开 DSH (start and open)**. First cold boot can take 1–3 minutes; the engine's
   output is visible under Advanced → *View engine output*.

## Known limits (read before relying on this)

- **Not rendered inside the Decky panel.** The GUI opens in Steam's browser, not as an embedded
  panel, because the `SameSite=Strict` cookie rules out framing. This is a deliberate consequence
  of dsh's auth model, not an oversight.
- **Verified on real hardware.** On 2026-10-19 it was exercised on a SkorionOS / first-gen ROG Ally
  (x86_64): the plugin loads, the QAM panel works, the environment probe runs, and it **started the
  engine and opened the DSH GUI inside Steam's built-in browser**. Findings:
  - **`bwrap` is usable** → the first sandbox rung passes, so `danger-full-access` is **not** needed
    (`Landlock` reporting unusable is harmless: the Linux chain is `bwrap` → `landlock`, and
    passing the first rung is enough).
  - **`/` reported writable** → the usual "SteamOS root is read-only" assumption did not hold; yet
    `/usr` may still be unwritable or revert on reboot, so installing Node under `$HOME` remains the
    recommendation.
  - **Node discovery was a real pitfall** → the plugin process only inherits a minimal PATH and
    cannot see an nvm configured in the login shell. Since 0.1.1 the probe shows the actual PATH
    and the paths it tried, and covers Homebrew/nix/snap/distrobox layouts.
- **Still unverified.** Engine-side end-to-end behaviour (executing commands under Gaming Mode, long
  sessions, resume from suspend) is not sufficiently covered yet. Cold boot is slow — allow 1–3 min.
- **Cold boot is slow.** `dsh` resolves a large dependency graph on first run. `STARTUP_TIMEOUT_S`
  (180 s) bounds the wait and reports the engine's tail output on failure.
- **Gamepad input in Steam's browser** is Steam's own to manage; this plugin does not add gamepad
  bindings or a virtual keyboard of its own.
- **Port reuse cannot recover the token.** If another dsh instance owns the port, the plugin can
  only point the browser at it; a browser that has never authenticated cannot mint the cookie
  without that instance's launch URL.

## Tests (run without hardware)

The backend is pure Python with a stubbed `decky` module, so its logic is testable off-device:

```bash
PYTHONPATH=tests python3 tests/run_tests.py
```

Covered: URL capture, idempotent restart, URL-line filtering (the "opening the default browser"
line is correctly **not** treated as a URL), config round-trip, `--no-open` always present, argv
quoting of `extra_args`, death-before-URL raising cleanly, `stop()` never killing a foreign
instance, and the packaged zip's Decky layout rules.

Three real defects were found and fixed this way, rather than by inspection:

1. **Deadlock** — `start()` re-entered a non-reentrant `asyncio.Lock` by calling `stop()`.
2. **Misleading exit code** — the stdout pump reported `exit=None` because EOF arrives before the
   process is reaped; it now awaits the real status.
3. **1.4 MB sourcemap** — `@decky/rollup` wins option conflicts with its defaults, so
   `output.sourcemap` must be mutated on the returned config, not passed in.

## Files

| Path | Role |
|---|---|
| `plugin.json` | Decky manifest (no `root` flag) |
| `main.py` | Decky backend: discovery, launch, URL capture, probe, settings |
| `src/index.tsx` | QAM panel UI |
| `tests/run_tests.py` | 68 offline checks (run without a Deck) |
| `package.sh` | Builds `dsh-decky.zip` in the Decky-required layout |
| `tsconfig.json`, `rollup.config.js`, `package.json` | Build toolchain |

## License

MIT. Not affiliated with Valve, Decky, or DeepSeek.
