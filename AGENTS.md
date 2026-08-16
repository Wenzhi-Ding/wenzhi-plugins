# wenzhi-plugins — agent rules

## 发布
- 改插件后同步 bump 两处版本号：`plugins/<name>/.zcode-plugin/plugin.json` 与根 `marketplace.json` 的 `version`，保持一致。
- 生效链：commit + push GitHub → 插件管理里更新该插件 → 新会话加载（hook/插件改动不热加载，验证注入的方法见 zcode-tools 4.3）。交付时提醒用户走完这条链再验收。
