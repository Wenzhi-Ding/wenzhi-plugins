#!/usr/bin/env bash
# humanize 插件的 UserPromptSubmit hook。
#
# 协议（ZCode）：stdout 输出单个 JSON 对象（以 { 开头）；退出码 0 放行；诊断信息写 stderr。
# 故意不读 stdin：宿主写入事件后不关闭管道，等 EOF 的读法会一直挂起到超时（zcode-tools 4.5）。
#
# 行为：
#   - 每轮注入完整规则：规则正文在 hooks/rules.txt，读入、JSON 转义后拼进 additionalContext。
#     正常路径无任何计数与状态文件。
#   - 开关：~/.zcode/humanize-off 存在时不注入（每次触发重新检查，中途生效）。
#   - 失败可见：规则文件缺失/为空时输出 systemMessage 提示（每会话一次）+ stderr 诊断，不注入。
#     去重标记存状态目录，会话键取宿主注入的 ZCODE_SESSION_ID，取不到时退化为全局键，
#     多会话并行时最多各多提示一次，无碍。
#
# 配置（环境变量）：
#   HUMANIZE_OFF_FILE     开关文件路径，默认 ~/.zcode/humanize-off
#   HUMANIZE_RULES_FILE   规则文件路径，默认随插件目录
#   HUMANIZE_STATE_DIR    状态目录（只存「缺失提示已发」标记），默认 $TMPDIR/humanize
#
# 手动冒烟测试（在仓库 plugins/humanize 目录下）：
#   bash hooks/humanize.sh                 # 每次运行都输出完整规则
#   touch ~/.zcode/humanize-off && bash hooks/humanize.sh   # 应无输出；测完 rm 掉开关文件
#   HUMANIZE_RULES_FILE=/nonexistent bash hooks/humanize.sh # 首次应输出带 systemMessage 的 JSON
#   stdin 保持打开不得挂起（zcode-tools 4.5.4）：
#     node -e "const{spawn}=require('child_process');const p=spawn('bash',['hooks/humanize.sh'],{stdio:['pipe','pipe','pipe']});const t=setTimeout(()=>{console.error('HANG');p.kill();process.exit(1)},5000);p.on('exit',c=>{clearTimeout(t);console.log('exited',c)})"

set -u

err() { printf 'humanize: %s\n' "$*" >&2; }

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES_FILE="${HUMANIZE_RULES_FILE:-$SELF_DIR/rules.txt}"
OFF_FILE="${HUMANIZE_OFF_FILE:-$HOME/.zcode/humanize-off}"
STATE_ROOT="${HUMANIZE_STATE_DIR:-${TMPDIR:-/tmp}/humanize}"

# 开关：文件存在即静默放行、不注入。
[ -f "$OFF_FILE" ] && exit 0

json_escape() {
  # JSON 字符串转义。顺序固定：先删 CR（Windows 行尾），再转义反斜杠、双引号、制表符、换行。
  local s="$1"
  s="${s//$'\r'/}"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\t'/\\t}"
  s="${s//$'\n'/\\n}"
  printf '%s' "$s"
}

emit_context() { # $1：已转义的 additionalContext 文本
  printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}\n' "$1"
}

# ---- 读规则；缺失/为空则可见地放行 ----------------------------------------
rules=""
if [ -r "$RULES_FILE" ]; then
  rules="$(tr -d '\r' < "$RULES_FILE")"
fi
if [ -z "$rules" ]; then
  err "规则文件缺失或为空：${RULES_FILE}，本轮未注入说人话规则。"
  session_key="${ZCODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
  session_key="$(printf '%s' "$session_key" | tr -cd 'A-Za-z0-9_-')"
  [ -n "$session_key" ] || session_key="shared"
  mkdir -p "$STATE_ROOT" 2>/dev/null || true
  find "$STATE_ROOT" -name '*.notified' -mtime +2 -delete 2>/dev/null || true
  notified="$STATE_ROOT/$session_key.notified"
  if [ -d "$STATE_ROOT" ] && [ ! -e "$notified" ] && : > "$notified" 2>/dev/null; then
    printf '{"systemMessage":"humanize: 规则文件缺失或为空（%s），本轮未注入说人话规则；本提示每会话只出现一次。"}\n' \
      "$(json_escape "$RULES_FILE")"
  fi
  exit 0
fi

emit_context "$(json_escape "$rules")"
exit 0
