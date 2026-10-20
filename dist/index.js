const manifest = {"name":"DSH Launcher"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const addEventListener = api.addEventListener;
const removeEventListener = api.removeEventListener;
const toaster = api.toaster;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

var DefaultContext = {
  color: undefined,
  size: undefined,
  className: undefined,
  style: undefined,
  attr: undefined
};
var IconContext = SP_REACT.createContext && /*#__PURE__*/SP_REACT.createContext(DefaultContext);

var _excluded = ["attr", "size", "title"];
function _objectWithoutProperties(e, t) { if (null == e) return {}; var o, r, i = _objectWithoutPropertiesLoose(e, t); if (Object.getOwnPropertySymbols) { var n = Object.getOwnPropertySymbols(e); for (r = 0; r < n.length; r++) o = n[r], -1 === t.indexOf(o) && {}.propertyIsEnumerable.call(e, o) && (i[o] = e[o]); } return i; }
function _objectWithoutPropertiesLoose(r, e) { if (null == r) return {}; var t = {}; for (var n in r) if ({}.hasOwnProperty.call(r, n)) { if (-1 !== e.indexOf(n)) continue; t[n] = r[n]; } return t; }
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function ownKeys(e, r) { var t = Object.keys(e); if (Object.getOwnPropertySymbols) { var o = Object.getOwnPropertySymbols(e); r && (o = o.filter(function (r) { return Object.getOwnPropertyDescriptor(e, r).enumerable; })), t.push.apply(t, o); } return t; }
function _objectSpread(e) { for (var r = 1; r < arguments.length; r++) { var t = null != arguments[r] ? arguments[r] : {}; r % 2 ? ownKeys(Object(t), true).forEach(function (r) { _defineProperty(e, r, t[r]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function (r) { Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r)); }); } return e; }
function _defineProperty(e, r, t) { return (r = _toPropertyKey(r)) in e ? Object.defineProperty(e, r, { value: t, enumerable: true, configurable: true, writable: true }) : e[r] = t, e; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == typeof i ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != typeof t || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r); if ("object" != typeof i) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); }
function Tree2Element(tree) {
  return tree && tree.map((node, i) => /*#__PURE__*/SP_REACT.createElement(node.tag, _objectSpread({
    key: i
  }, node.attr), Tree2Element(node.child)));
}
function GenIcon(data) {
  return props => /*#__PURE__*/SP_REACT.createElement(IconBase, _extends({
    attr: _objectSpread({}, data.attr)
  }, props), Tree2Element(data.child));
}
function IconBase(props) {
  var elem = conf => {
    var attr = props.attr,
      size = props.size,
      title = props.title,
      svgProps = _objectWithoutProperties(props, _excluded);
    var computedSize = size || conf.size || "1em";
    var className;
    if (conf.className) className = conf.className;
    if (props.className) className = (className ? className + " " : "") + props.className;
    return /*#__PURE__*/SP_REACT.createElement("svg", _extends({
      stroke: "currentColor",
      fill: "currentColor",
      strokeWidth: "0"
    }, conf.attr, attr, svgProps, {
      className: className,
      style: _objectSpread(_objectSpread({
        color: props.color || conf.color
      }, conf.style), props.style),
      height: computedSize,
      width: computedSize,
      xmlns: "http://www.w3.org/2000/svg"
    }), title && /*#__PURE__*/SP_REACT.createElement("title", null, title), props.children);
  };
  return IconContext !== undefined ? /*#__PURE__*/SP_REACT.createElement(IconContext.Consumer, null, conf => elem(conf)) : elem(DefaultContext);
}

// THIS FILE IS AUTO GENERATED
function FaRocket (props) {
  return GenIcon({"attr":{"viewBox":"0 0 512 512"},"child":[{"tag":"path","attr":{"d":"M505.12019,19.09375c-1.18945-5.53125-6.65819-11-12.207-12.1875C460.716,0,435.507,0,410.40747,0,307.17523,0,245.26909,55.20312,199.05238,128H94.83772c-16.34763.01562-35.55658,11.875-42.88664,26.48438L2.51562,253.29688A28.4,28.4,0,0,0,0,264a24.00867,24.00867,0,0,0,24.00582,24H127.81618l-22.47457,22.46875c-11.36521,11.36133-12.99607,32.25781,0,45.25L156.24582,406.625c11.15623,11.1875,32.15619,13.15625,45.27726,0l22.47457-22.46875V488a24.00867,24.00867,0,0,0,24.00581,24,28.55934,28.55934,0,0,0,10.707-2.51562l98.72834-49.39063c14.62888-7.29687,26.50776-26.5,26.50776-42.85937V312.79688c72.59753-46.3125,128.03493-108.40626,128.03493-211.09376C512.07526,76.5,512.07526,51.29688,505.12019,19.09375ZM384.04033,168A40,40,0,1,1,424.05,128,40.02322,40.02322,0,0,1,384.04033,168Z"},"child":[]}]})(props);
}

