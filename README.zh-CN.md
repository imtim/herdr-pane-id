# herdr-pane-id

[English](README.md) | **中文**

Herdr 插件：给每个 pane 打上短 pane ID（如 `pF`）标签，herdr 检测到 agent 后再加上 agent 名（`pi | pF`）——让你随时知道正在看的是哪个窗口，并能从任何地方按 id 定位它：`herdr pane run wP:pF ...`、`herdr agent prompt pi ...`，或从另一个 agent pane 里调用（与 [herdr agent skill](https://herdr.dev/docs/agent-skill/) 配合使用效果最佳）。

Tab 采用同样的紧凑形式：单 pane 的 tab 显示 `1_t1:p1`（数字、tab id、pane id）；加入第二个 pane 后切换为 `1_t1(2)`（pane 数量）。手动改名的 tab 保留你的名字并追加 tab id（`MyTab:t2`）。Workspace 显示 `Projects:wP`（名字 + id），herdr 启动后新建的 workspace 同样适用。

## 行为

不向 pane 里输入任何内容——标签只在 herdr 侧生效（`pane rename` / `tab rename` / `workspace rename`），屏幕保持完全干净。

| 事件 | 标签 |
| --- | --- |
| `pane.created` | `pF` |
| `pane.agent_detected`（有 agent） | `<agent-name> | pF` |
| `pane.agent_detected`（释放 / 退出） | `pF` |

Tab 标签（每个 pane/tab 事件及启动时校准）：

| Tab 状态 | Tab 标签 |
| --- | --- |
| 单 pane、默认编号 | `1_t1:p1` |
| 两个及以上 pane | `1_t1(2)`（pane 数量） |
| 手动命名（非数字） | `Name:tN`（保留名字，追加 tab id） |

基数始终取自 tab 自身的标签，所以 `1_t1:p1` 与 tab 栏显示保持一致。校准脚本（`tab-label.py`）幂等且可自愈：tab 里唯一的 pane 变化后，标签会在下一个事件更新。旧版插件格式（`3: t5: pP`、`3: pP`）自动升级。手动改名通过 `tab.renamed` 事件即时补上 `:tN`。

Workspace 标签（启动时、`workspace.created` / `workspace.renamed` / `workspace.updated` / `pane.closed` / `pane.moved` 事件，以及一个每几秒运行的小 watcher 循环时校准）：

| Workspace 状态 | Workspace 标签 |
| --- | --- |
| 自动管理 | `<derived>:wP` |
| 手动改名 | `<your-name>:wP`（后缀自动补回） |
| 旧格式 `Name: id` / `id Name` | 自动迁移为 `Name:id` |

自动管理的基底跟随 root pane 所在文件夹，推导规则与 herdr 原生一致：文件夹在 git 仓库内时取仓库根名，否则取文件夹名（`$HOME` 显示 `~`）。herdr 原生只在标签不是自定义名时跟随文件夹——一旦改名就永久钉死；本插件改为重新推导：任何状态下 `:wP` 后缀都可见，手动改名保留你的基底并在几秒内补回后缀。

为什么需要 watcher：herdr 在 pane 的 cwd 变化时不发任何事件（OSC 7 `cd` 报告只走渲染路径），所以文件夹跟随无法纯事件驱动。`workspace-sync.py` 在它能 hook 的每个 workspace/pane 事件上校准，另外由 startup hook 派生的独立 watcher（`--watch`）每 5 秒轮询以捕捉纯 `cd`。watcher 在 herdr 长时间不可达时自行退出，下次启动时重新派生；通过 pid 文件保证不重复。可用 `HERDR_PANE_ID_WATCHER=0` 关闭，用 `HERDR_PANE_ID_WATCH_INTERVAL`（秒）和 `HERDR_PANE_ID_WATCH_MAX_FAILS` 调节。

`<agent-name>` 是 `herdr agent start <name>` 指定的名字（即 `herdr agent prompt <name>` 寻址的名字），未命名 agent 回退为检测到的 agent 类型（`pi`、`codex`……）。

Pane 标签在任何状态下都保留 pane id：插件管理的 pane 显示 `pF` / `<agent> | pF`；手动改名的 pane 保留你的名字并追加 pane id（`MyPane:pF`）。herdr 对 pane 手动改名不发事件，因此 id 会在该 pane 的下一个 `pane.agent_detected` 事件或下次启动时补回（`on-pane-event.sh --reconcile`）；agent 名只注入插件管理的标签，绝不覆盖手动名。

## 零噪音的 pane 内提示符（推荐，可选）

herdr 已向每个 pane 注入 `HERDR_PANE_ID` 环境变量。在 `~/.zshrc`（或 `~/.bashrc`）加一行，每个提示符都会显示自己的 pane ID——无需插件事件、无需输入命令、agent pane 同样生效：

```zsh
[[ -n "${HERDR_PANE_ID:-}" ]] && PROMPT="[%{$reset_color%}$HERDR_PANE_ID] $PROMPT"
```

## 配置

herdr 没有内置的插件设置 API（plugin v1），因此本插件从配置目录读取 `config.toml`（路径由 `herdr plugin config-dir pane-id` 打印；环境变量 `$HERDR_PLUGIN_CONFIG_DIR`）。首次使用时自动播种一份带完整注释和示例的模板；修改在下一个事件或 watcher 周期生效——无需重启。

```toml
[behavior]
# 手动改名后 id 是否仍可见？
#   true  -> "MyName:wP" / "MyTab:t2" / "MyPane:pF"   （默认）
#   false -> 手动改名后隐藏 id
workspace = true
tab = true
pane = true

[format.workspace]
separator = ":"          # "trading-manager:wR" / "trading-manager_wR" / ...

[format.tab]
separator = ":"          # "1_t1:p1"（tab id 与 pane id 之间）
number_separator = "_"   # "1_t1:p1"（数字与 tab id 之间，"-" 得 "1-t1:p1"）

[format.pane]
separator = ":"          # "MyPane:pF"
```

每个 `always_visible` / `separator` 都是分类型的，可以混搭，例如 `workspace = false` 让 workspace 手动改名后隐藏 id，而 tab / pane 保留。`false` 只影响手动标签：自动管理标签（`pF`、`pi | pF`、`1_t1:p1`、`<derived>:wP`）始终显示 id。0.8 之前的扁平 `always_visible` / `separator` 键仍可用，统一作用于三类；配置切换后，旧分隔符写成的标签会自动迁移。

## 环境要求

- herdr >= 0.8.0
- python3（供 `tab-label.py` 与 `workspace-sync.py` 使用）

## 安装

从 GitHub 安装：

```bash
herdr plugin install imtim/herdr-pane-id
```

本地开发（改动即时生效，无需重新安装）：

```bash
git clone https://github.com/imtim/herdr-pane-id.git
herdr plugin link /path/to/herdr-pane-id
```

验证：

```bash
herdr plugin list
herdr plugin log list --plugin pane-id
```

调试日志（事件、解析出的 pane id、agent 名、改名失败、watcher）和同步状态（每个 workspace 的 `mode: auto|manual` 与插件最后写入的基底，保证手动名在校准后不丢失）存放在插件状态目录，macOS/Linux 通常为 `~/.local/state/herdr/plugins/pane-id/`：

```bash
cat "${HERDR_PLUGIN_STATE_DIR:-~/.local/state/herdr/plugins/pane-id}"/pane-id.log
cat "${HERDR_PLUGIN_STATE_DIR:-~/.local/state/herdr/plugins/pane-id}"/workspace-bases.json
```

## 发布到 herdr 市场

herdr 市场自动索引带 `herdr-plugin` 话题的公开 GitHub 仓库（每 30 分钟刷新）。要让插件以 `herdr plugin install <user>/herdr-pane-id` 安装，请在发布后在仓库设置中添加该话题。

## 卸载

```bash
herdr plugin unlink pane-id
```

## 备注

- 只有新建的 pane 会被打上纯 id 标签；已存在的 pane 保持原样，不会覆盖手动标题。已有 agent pane 在下一个 `pane.agent_detected` 事件时获得 agent 标签。手动 pane 名会被补上 `:pF`（启动校准或下一个 agent 事件），且永远不会被覆盖。
- Tab 标签在 `pane.created` / `pane.closed` / `pane.moved` / `tab.created` / `tab.renamed` / `pane.agent_detected` 及启动时校准——全量校准覆盖跨 tab 移动的 pane。手动 tab 名补上 `:tN`。
- Workspace 标签在 `workspace.created` / `workspace.renamed` / `workspace.updated` / `pane.closed` / `pane.moved`、启动时及 watcher 循环（默认每 5 秒）中校准。手动改名保留基底，并在 `workspace.renamed` 事件上立即补回 `:wP` 后缀。
- 自动基底取自 root pane（第一个 tab 中编号最小的 pane），与 herdr 自身的身份来源一致。
- `herdr agent rename` 不发事件，因此标签会保留旧名直到下一个检测事件（如 agent 退出或重启）。
- pane 移动到其他 workspace 时 pane ID 会变化；移动时不更新标签。
- Manifest 变更（新事件 hook）在下一次事件派发时生效（herdr 在运行 hook 前会重读插件注册表），但 `[[startup]]` hook 只在服务器启动时运行：安装或更新插件后请重启一次 herdr，让 workspace watcher 派生。脚本变更即时生效，因为 hook 每次事件都会重新读取脚本。
