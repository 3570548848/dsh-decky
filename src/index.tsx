import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  TextField,
  ToggleField,
  Field,
  DropdownItem,
  Navigation,
  Router,
  staticClasses,
} from "@decky/ui";
import {
  addEventListener,
  callable,
  definePlugin,
  removeEventListener,
  toaster,
} from "@decky/api";
import { useEffect, useState } from "react";
import { FaRocket } from "react-icons/fa";

// ---------------------------------------------------------------------------
// Backend bindings (Python methods on the Plugin class in main.py)
// ---------------------------------------------------------------------------

type Resolved = { node: string | null; dsh: string | null; source: string };

type ConfigShape = {
  node_path: string;
  dsh_path: string;
  port: number;
  workdir: string;
  permission_mode: string;
  extra_args: string;
  autostart: boolean;
  open_with: string;
};

type ConfigReply = {
  config: ConfigShape;
  resolved: Resolved;
  home: string;
};

type StatusReply = {
  running: boolean;
  managed: boolean;
  url: string | null;
  port: number;
  pid: number | null;
  uptime_s: number | null;
  exit_code: number | null;
  error: string | null;
  resolved: Resolved;
};

type SandboxVerdict = {
  usable: boolean;
  runner?: string;
  enforcement?: string;
  advice?: string;
};

type ProbeReply = {
  node: {
    path: string | null;
    version?: string;
    source?: string | null;
    tried?: { path: string; found: string }[] | null;
  };
  dsh: { path: string | null; source: string };
  diagnostics: string[];
  path_env: string;
  cwd: string;
  root_readonly: boolean | null;
  bwrap: { path: string | null; usable: boolean; reason?: string; argv?: string[] } | null;
  landlock: { path: string | null; usable: string; reason?: string } | null;
  sandbox_verdict: SandboxVerdict;
};

const getConfig = callable<[], ConfigReply>("get_config");
const setConfig = callable<[patch: Partial<ConfigShape>], ConfigReply>("set_config");
const getStatus = callable<[], StatusReply>("status");
const startEngine = callable<[], { ok: boolean; url: string; reused?: boolean; port: number; note?: string }>("start");
const stopEngine = callable<[], { ok: boolean; stopped: boolean }>("stop");
const getLog = callable<[], { lines: string[] }>("get_log");
const probeEnv = callable<[], ProbeReply>("probe");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Open the DSH GUI in Steam's own browser.
 *
 * dsh authenticates the browser with a launch token in the query string, then
 * mints an `HttpOnly; SameSite=Strict` cookie bound to the exact authority.
 * Load-bearing consequence: the GUI must be opened as a top-level navigation in
 * a real browsing context. An <iframe> would be same-site-but-cross-origin and
 * would arrive without the cookie, so it is not an option (verified against
 * dsh-client-connection: sessionCookie() pins SameSite=Strict + HttpOnly).
 *
 * `Navigation.NavigateToExternalWeb` is the documented route into Steam's
 * built-in browser. `Router.NavigateToExternalWeb` is the same operation on the
 * other exported surface, kept as a fallback in case one is unavailable.
 */
function openGui(url: string) {
  const attempts: Array<[string, () => void]> = [
    ["Navigation", () => Navigation.NavigateToExternalWeb(url)],
    ["Router", () => (Router as any).NavigateToExternalWeb(url)],
  ];
  const errors: string[] = [];
  for (const [label, run] of attempts) {
    try {
      run();
      return;
    } catch (e) {
      errors.push(`${label}: ${String(e)}`);
    }
  }
  toaster.toast({ title: "打开失败", body: errors.join(" | ") });
}

function Row({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <Field label={label} childrenLayout="below" bottomSeparator="none">
      <div
        style={{
          fontFamily: "monospace",
          fontSize: "0.8em",
          wordBreak: "break-all",
          paddingTop: "2px",
          paddingBottom: "6px",
          color: warn ? "#ff8a80" : undefined,
        }}
      >
        {value}
      </div>
    </Field>
  );
}

// ---------------------------------------------------------------------------
// Content
// ---------------------------------------------------------------------------

