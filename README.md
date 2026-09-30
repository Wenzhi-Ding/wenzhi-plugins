# wenzhi-plugins

ZCode 插件市场。在 ZCode 的插件管理里添加本仓库即可一键安装下面的插件，各插件的完整说明见各自目录下的 README。

## 插件

### humanize

通过 UserPromptSubmit hook 在每条用户消息后注入一段「说人话」要求，抑制残句、翻译腔和空洞大词；会话回复和为用户起草的产出物（论文、报告、对外邮件等）都适用，可随时用开关文件关闭。

详见 [plugins/humanize/README.md](plugins/humanize/README.md)。

### skill-stats

统计每个技能（skill）被触发的次数，并区分触发来源：你在输入框敲 `/技能名` 触发，还是 agent 在任务中主动选择调用。在会话里输入 `/skill-stats` 查看统计表。数据存在 `~/.zcode/skill-stats/`，`~/.zcode/skill-stats-off` 文件存在时停止记录。

详见 [plugins/skill-stats/README.md](plugins/skill-stats/README.md)。

## 安装

要求：

- ZCode
- 本机可运行 `bash`（macOS/Linux 自带；Windows 用 Git Bash，ZCode 在 Windows 本身依赖它）——humanize 需要
- 本机已安装 Python 3——skill-stats 会依次尝试 `python3`、`python` 和 Windows 的 `py -3`

步骤：

1. 打开 ZCode → 设置 → 插件管理 → 发现
2. 点 `+` 添加 GitHub 仓库：`Wenzhi-Ding/wenzhi-plugins`
3. 在列表中找到想装的插件，点安装（默认启用，下个会话生效）

## 许可

[MIT](LICENSE)
