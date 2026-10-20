# DSH Launcher

**在 Steam 游戏模式里用上 DSH 的 Web Agent —— 不用切桌面模式。**

[![Decky](https://img.shields.io/badge/Decky-Loader-1a9fff)](https://github.com/SteamDeckHomebrew/decky-loader)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

简体中文 | [English](README.en.md)

![两种打开方式演示](docs/ab-demo.gif)

---

## 这是什么

[DeepSeek Harness（`dsh`）](https://github.com/deepseek-ai/DeepSeek-Harness) 是个强大的 Agent 运行时，但它得靠浏览器界面来用。而在 SteamOS 掌机的**游戏模式**下，没有桌面会话 —— 没有浏览器可以打开，`dsh` 默认的 `xdg-open` 交接也失效。

这个插件解决的就是这一步：**在游戏模式里把 dsh 跑起来，并把界面送到你眼前。**

- 一键从快速访问菜单（QAM）启动/停止引擎
- 环境自检：告诉你 Node/dsh 在哪、沙箱能不能用
- 两种打开方式可选（见下）
- 6 秒内热更新；停止是显式动作，不会因插件重载而杀掉你的会话

> **它是 DSH 插件吗？** 不是。这是 **Decky Loader 插件** —— 两套不同的插件生态。
> 另外，**`dsh` 引擎本身不需要移植**：它是纯 JavaScript，无 `os`/`cpu` 限制，Linux x64/arm64 的预编译件都已发布在 npm 上。SteamOS 缺的只是一层**启动适配层**，也就是本插件。

## 两种打开方式

两者都是**顶层导航**，因此都满足 dsh 的 `SameSite=Strict` Cookie 要求。

| | 方式 A · Steam 内置浏览器（默认） | 方式 B · 外部浏览器独立窗口 |
|---|---|---|
| 做法 | `Navigation.NavigateToExternalWeb(url)`，交给 Steam 自己的浏览器 | 插件启动真实浏览器：Chromium 系 `--app=<url>`；Firefox 系 `--kiosk <url>` |
| 形态 | 在 Steam 浏览器里打开 | 无地址栏窗口，**盖在 Gaming Mode 之上** |
| 依赖 | Steam 未公开 API（`CreateBrowserView` 等） | **完全绕开** Steam 私有 API |
| 抗更新 | 较弱（Steam 升级可能失效） | **较强**（用的是标准浏览器） |
| 前提 | Steam 自带浏览器可用 | 设备上装着浏览器（含 flatpak 版） |

方式 B 会自动探测浏览器：原生路径（`/usr/bin`、Homebrew、nix、snap）→ flatpak。面板里有「探测可用浏览器」按钮可直接查看。

> **为什么不能用 `<iframe>` 内嵌？**
> dsh 的会话 Cookie 是 `HttpOnly; SameSite=Strict` 且绑定到具体 authority。iframe 属同站跨源，到达时**不带 Cookie**，界面根本出不来。

## 安装

### 第一步：设备上装好 Node.js 与 dsh

> 根文件系统通常只读（`/` 可能因 overlay 显示为可写，但 `/usr` 多半仍不可写、重启即丢）。**推荐装到 `$HOME`。**

```sh
# 装 nvm —— 注意不要写死版本号，先取最新 tag
NVM_VER=$(curl -s https://api.github.com/repos/nvm-sh/nvm/releases/latest \
  | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4)
curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VER/install.sh" | bash

# 关掉终端重开（让 nvm 环境变量生效），然后：
nvm install --lts && nvm use --lts
node -v

npm i -g @deepseek-ai/dsh
dsh --version
```

若 `raw.githubusercontent.com` 不可达，改用 git：
```sh
git clone --depth 1 https://github.com/nvm-sh/nvm.git ~/.nvm && cd ~/.nvm && ./install.sh
```

> ⚠️ **记下 `which node` 的输出**（如 `/home/deck/.nvm/versions/node/v24.x.x/bin/node`）。
> Decky 插件是服务进程，**只继承精简的 PATH、看不到你登录 shell 里的 nvm**。若自检报找不到 Node，把这个路径填进插件「高级设置」。

### 第二步：装插件

```sh
curl -L -o dsh-decky.zip \
  https://github.com/3570548848/dsh-decky/releases/latest/download/dsh-decky.zip
```

- **Decky 界面**：设置 → 开发者 → 从 zip 安装插件 → 重载 loader
- **手动**：`unzip dsh-decky.zip -d ~/homebrew/plugins/`

> 用上面的 `/releases/latest/download/` 即可，它始终指向最新正式版（当前 v0.1.15）。想锁版本就把 `latest` 换成具体 tag，例如 `v0.1.15`。

压缩包内必须是**恰好一层顶层目录**（`dsh-decky/plugin.json`）——这是 Decky 安装器 `extractall` 的硬性要求，打包脚本与测试都会校验。

### 第三步：首次运行

1. QAM → **DSH Launcher**
2. 点 **环境自检**，看三项：
   - **Node.js / dsh** ——解析到的路径；显示「未找到」就去高级设置手填
   - **bwrap / Landlock** ——若都不可用，把权限档位设为 `danger-full-access`（并弄清其含义），或安装 `bubblewrap`
   - **`/` 是否只读** ——告诉你该往哪装
3. 点 **启动并打开 DSH**。首次冷启动约 1–3 分钟，引擎输出可在「高级 → 查看引擎输出」看到

## 安全

- **不使用 `root` 标志。** 插件以普通用户身份运行引擎。Decky 支持让后端以 root 运行，但那样 Agent 会在你家目录里留下 root 属主文件——第三方插件用能满足功能的最小权限才对。
- **不读取、不存储任何凭据。** 插件从不打开 `~/.dsh` 里的密钥；启动令牌只是从引擎 stdout 解析出来交给浏览器。
- **`danger-full-access` 是有文档说明的应急出口**，不是默认值。它会解除 Agent 每条命令的文件约束，只应在沙箱执行器确实不可用时启用。

## 版本与更新记录

### v0.1.15 · 引擎环境不再被 PyInstaller 污染

**症状**：DSH 引擎正常起来了，界面也能开，但配置管理的**同步**失败——

```
读取远端快照失败：git clone https://github.com/<user>/<repo>.git 失败 (exit 128)
… /_MEI0000054cWWSwqE/libssl.so.3: version `OPENSSL_3.5.0' not found
   (required by /usr/lib/libcurl.so.4) …
致命错误：remote helper 'https' aborted session
```

**根因**：SteamOS 的 `/usr/bin/flatpak` 是 PyInstaller 打包的，它把自己的旧 OpenSSL 解包到 `$TMPDIR/_MEIxxxxxx/`。Decky 服务进程的 `LD_LIBRARY_PATH` 恰好指向那种目录，于是**所有子进程**（node、git、git-remote-https）都优先从那里加载 libssl，版本不够就 abort。v0.1.6 修过一模一样的坑，但只修了「启动浏览器的环境」（`_gui_env`），**启动引擎的环境**（`_build_env`）仍然原样继承 `os.environ` —— 引擎活了，它下面的 git 死了。

**修法**：把清洗提到最外层统一入口 `_sanitize_inherited_env()`，引擎与浏览器两条 spawn 路径都走它。它比 v0.1.6 更克制也更彻底：

- `LD_LIBRARY_PATH` / `LD_PRELOAD` 里**只删**指向 `_MEI…` 的条目和已不存在的目录，**你手动设的合法值会被保留**（v0.1.6 是整条变量丢掉）；
- 整条都被遮蔽时**移除变量**而不是留空（空条目在加载器语义里等于「当前目录」）；
- `TMPDIR` 只在「是 `_MEI` 目录 / 不可写 / 不存在」时才换成 `/tmp`，合理值不动。

**如果你现在就卡在这**：升级本插件并重启引擎即可（插件改的是启动环境，不重启不生效）。临时应急也可以手动：

```bash
env -u LD_LIBRARY_PATH TMPDIR=/tmp <原来的 dsh 启动命令> --profile web --no-open --port 3080
```

或者把配置管理的同步通道从 **Git** 换成 **Gist / WebDAV** —— 那两条走 Node 的 HTTPS，根本不 spawn `git`，绕开动态链接器。

## 已知限制

- **界面不在 Decky 面板内**（方式 A/B 都不是内嵌）——`SameSite=Strict` 排除了 iframe。这是 dsh 鉴权模型的必然结果。
- **方式 B 尚未实机验证**：`--app`/`--kiosk` 启动、GUI 环境变量注入、以及在 Gaming Mode 下窗口能否正常显示，都还没在真机上跑过。
- **冷启动较慢**：首次运行要解析大片依赖图，超时上限 180 秒。
- **端口复用拿不回令牌**：若端口已被**别的** dsh 实例占用，插件拿不到它的启动令牌（令牌随机生成、仅存内存），浏览器也就无法鉴权。此时**换个端口**（如 3081）即可。
- **手柄输入**在 Steam 浏览器内由 Steam 管理；本插件不提供额外的按键绑定或虚拟键盘。
- 引擎侧端到端（游戏模式下执行命令、长会话、休眠恢复）**仍未充分验证**。

## 设计要点与依据

以下每条都从真实安装包源码读出，而非凭记忆。来源：`@deepseek-ai/dsh` 0.2.1-rc.2、`@decky/ui` 4.15.1、`@decky/api` 1.1.3、官方 `decky-plugin-template`、[jessebofill/DeckWebBrowser](https://github.com/jessebofill/DeckWebBrowser)。

<details>
<summary><b>关键事实与证据（点击展开）</b></summary>

| 事实 | 影响 | 证据 |
|---|---|---|
| `@deepseek-ai/dsh` 未声明 `os`/`cpu`；依赖含 `node-addon-system-linux-x64` | 无需为 DSH 内核移植 | `0.2.1-rc.2` npm 元数据 |
| `dsh web` 向 stdout 打印 `dsh web: <url>` | 启动令牌只出现在这一行 | `dsh-web-app/lib/index.js:162` |
| 鉴权用 `?token=`，随后下发**绑定 authority** 的 `HttpOnly; SameSite=Strict` Cookie | 界面**必须**顶层导航；iframe 拿不到 Cookie | `dsh-client-connection/lib/index.js:348` |
| 浏览器交接走 `open` → `xdg-open`；`--no-open` 跳过 | 游戏模式无桌面会话，**必须 `--no-open`** | `dsh-web-app/lib/index.js:156-169` |
| Linux 沙箱链 `bwrap` → `landlock`；都失败则 **fail-closed** 拒绝执行 | 正常的掌机也可能拒绝任何命令 | `dsh-sandbox-local`：`PLATFORM_CHAINS.linux` |
| `danger-full-access` 完全绕过 `ctx.sandbox` | 无可沙箱执行器时的应急出口 | `dsh-bash-sandbox/lib/index.js:68` |
| Linux 上 node-pty 走 `forkpty()`（`spawn-helper` 仅 macOS） | Linux PTY 无需额外垫片 | `node-pty/src/unix/pty.cc:393` |
| `koffi` 只在 Win32 惰性加载 | 非 Windows 无需构建 FFI | `dsh-win32-process/lib/index.js:25` |
| Decky `flags` 可写 `root` → 后端以 root 运行 | **本插件刻意不用** | `decky.pyi` 29/37 行 |

</details>

<details>
<summary><b>启动与打开的实现细节（点击展开）</b></summary>

**启动。** 后端在**独立进程组**里拉起 `dsh --profile web --no-open --port <N>`，持续读 stdout 解析带令牌 URL。之后**先等端口真能接受连接**才把 URL 交出去——打印那一行发生在端口绑定之前，只看它会有竞态。

**打开。** 见上文两种方式。方式 B 的浏览器探测顺序为原生路径 → flatpak（先 `flatpak info` 试探，再 `flatpak run`），并**显式注入 GUI 环境变量**（`DISPLAY`、`WAYLAND_DISPLAY`、`XDG_RUNTIME_DIR`）——插件是服务进程，通常继承不到，缺了浏览器起不来或不可见。

**存活。** `_unload` 刻意**不**停引擎。插件重载、Steam 从休眠恢复，都不该杀掉进行中的 Agent 会话。停止是明确的用户动作。

**绝不越界。** 端口已被别的实例占用时，报为**外部实例**、标 `managed: false`，且 **`stop()` 不会去杀它**——有测试覆盖。

</details>

## 开发

```sh
pnpm install
pnpm run build      # 构建 src/index.tsx → dist/index.js
bash package.sh     # 按 Decky 要求布局打包 → ../dsh-decky.zip
PYTHONPATH=tests python3 tests/run_tests.py    # 80 项离线检查，无需掌机
```

后端是纯 Python，只依赖一个被 stub 的 `decky` 模块，因此**逻辑可脱离设备测试**。

覆盖范围：URL 捕获、重复启动、URL 行过滤（「opening the default browser」会被正确**排除**）、配置往返、始终带 `--no-open`、`extra_args` 的 argv 处理、报 URL 前进程死亡的干净报错、`stop()` 不杀外部实例、zip 的 Decky 目录规则、方案 B 的启动参数与 GUI 环境注入。

**测试抓出的真实缺陷**（并非肉眼检查发现）：

1. **死锁** —— `start()` 调用 `stop()`，重入不可重入的 `asyncio.Lock`
2. **误导的退出码** —— stdout 泵报 `exit=None`，因为进程回收前 EOF 已到
3. **1.4 MB sourcemap** —— `@decky/rollup` 的选项合并由**默认值**胜出，必须改返回值而非传参
4. **属性遮蔽方法** —— `self._browser_argv` 把同名方法遮住，调用报 `NoneType not callable`
5. **死配置** —— `open_with` 早已声明却从未被后端读取，等于宣告了一个不存在的选项

## 文件结构

| 路径 | 作用 |
|---|---|
| `plugin.json` | Decky 清单（不含 `root` 标志） |
| `main.py` | 后端：路径发现、启动、URL 捕获、环境探测、设置读写、外部窗口 |
| `src/index.tsx` | QAM 面板界面 |
| `dist/index.js` | 构建产物（已提交） |
| `tests/run_tests.py` | 80 项离线检查 |
| `package.sh` | 按 Decky 布局打包 |
| `docs/ab-demo.gif` | 两种打开方式的演示动画 |

## 许可

MIT。与 Valve、Decky、DeepSeek 均无附属关系。
