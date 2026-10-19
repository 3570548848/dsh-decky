# DSH Launcher — 面向 SteamOS 系掌机的 Decky Loader 插件

简体中文 | [English](README.en.md)

在 **Steam 游戏模式（Gaming Mode）** 里运行 **DeepSeek Harness（`dsh`）** 的 Web Agent，并用 Steam 自带的浏览器打开它的图形界面——不必切到桌面模式，也不依赖 `xdg-open`。

顺带回答那个问题：*「能不能做一个适用于 SteamOS 的 dsh 插件？」*——`dsh` 引擎本身**不需要移植**：它是纯 JavaScript，没有 `os`/`cpu` 限制，Linux x64/arm64 的预编译件也都发布在 npm 上。SteamOS 真正需要的是一层**启动 / 适配层**，也就是本插件。（注意：*DSH* 插件与 *Decky* 插件是两套不同的插件生态，本仓库是 **Decky** 插件。）

---

## 已核实的事实

以下每条都从真实安装包里读出来，不是凭记忆。来源：`@deepseek-ai/dsh` 0.2.1-rc.2、`@decky/ui` 4.15.1、`@decky/api` 1.1.3、官方 `decky-plugin-template`，以及 [jessebofill/DeckWebBrowser](https://github.com/jessebofill/DeckWebBrowser)。

| 事实 | 影响 | 证据 |
|---|---|---|
| `@deepseek-ai/dsh` 未声明 `os`/`cpu` 限制；依赖里含 `@deepseek-ai/node-addon-system-linux-x64` | **无需为 DSH 内核做移植。** Linux x64 本就是受支持的目标平台 | `0.2.1-rc.2` 的 npm 元数据 |
| `dsh web` 会向 stdout 打印 `dsh web: <authenticated-url>` | 启动令牌只出现在这一行，必须解析它 | `dsh-web-app/lib/index.js:162` |
| `dsh` 通过 `?token=` 鉴权，随后下发 **绑定到该 authority 的** `HttpOnly; SameSite=Strict` Cookie | 界面**必须**在真实浏览上下文里以顶层导航打开。用 `<iframe>` 属同站跨源，到达时**不带 Cookie**，等于未鉴权 | `dsh-client-connection/lib/index.js:348`（`sessionCookie`） |
| `dsh web` 的浏览器交接走 `open` 包 → `xdg-open`；加 `--no-open` 即跳过 | 游戏模式没有桌面会话，所以**必须始终以 `--no-open` 启动**、由我们自己打开 URL | `dsh-web-app/lib/index.js:156-169` |
| Linux 沙箱链是 `bwrap` → `landlock`；若两者探测都失败，则**直接拒绝执行（fail-closed，报 `SANDBOX_UNAVAILABLE`）**，不会静默地无约束放行 | 一台看起来正常的掌机也可能拒绝任何命令。两者都要探测，并把修复办法讲清楚 | `dsh-sandbox-local`：`PLATFORM_CHAINS.linux = ["bwrap","landlock"]` |
| `danger-full-access` **完全绕过 `ctx.sandbox`**（走 `super.execute`，`denied: false`） | 当机器上没有可用沙箱执行器时的应急出口 | `dsh-bash-sandbox/lib/index.js:68`；其 README 第 173 行 |
| Linux 上 node-pty 走 `forkpty()`；`spawn-helper` 仅 `#if defined(__APPLE__)` 时使用 | Linux 的 PTY **不需要**额外垫片；`prebuilds/linux-x64/pty.node` 随包发布 | `node-pty/src/unix/pty.cc:393` |
| `koffi`（FFI）只在 Win32 路径上经 `createLazyRequire` 加载 | 非 Windows 永不加载它，无需构建 FFI | `dsh-win32-process/lib/index.js:25` |
| Decky 的 `plugin.json` 中 `flags` 可写 `root`，会让**后端以 root 身份运行** | **本插件刻意不使用它**——见下方「安全」一节 | `decky.pyi` 第 29/37 行 |

## 设计思路与理由

**启动。** 后端在**独立进程组**里拉起 `dsh --profile web --no-open --port <N>`，持续读取 stdout，解析出打印的带令牌 URL。之后它会**先等端口真正能接受连接**再把 URL 交出去——因为打印那一行发生在端口绑定之前，只看那一行就打开会有竞态。

**打开。** 前端调用 `Navigation.NavigateToExternalWeb(url)`（来自 `@decky/ui`），把 URL 交给 Steam 自带浏览器。正因为那个 `SameSite=Strict` Cookie，这才是唯一可行的路径：必须是顶层导航，不能是 frame。

**存活。** `_unload` 刻意**不**停止引擎。插件重载、或 Steam 从休眠恢复，都不该杀掉正在进行的 Agent 会话。停止是一个明确的用户动作。

**绝不越界。** 如果端口已经在服务（比如 systemd 单元、手工起的进程），插件会把它报为**外部实例**、标记 `managed: false`，并且 **`stop()` 不会去杀它**——这一点有测试覆盖。

## 安全

- **不使用 `root` 标志。** 插件以普通用户身份运行引擎，不触碰任何特权操作。让 Agent 以 root 运行，意味着 root 属主的文件会悄悄出现在你的家目录里；而 Decky 插件属于第三方代码——能满足功能的最小权限才是正确选择。
- **不读取、不存储任何凭据。** 插件从不打开 `~/.dsh` 里的密钥；启动令牌是从引擎自己的 stdout 解析出来的，直接交给 Steam 浏览器。
- `danger-full-access` 是**有文档说明的应急出口**，不是默认值。它会关闭 Agent 每条命令的文件约束。只有在环境自检报告两个沙箱执行器都不可用、并且你接受无约束执行时，才应启用。

## 安装

### 1. 先把 Node.js 与 dsh 装到设备上（只需一次）

根文件系统是只读的（`/` 可能因 overlay 显示为可写，但 `/usr` 通常仍不可写、且重启会丢），所以 `apt`/`dnf`/`pacman` 未必可靠。**推荐装到 `$HOME`**：

```bash
# 方案 A：nvm —— 不要写死版本号，先取最新 tag 再装
NVM_VER=$(curl -s https://api.github.com/repos/nvm-sh/nvm/releases/latest \
  | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4)
echo "即将安装 nvm $NVM_VER"
curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VER/install.sh" | bash

# 关闭终端重开（让 nvm 的环境变量生效），然后：
nvm install --lts        # dsh 要求 Node >= 20；用 LTS 稳定线
nvm use --lts
node -v

npm i -g @deepseek-ai/dsh
dsh --version             # 确认能跑起来
```

> 若 `raw.githubusercontent.com` 不通（部分网络环境下该域名不可达），改用 git 安装：
> ```bash
> git clone --depth 1 https://github.com/nvm-sh/nvm.git ~/.nvm && cd ~/.nvm && ./install.sh
> ```

> **务必记下 `which node` 的输出**（形如 `/home/deck/.nvm/versions/node/v24.x.x/bin/node`）。
> Decky 插件进程只继承精简的 PATH，**看不到你登录 shell 里的 nvm**；若自检报找不到 Node，
> 就把这个路径填进插件的「高级设置」。

> 方案 B：fnm，或把官方预编译压缩包解到 `~/.local`。若你的发行版能持久地写 `/usr`，
> 用软件包管理器也可以——插件会自行发现路径，也允许在设置里显式覆盖。

### 2. 打包插件

打包脚本会产出可直接安装的压缩包：

```bash
bash package.sh          # 生成 ../dsh-decky.zip
```

前提是 `dist/index.js` 已存在。它已随本仓库提交；若要从 `src/index.tsx` 重新构建，你需要一台能运行 `@decky/rollup` 的主机：

```bash
pnpm install
pnpm run build
```

> `@rollup/rollup-linux-x64-musl` 被固定为开发依赖，因为 Decky 的构建通常在 Linux x64 上进行；在其它主机上该可选依赖会被跳过。不过本项目已在 `linux/android arm64`（`@rollup/rollup-android-arm64`）上构建并验证通过。

### 3. 部署到 Decky

Decky 自带的安装器执行的是 `ZipFile(...).extractall(~/homebrew/plugins)`，所以压缩包里**必须恰好只有一层顶层目录**、且 `plugin.json` 位于深度 1——`package.sh` 保证了这一点，README 配套的测试套件也会校验。

```bash
# 走 Decky 界面：设置 → 开发者 → 从 zip 安装插件，选中 dsh-decky.zip
# 然后重载 loader。

# 或手动：
unzip dsh-decky.zip -d ~/homebrew/plugins/
# → ~/homebrew/plugins/dsh-decky/{plugin.json,package.json,main.py,dist/index.js,py_modules/}
```

### 4. 首次运行

1. 打开快速访问菜单（Quick Access Menu）→ **DSH Launcher**。
2. 点 **环境自检（environment probe）**，看结果：
   - **Node.js / dsh** ——解析到的路径。若显示「未找到」，去高级设置里填上。
   - **/ 只读** ——SteamOS 上应为 `true`；它告诉你该往哪儿装。
   - **bwrap / Landlock** ——若两者都不可用，把权限档位设为 `danger-full-access`（并弄清这意味着什么），或安装 `bubblewrap`。
3. 点 **启动并打开 DSH（start and open）**。首次冷启动可能耗时 1–3 分钟；引擎输出可在 高级 →「查看引擎输出」里看到。

## 已知限制（依赖它之前请先读）

- **界面不渲染在 Decky 面板内。** 图形界面在 Steam 浏览器里打开，而不是内嵌面板，因为 `SameSite=Strict` Cookie 排除了 iframe 方案。这是 dsh 鉴权模型的必然结果，不是疏漏。
- **已在真机上跑通。** 2026-10-19 在 SkorionOS / ROG Ally 初代（x86_64）上实测：插件正常加载、QAM 面板可用、环境自检可运行，**并能启动引擎、在 Steam 自带浏览器里打开 DSH 图形界面**。以下为实测结论：
  - **`bwrap` 可用** → 沙箱第一级通过，**不需要** `danger-full-access`（`Landlock` 报不可用无妨，Linux 链是 `bwrap` → `landlock`，前级通过即可）。
  - **`/` 显示为可写** → 推翻了「SteamOS 根必只读」的通用假设；但 `/usr` 可能仍不可写、或重启即丢，因此安装 Node 仍建议落在 `$HOME`。
  - **Node 路径发现曾是坑** → 插件进程只继承精简 PATH，看不到登录 shell 的 nvm。0.1.1 起自检会显示真实 PATH、试过的路径，并覆盖 Homebrew/nix/snap/distrobox 等落点。
- **仍有未覆盖项。** 引擎侧的端到端能力（在游戏模式下真正执行命令、长会话、休眠恢复）尚未充分验证；首次冷启动较慢，请预留 1–3 分钟。
- **冷启动较慢。** `dsh` 首次运行要解析一大片依赖图。`STARTUP_TIMEOUT_S`（180 秒）限制了等待上限，失败时会回报引擎的输出尾部。
- **Steam 浏览器内的手柄输入**由 Steam 自己管理；本插件不额外提供手柄绑定或虚拟键盘。
- **端口复用无法找回令牌。** 若端口已被另一个 dsh 实例占用，插件只能把浏览器指过去；一个从未鉴权过的浏览器，拿不到该实例的启动 URL 就无法生成 Cookie。

## 测试（无需硬件即可运行）

后端是纯 Python，只依赖一个被 stub 的 `decky` 模块，因此逻辑可脱离设备测试：

```bash
PYTHONPATH=tests python3 tests/run_tests.py
```

覆盖范围：URL 捕获、可重复的重复启动、URL 行过滤（「opening the default browser」那行会被正确**排除**，不当作 URL）、配置往返读写、始终带上 `--no-open`、`extra_args` 的 argv 引用处理、报告 URL 前进程死亡的干净报错、`stop()` 永不杀死外部实例，以及打包后 zip 的 Decky 目录规则。

有三个真实缺陷是靠这套测试（而非肉眼检查）发现并修掉的：

1. **死锁** —— `start()` 调用 `stop()`，重入了一个不可重入的 `asyncio.Lock`。
2. **误导性的退出码** —— stdout 泵报出 `exit=None`，因为进程被回收之前 EOF 就已到达；现在它会等待真实退出状态。
3. **1.4 MB 的 sourcemap** —— `@decky/rollup` 在与默认值发生选项冲突时由默认值胜出，所以 `output.sourcemap` 必须改在返回的 config 对象上，而不是作为参数传入。

## 文件说明

| 路径 | 作用 |
|---|---|
| `plugin.json` | Decky 清单（不含 `root` 标志） |
| `main.py` | Decky 后端：路径发现、启动、URL 捕获、环境探测、设置读写 |
| `src/index.tsx` | 快速访问菜单（QAM）面板界面 |
| `tests/run_tests.py` | 68 项离线检查（无需掌机） |
| `package.sh` | 按 Decky 要求的布局生成 `dsh-decky.zip` |
| `tsconfig.json`、`rollup.config.js`、`package.json` | 构建工具链 |

## 许可

MIT。与 Valve、Decky、DeepSeek 均无附属关系。