function Content() {
  const [cfg, setCfg] = useState<ConfigReply | null>(null);
  const [status, setStatus] = useState<StatusReply | null>(null);
  const [probe, setProbe] = useState<ProbeReply | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const refresh = async () => {
    try {
      const [c, s] = await Promise.all([getConfig(), getStatus()]);
      setCfg(c);
      setStatus(s);
    } catch (e) {
      toaster.toast({ title: "读取状态失败", body: String(e) });
    }
  };

  useEffect(() => {
    refresh();
    const poll = setInterval(async () => {
      try {
        setStatus(await getStatus());
      } catch {
        /* keep last known status */
      }
    }, 4000);
    return () => clearInterval(poll);
  }, []);

  const patch = async (p: Partial<ConfigShape>) => {
    try {
      setCfg(await setConfig(p));
    } catch (e) {
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
      openGui(res.url);
    } catch (e) {
      toaster.toast({ title: "启动失败", body: String(e).slice(0, 400) });
      setLog((await getLog().catch(() => ({ lines: [] }))).lines);
    } finally {
      setBusy(null);
    }
  };

  const doStop = async () => {
    setBusy("stop");
    try {
      await stopEngine();
      await refresh();
    } catch (e) {
      toaster.toast({ title: "停止失败", body: String(e) });
    } finally {
      setBusy(null);
    }
  };

  const doProbe = async () => {
    setBusy("probe");
    try {
      setProbe(await probeEnv());
    } catch (e) {
      toaster.toast({ title: "环境自检失败", body: String(e) });
    } finally {
      setBusy(null);
    }
  };

  const doLog = async () => {
    setBusy("log");
    try {
      setLog((await getLog()).lines);
    } finally {
      setBusy(null);
    }
  };

  const st = status;
  const known = Boolean(cfg?.resolved?.node);
  const verdict = probe?.sandbox_verdict;

  return (
    <>
      <PanelSection title="引擎">
        <PanelSectionRow>
          <Field
            label="状态"
            childrenLayout="below"
          >
            <div style={{ fontSize: "0.9em" }}>
              {st?.running
                ? st.managed
                  ? `运行中 · PID ${st.pid}${st.uptime_s ? ` · ${st.uptime_s}s` : ""}`
                  : "运行中（由外部实例提供，非本插件启动）"
                : st?.error
                ? "未运行（上次启动出错）"
                : "未运行"}
            </div>
          </Field>
        </PanelSectionRow>

        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy !== null || st?.running} onClick={doStart}>
            {busy === "start" ? "启动中…（可能需要 1–3 分钟冷启动）" : "启动并打开 DSH"}
          </ButtonItem>
        </PanelSectionRow>

        {st?.running && st?.url && (
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => openGui(st.url as string)}>
              打开 DSH 界面
            </ButtonItem>
          </PanelSectionRow>
        )}

        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy !== null || !st?.managed} onClick={doStop}>
            {busy === "stop" ? "停止中…" : "停止引擎"}
          </ButtonItem>
        </PanelSectionRow>

        {st?.error && (
          <PanelSectionRow>
            <Row label="上次错误" value={st.error} warn />
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="路径">
        <PanelSectionRow>
          <Row
            label="Node.js"
            value={cfg?.resolved?.node ?? "未找到 —— SteamOS 根目录只读，请装到 $HOME"}
            warn={!cfg?.resolved?.node}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <Row label="dsh" value={cfg?.resolved?.dsh ?? "未找到"} warn={!cfg?.resolved?.dsh} />
        </PanelSectionRow>
        <PanelSectionRow>
          <Row label="来源" value={cfg?.resolved?.source ?? "-"} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy !== null} onClick={doProbe}>
            {busy === "probe" ? "检测中…" : "环境自检（Node / bwrap / Landlock / 只读根）"}
          </ButtonItem>
        </PanelSectionRow>
        {probe && (
          <>
            <PanelSectionRow>
              <Row label="Node 版本" value={probe.node?.version ?? "未知"} warn={!probe.node?.version} />
            </PanelSectionRow>
            <PanelSectionRow>
              <Row
                label="根文件系统"
                value={probe.root_readonly === null ? "未知" : probe.root_readonly ? "/ 只读（SteamOS 典型）" : "/ 可写"}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <Row
                label="bwrap"
                value={probe.bwrap?.path ? (probe.bwrap.usable ? "可用" : `不可用：${probe.bwrap.reason ?? "probe 失败"}`) : "未安装"}
                warn={!probe.bwrap?.usable}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <Row
                label="Landlock"
                value={String(probe.landlock?.usable ?? "不可用")}
                warn={!(probe.landlock?.usable === "full" || probe.landlock?.usable === "partial")}
              />
            </PanelSectionRow>
            {verdict && !verdict.usable && verdict.advice && (
              <PanelSectionRow>
                <Row label="沙箱不可用" value={verdict.advice} warn />
              </PanelSectionRow>
            )}
            {!probe.node?.path && (
              <PanelSectionRow>
                <Row
                  label="Node 未找到"
                  value={
                    "插件进程只继承精简的 PATH，不会加载你登录 shell 的环境。\n" +
                    "它看到的 PATH：" + (probe.path_env || "(空)") + "\n" +
                    "试过的位置（均未命中）：\n" +
                    ((probe.node?.tried ?? []).map((t) => "  " + t.path).join("\n") ||
                      "(无记录)") +
                    "\n→ 在下面「高级设置」里手动填写 Node 路径（发行版包通常在 /usr/bin/node，" +
                    "Homebrew 在 /home/linuxbrew/.linuxbrew/bin/node）。"
                  }
                  warn
                />
              </PanelSectionRow>
            )}
            {(probe.diagnostics ?? []).length > 0 && (
              <PanelSectionRow>
                <Row label="诊断" value={probe.diagnostics.join("\n")} />
              </PanelSectionRow>
            )}
          </>
        )}
      </PanelSection>

      <PanelSection title="设置">
        <PanelSectionRow>
          <TextField
            label="端口"
            value={String(cfg?.config?.port ?? 3080)}
            mustBeNumeric
            onChange={(e) => patch({ port: Number(e.target.value) || 3080 })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="随插件加载自动启动"
            description="插件加载时后台拉起引擎（仍需手动打开界面）"
            checked={Boolean(cfg?.config?.autostart)}
            onChange={(v) => patch({ autostart: v })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="显示高级设置"
            checked={showAdvanced}
            onChange={setShowAdvanced}
          />
        </PanelSectionRow>

        {showAdvanced && (
          <>
            <PanelSectionRow>
              <TextField
                label="Node 路径（留空=自动查找）"
                value={cfg?.config?.node_path ?? ""}
                onChange={(e) => patch({ node_path: e.target.value })}
                description="例如 /home/deck/.local/bin/node"
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <TextField
                label="dsh 路径（留空=自动查找）"
                value={cfg?.config?.dsh_path ?? ""}
                onChange={(e) => patch({ dsh_path: e.target.value })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <TextField
                label="工作目录"
                value={cfg?.config?.workdir ?? ""}
                onChange={(e) => patch({ workdir: e.target.value })}
                description="Agent 的默认工作区；留空用 $HOME"
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <TextField
                label="权限档位（DSH_PERMISSION_MODE）"
                value={cfg?.config?.permission_mode ?? ""}
                onChange={(e) => patch({ permission_mode: e.target.value })}
                description="留空用 DSH 默认；沙箱不可用时设为 danger-full-access"
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <DropdownItem
                label="权限档位预设"
                rgOptions={[
                  { data: "", label: "（留空，用 DSH 默认）" },
                  { data: "danger-full-access", label: "danger-full-access（绕过沙箱）" },
                  { data: "workspace-write", label: "workspace-write" },
                  { data: "read-only", label: "read-only" },
                ]}
                selectedOption={cfg?.config?.permission_mode ?? ""}
                onChange={(opt) => patch({ permission_mode: String(opt.data) })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <TextField
                label="附加参数"
                value={cfg?.config?.extra_args ?? ""}
                onChange={(e) => patch({ extra_args: e.target.value })}
                description='追加到 dsh 命令行，如 --trusted-host deck.local'
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" disabled={busy !== null} onClick={doLog}>
                {busy === "log" ? "读取中…" : "查看引擎输出"}
              </ButtonItem>
            </PanelSectionRow>
          </>
        )}
      </PanelSection>

      {log.length > 0 && (
        <PanelSection title="引擎输出（最近）">
          <PanelSectionRow>
            <pre
              style={{
                maxHeight: "200px",
                overflow: "auto",
                fontSize: "0.7em",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                margin: 0,
                width: "100%",
              }}
            >
              {log.join("\n")}
            </pre>
          </PanelSectionRow>
        </PanelSection>
      )}

      {!known && (
        <PanelSection title="首次使用">
          <PanelSectionRow>
            <div style={{ fontSize: "0.85em", lineHeight: 1.5 }}>
              SteamOS 根文件系统只读，无法 apt 安装 Node。请先把 Node.js 装到 $HOME：
              <br />
              1) 安装 Node（nvm/fnm，或官方预编译包解到 ~/.local）
              <br />
              2) <code>npm i -g @deepseek-ai/dsh</code>
              <br />
              3) 回到这里点「环境自检」，确认路径与沙箱
            </div>
          </PanelSectionRow>
        </PanelSection>
      )}
    </>
  );
}

export default definePlugin(() => {
  const listener = addEventListener<[msg: string]>("dsh_status", (msg) => {
    toaster.toast({ title: "DSH", body: msg });
  });

  return {
    name: "DSH Launcher",
    titleView: <div className={staticClasses.Title}>DSH Launcher</div>,
    content: <Content />,
    icon: <FaRocket />,
    onDismount() {
      // Intentionally no engine shutdown here: a plugin reload must not kill a
      // running agent session. Stop is an explicit user action.
      removeEventListener("dsh_status", listener);
    },
  };
});
