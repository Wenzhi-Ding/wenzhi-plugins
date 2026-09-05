# wenzhi-plugins — agent rules

## 发布
- 开始发布前先运行 `command -v gh`、`gh auth status`，并检查 `git config --get user.name`、`git config --get user.email`。缺少 `gh`、未登录、身份为空或邮箱为 `<hostname>.local` 时，在 commit/tag 前处理；不把这些依赖留到 push 标签以后才发现。
- 改插件后同步 bump 两处版本号：`plugins/<name>/.zcode-plugin/plugin.json` 与根 `marketplace.json` 的 `version`，保持一致。
- Git 标签与 GitHub Release 标签统一用 `<插件名>-v<版本号>`，如 `humanize-v0.4.1`、`skill-stats-v0.1.0`；这个仓库的各插件独立使用版本号，不创建可能与其他插件冲突的仓库级 `v<版本号>` 标签。创建前同时检查本地和远端标签是否已存在。
- 生效链：commit + push GitHub → 插件管理里更新该插件 → 新会话加载（hook/插件改动不热加载，验证注入的方法见 zcode-tools 4.3）。交付时提醒用户走完这条链再验收。

## 测试
- 插件测试若会读取某个公开环境变量前缀（如 `HUMANIZE_*`、`SKILL_STATS_*`），构造子进程环境时先删除继承的同前缀变量，再设置测试默认值，最后应用当前用例的显式覆盖值。发布前至少用一个会改变默认行为的外部值运行整套测试，证明调用者环境不会改变测试结果。
- 插件包含 hook 时，冒烟测试必须从插件的 `hooks.json` 读取、展开并执行真实命令，覆盖清单 → shell/process → 解释器 → 脚本的完整启动链。直接用测试进程自身的解释器调用脚本只能算脚本测试，不能作为 hook 启动验证。
- hook 依赖 `node`、`python`、`python3`、`bash` 等外部命令时，发布前分别在目标桌面宿主环境验证命令可达性；不得用交互式终端的 PATH 代替 Finder、Explorer 启动的 ZCode 环境。需要跨平台回退时，测试至少覆盖每个回退入口和全部入口缺失。

## 提交
- `marketplace.json` 和根 `README.md` 是所有插件共享的登记文件。工作区带其他插件的未提交改动时，一笔提交只装一个插件的事；两边改动交叠进同一文件时，先临时撤回自己的改动、单独提交对方那笔、再恢复自己的改动提交（自己的改动可用 Edit 精确重放时适用）。
- 不是本会话产出的遗留改动，处置（提交/push）前先向用户交底并给建议，等拍板；确属完成本任务所必需（如不先提交对方改动就无法提交登记文件）时可以提交，但内容零改动、分笔单独提交，并在交付报告的显眼位置说明。