const getConfig = callable("get_config");
const setConfig = callable("set_config");
const getStatus = callable("status");
const startEngine = callable("start");
const stopEngine = callable("stop");
const getLog = callable("get_log");
const openExternal = callable("open_external");
const closeExternal = callable("close_external");
const browserProbe = callable("browser_probe");
const probeEnv = callable("probe");
// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
/**
 * Open the DSH GUI.
 *
 * dsh authenticates the browser with a launch token in the query string, then
 * mints an `HttpOnly; SameSite=Strict` cookie bound to the exact authority.
 * Load-bearing consequence: the GUI must be opened as a top-level navigation in
 * a real browsing context. An <iframe> would be same-site-but-cross-origin and
 * would arrive without the cookie, so it is not an option (verified against
 * dsh-client-connection: sessionCookie() pins SameSite=Strict + HttpOnly).
 *
 * Two modes, chosen by the `open_with` setting:
 *   - "builtin": route into Steam's own browser via NavigateToExternalWeb.
 *   - "external" (plan B): start a real browser as a standalone window
 *     (`chromium --app=<url>` / `firefox --kiosk <url>`). Both are top-level
 *     navigations, so the strict cookie is satisfied either way.
 */
async function openGui(url, mode) {
    if (mode === "external") {
        try {
            const res = await openExternal();
            if (res.ok) {
                toaster.toast({ title: "已在外部窗口打开", body: res.browser ?? "" });
                return;
            }
            // Fall back to the built-in browser rather than leaving a dead button,
            // but say why — a silent fallback would hide a real configuration issue.
            toaster.toast({
                title: "外部窗口打开失败，改用内置浏览器",
                body: (res.advice ?? res.reason ?? "").slice(0, 220),
            });
        }
        catch (e) {
            toaster.toast({ title: "外部窗口调用失败，改用内置浏览器", body: String(e).slice(0, 220) });
        }
    }
    // Built-in browser path (also the fallback above).
    const attempts = [
        ["Navigation", () => DFL.Navigation.NavigateToExternalWeb(url)],
        ["Router", () => DFL.Router.NavigateToExternalWeb(url)],
    ];
    const errors = [];
    for (const [label, run] of attempts) {
        try {
            run();
            return;
        }
        catch (e) {
            errors.push(`${label}: ${String(e)}`);
        }
    }
    toaster.toast({ title: "打开失败", body: errors.join(" | ") });
}
function Row({ label, value, warn }) {
    return (SP_JSX.jsx(DFL.Field, { label: label, childrenLayout: "below", bottomSeparator: "none", children: SP_JSX.jsx("div", { style: {
                fontFamily: "monospace",
                fontSize: "0.8em",
                wordBreak: "break-all",
                paddingTop: "2px",
                paddingBottom: "6px",
                color: warn ? "#ff8a80" : undefined,
            }, children: value }) }));
}
// ---------------------------------------------------------------------------
// Content
// ---------------------------------------------------------------------------
function Content() {
    const [cfg, setCfg] = SP_REACT.useState(null);
    const [status, setStatus] = SP_REACT.useState(null);
    const [probe, setProbe] = SP_REACT.useState(null);
    const [log, setLog] = SP_REACT.useState([]);
    const [busy, setBusy] = SP_REACT.useState(null);
    const [showAdvanced, setShowAdvanced] = SP_REACT.useState(false);
    const [browserInfo, setBrowserInfo] = SP_REACT.useState(null);
    const refresh = async () => {
        try {
            const [c, s] = await Promise.all([getConfig(), getStatus()]);
            setCfg(c);
            setStatus(s);
        }
        catch (e) {
            toaster.toast({ title: "读取状态失败", body: String(e) });
        }
    };
    SP_REACT.useEffect(() => {
        refresh();
        const poll = setInterval(async () => {
            try {
                setStatus(await getStatus());
            }
            catch {
                /* keep last known status */
            }
        }, 4000);
        return () => clearInterval(poll);
    }, []);
    const patch = async (p) => {
        try {
            setCfg(await setConfig(p));
        }
        catch (e) {
            toaster.toast({ title: "保存失败", body: String(e) });
        }
    };
    const doStart = async () => {
        setBusy("start");
        try {
            const res = await startEngine();
            await refresh();
            if (res.note) {
                toaster.toast({ title: "复用已有实例", body: res.note });
            }
            await openGui(res.url, cfg?.config?.open_with ?? "builtin");
        }
        catch (e) {
            toaster.toast({ title: "启动失败", body: String(e).slice(0, 400) });
            setLog((await getLog().catch(() => ({ lines: [] }))).lines);
        }
        finally {
            setBusy(null);
        }
    };
    const doStop = async () => {
        setBusy("stop");
        try {
            await stopEngine();
            await refresh();
        }
        catch (e) {
            toaster.toast({ title: "停止失败", body: String(e) });
        }
        finally {
            setBusy(null);
        }
    };
    const doProbe = async () => {
        setBusy("probe");
        try {
            setProbe(await probeEnv());
        }
        catch (e) {
            toaster.toast({ title: "环境自检失败", body: String(e) });
        }
        finally {
            setBusy(null);
        }
    };
    const doLog = async () => {
        setBusy("log");
        try {
            setLog((await getLog()).lines);
        }
        finally {
            setBusy(null);
        }
    };
    const st = status;
    const known = Boolean(cfg?.resolved?.node);
    const verdict = probe?.sandbox_verdict;
    return (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsxs(DFL.PanelSection, { title: "\u5F15\u64CE", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.Field, { label: "\u72B6\u6001", childrenLayout: "below", children: SP_JSX.jsx("div", { style: { fontSize: "0.9em" }, children: st?.running
                                    ? st.managed
                                        ? `运行中 · PID ${st.pid}${st.uptime_s ? ` · ${st.uptime_s}s` : ""}`
                                        : "运行中（由外部实例提供，非本插件启动）"
                                    : st?.error
                                        ? "未运行（上次启动出错）"
                                        : "未运行" }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy !== null || st?.running, onClick: doStart, children: busy === "start" ? "启动中…（可能需要 1–3 分钟冷启动）" : "启动并打开 DSH" }) }), st?.running && st?.url && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", onClick: () => openGui(st.url, cfg?.config?.open_with ?? "builtin"), children: "\u6253\u5F00 DSH \u754C\u9762\uFF08\u6309\u8BBE\u7F6E\u7684\u6253\u5F00\u65B9\u5F0F\uFF09" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy !== null, onClick: async () => {
                                        setBusy("ext");
                                        try {
                                            const res = await openExternal();
                                            if (res.ok) {
                                                toaster.toast({ title: "已在外部窗口打开", body: res.browser ?? "" });
                                            }
                                            else {
                                                toaster.toast({
                                                    title: "外部窗口打开失败",
                                                    body: (res.advice ?? res.reason ?? "").slice(0, 260),
                                                });
                                            }
                                        }
                                        catch (e) {
                                            toaster.toast({ title: "调用失败", body: String(e).slice(0, 260) });
                                        }
                                        finally {
                                            setBusy(null);
                                        }
                                    }, children: busy === "ext" ? "打开中…" : "用外部窗口打开（方案 B）" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy !== null, onClick: async () => {
                                        try {
                                            const res = await closeExternal();
                                            toaster.toast({
                                                title: res.closed ? "已关闭外部窗口" : "没有由本插件打开的外部窗口",
                                                body: res.closed ? "已向浏览器进程发送终止信号。" : "插件只关闭自己启动的那个窗口。",
                                            });
                                        }
                                        catch (e) {
                                            toaster.toast({ title: "关闭失败", body: String(e) });
                                        }
                                    }, children: "\u5173\u95ED\u5916\u90E8\u7A97\u53E3" }) })] })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy !== null || !st?.managed, onClick: doStop, children: busy === "stop" ? "停止中…" : "停止引擎" }) }), st?.error && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "\u4E0A\u6B21\u9519\u8BEF", value: st.error, warn: true }) }))] }), SP_JSX.jsxs(DFL.PanelSection, { title: "\u8DEF\u5F84", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "Node.js", value: cfg?.resolved?.node ?? "未找到 —— SteamOS 根目录只读，请装到 $HOME", warn: !cfg?.resolved?.node }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "dsh", value: cfg?.resolved?.dsh ?? "未找到", warn: !cfg?.resolved?.dsh }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "\u6765\u6E90", value: cfg?.resolved?.source ?? "-" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy !== null, onClick: doProbe, children: busy === "probe" ? "检测中…" : "环境自检（Node / bwrap / Landlock / 只读根）" }) }), probe && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "Node \u7248\u672C", value: probe.node?.version ?? "未知", warn: !probe.node?.version }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "\u6839\u6587\u4EF6\u7CFB\u7EDF", value: probe.root_readonly === null ? "未知" : probe.root_readonly ? "/ 只读（SteamOS 典型）" : "/ 可写" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "bwrap", value: probe.bwrap?.path ? (probe.bwrap.usable ? "可用" : `不可用：${probe.bwrap.reason ?? "probe 失败"}`) : "未安装", warn: !probe.bwrap?.usable }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "Landlock", value: String(probe.landlock?.usable ?? "不可用"), warn: !(probe.landlock?.usable === "full" || probe.landlock?.usable === "partial") }) }), verdict && !verdict.usable && verdict.advice && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "\u6C99\u7BB1\u4E0D\u53EF\u7528", value: verdict.advice, warn: true }) })), !probe.node?.path && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "Node \u672A\u627E\u5230", value: "插件进程只继承精简的 PATH，不会加载你登录 shell 的环境。\n" +
                                        "它看到的 PATH：" + (probe.path_env || "(空)") + "\n" +
                                        "试过的位置（均未命中）：\n" +
                                        ((probe.node?.tried ?? []).map((t) => "  " + t.path).join("\n") ||
                                            "(无记录)") +
                                        "\n→ 在下面「高级设置」里手动填写 Node 路径（发行版包通常在 /usr/bin/node，" +
                                        "Homebrew 在 /home/linuxbrew/.linuxbrew/bin/node）。", warn: true }) })), (probe.diagnostics ?? []).length > 0 && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "\u8BCA\u65AD", value: probe.diagnostics.join("\n") }) }))] }))] }), SP_JSX.jsxs(DFL.PanelSection, { title: "\u8BBE\u7F6E", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "\u7AEF\u53E3", value: String(cfg?.config?.port ?? 3080), mustBeNumeric: true, onChange: (e) => patch({ port: Number(e.target.value) || 3080 }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.DropdownItem, { label: "\u6253\u5F00\u65B9\u5F0F", description: "\u65B9\u6848 A\uFF1A\u8D70 Steam \u5185\u7F6E\u6D4F\u89C8\u5668\uFF1B\u65B9\u6848 B\uFF1A\u7528\u5916\u90E8\u6D4F\u89C8\u5668\u5F00\u72EC\u7ACB\u7A97\u53E3", rgOptions: [
                                { data: "builtin", label: "A · Steam 内置浏览器（面板内跳转）" },
                                { data: "external", label: "B · 外部浏览器独立窗口" },
                            ], selectedOption: cfg?.config?.open_with ?? "builtin", onChange: (opt) => patch({ open_with: String(opt.data) }) }) }), (cfg?.config?.open_with ?? "builtin") === "external" && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy !== null, onClick: async () => {
                                setBusy("bp");
                                try {
                                    const bp = await browserProbe();
                                    setBrowserInfo(bp);
                                    toaster.toast({
                                        title: bp.found ? "找到浏览器" : "未找到浏览器",
                                        body: bp.found
                                            ? `${bp.label}（${bp.family}）`
                                            : "请安装 Chromium/Chrome/Firefox 或 flatpak 版浏览器",
                                    });
                                }
                                catch (e) {
                                    toaster.toast({ title: "探测失败", body: String(e) });
                                }
                                finally {
                                    setBusy(null);
                                }
                            }, children: busy === "bp" ? "探测中…" : "探测可用浏览器" }) })), (cfg?.config?.open_with ?? "builtin") === "external" && browserInfo && (SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(Row, { label: "\u6D4F\u89C8\u5668", value: browserInfo.found
                                ? `${browserInfo.label}（${browserInfo.family}）`
                                : `未找到。已查找：${(browserInfo.candidates ?? []).join("、")}` +
                                    (browserInfo.flatpak ? "（flatpak 可用但无匹配应用）" : "（flatpak 未安装）"), warn: !browserInfo.found }) })), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "\u968F\u63D2\u4EF6\u52A0\u8F7D\u81EA\u52A8\u542F\u52A8", description: "\u63D2\u4EF6\u52A0\u8F7D\u65F6\u540E\u53F0\u62C9\u8D77\u5F15\u64CE\uFF08\u4ECD\u9700\u624B\u52A8\u6253\u5F00\u754C\u9762\uFF09", checked: Boolean(cfg?.config?.autostart), onChange: (v) => patch({ autostart: v }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "\u663E\u793A\u9AD8\u7EA7\u8BBE\u7F6E", checked: showAdvanced, onChange: setShowAdvanced }) }), showAdvanced && (SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "Node \u8DEF\u5F84\uFF08\u7559\u7A7A=\u81EA\u52A8\u67E5\u627E\uFF09", value: cfg?.config?.node_path ?? "", onChange: (e) => patch({ node_path: e.target.value }), description: "\u4F8B\u5982 /home/deck/.local/bin/node" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "dsh \u8DEF\u5F84\uFF08\u7559\u7A7A=\u81EA\u52A8\u67E5\u627E\uFF09", value: cfg?.config?.dsh_path ?? "", onChange: (e) => patch({ dsh_path: e.target.value }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "\u5DE5\u4F5C\u76EE\u5F55", value: cfg?.config?.workdir ?? "", onChange: (e) => patch({ workdir: e.target.value }), description: "Agent \u7684\u9ED8\u8BA4\u5DE5\u4F5C\u533A\uFF1B\u7559\u7A7A\u7528 $HOME" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "\u6743\u9650\u6863\u4F4D\uFF08DSH_PERMISSION_MODE\uFF09", value: cfg?.config?.permission_mode ?? "", onChange: (e) => patch({ permission_mode: e.target.value }), description: "\u7559\u7A7A\u7528 DSH \u9ED8\u8BA4\uFF1B\u6C99\u7BB1\u4E0D\u53EF\u7528\u65F6\u8BBE\u4E3A danger-full-access" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.DropdownItem, { label: "\u6743\u9650\u6863\u4F4D\u9884\u8BBE", rgOptions: [
                                        { data: "", label: "（留空，用 DSH 默认）" },
                                        { data: "danger-full-access", label: "danger-full-access（绕过沙箱）" },
                                        { data: "workspace-write", label: "workspace-write" },
                                        { data: "read-only", label: "read-only" },
                                    ], selectedOption: cfg?.config?.permission_mode ?? "", onChange: (opt) => patch({ permission_mode: String(opt.data) }) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "\u9644\u52A0\u53C2\u6570", value: cfg?.config?.extra_args ?? "", onChange: (e) => patch({ extra_args: e.target.value }), description: '\u8FFD\u52A0\u5230 dsh \u547D\u4EE4\u884C\uFF0C\u5982 --trusted-host deck.local' }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy !== null, onClick: doLog, children: busy === "log" ? "读取中…" : "查看引擎输出" }) })] }))] }), log.length > 0 && (SP_JSX.jsx(DFL.PanelSection, { title: "\u5F15\u64CE\u8F93\u51FA\uFF08\u6700\u8FD1\uFF09", children: SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("pre", { style: {
                            maxHeight: "200px",
                            overflow: "auto",
                            fontSize: "0.7em",
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-all",
                            margin: 0,
                            width: "100%",
                        }, children: log.join("\n") }) }) })), !known && (SP_JSX.jsx(DFL.PanelSection, { title: "\u9996\u6B21\u4F7F\u7528", children: SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("div", { style: { fontSize: "0.85em", lineHeight: 1.5 }, children: ["SteamOS \u6839\u6587\u4EF6\u7CFB\u7EDF\u53EA\u8BFB\uFF0C\u65E0\u6CD5 apt \u5B89\u88C5 Node\u3002\u8BF7\u5148\u628A Node.js \u88C5\u5230 $HOME\uFF1A", SP_JSX.jsx("br", {}), "1) \u5B89\u88C5 Node\uFF08nvm/fnm\uFF0C\u6216\u5B98\u65B9\u9884\u7F16\u8BD1\u5305\u89E3\u5230 ~/.local\uFF09", SP_JSX.jsx("br", {}), "2) ", SP_JSX.jsx("code", { children: "npm i -g @deepseek-ai/dsh" }), SP_JSX.jsx("br", {}), "3) \u56DE\u5230\u8FD9\u91CC\u70B9\u300C\u73AF\u5883\u81EA\u68C0\u300D\uFF0C\u786E\u8BA4\u8DEF\u5F84\u4E0E\u6C99\u7BB1"] }) }) }))] }));
}
var index = definePlugin(() => {
    const listener = addEventListener("dsh_status", (msg) => {
        toaster.toast({ title: "DSH", body: msg });
    });
    return {
        name: "DSH Launcher",
        titleView: SP_JSX.jsx("div", { className: DFL.staticClasses.Title, children: "DSH Launcher" }),
        content: SP_JSX.jsx(Content, {}),
        icon: SP_JSX.jsx(FaRocket, {}),
        onDismount() {
            // Intentionally no engine shutdown here: a plugin reload must not kill a
            // running agent session. Stop is an explicit user action.
            removeEventListener("dsh_status", listener);
        },
    };
});

export { index as default };
