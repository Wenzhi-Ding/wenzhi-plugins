#!/usr/bin/env bash
# humanize 插件的 UserPromptSubmit hook。
#
# 协议（ZCode）：stdout 输出单个 JSON 对象（以 { 开头）；退出码 0 放行；诊断信息写 stderr。
# 故意不读 stdin：宿主写入事件后不关闭管道，等 EOF 的读法会一直挂起到超时（zcode-tools 4.5）。
#
# 行为：
#   - 规则正文在 hooks/rules.txt，本脚本读入、做 JSON 转义后拼进 additionalContext。
#   - 每轮注入完整规则（默认）。HUMANIZE_EVERY 设为大于 1 的值时改回隔轮：每会话第 1 轮
#     全量注入，此后每 HUMANIZE_EVERY 轮再全量一次，其余轮只注入一行提醒。
#   - 会话标识用环境变量 ZCODE_SESSION_ID（宿主给 hook 子进程注入），取不到时退回全局计数，
#     多个会话并行时会互相当轮次，属可接受的降级。
#   - 开关：~/.zcode/humanize-off 存在时不注入（每次触发重新检查，中途生效）。
#   - 失败可见：规则文件缺失/为空时输出 systemMessage 提示（每会话一次）+ stderr 诊断，不注入。
#
# 配置（环境变量）：
#   HUMANIZE_EVERY        隔几轮注入一次完整规则，默认 1（每轮注入）；设为大于 1 的值改回隔轮
#   HUMANIZE_OFF_FILE     开关文件路径，默认 ~/.zcode/humanize-off
#   HUMANIZE_RULES_FILE   规则文件路径，默认随插件目录
#   HUMANIZE_STATE_DIR    计数状态目录，默认 $TMPDIR/humanize
#   HUMANIZE_DEBUG        1 = 往 stderr 写一行运行诊断（会话键、轮次、模式）
#
# 手动冒烟测试（在仓库 plugins/humanize 目录下）：
#   bash hooks/humanize.sh                 # 第 1 次输出完整规则
#   bash hooks/humanize.sh                 # 连跑几次：每次都输出完整规则（默认 EVERY=1）
#   HUMANIZE_EVERY=4 bash hooks/humanize.sh   # 连跑 8 次：第 1、5 次输出完整规则，其余输出提醒
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
EVERY="${HUMANIZE_EVERY:-1}"
DEBUG="${HUMANIZE_DEBUG:-0}"

case "$EVERY" in ''|*[!0-9]*|0) EVERY=1 ;; esac

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

REMINDER='【说人话要求·提醒】说人话规则本轮继续生效，完整规则见本会话前文的「【说人话要求】」条目：概念性「为什么/是什么」先给最短充分答案，核心问题答完就停；复杂任务不套固定长度；写完整句子；不用物理动作或空间关系写因果；不把多词说法压成自造短词，标签拿掉上下文要还能懂；不写翻译腔，转述外文材料时源的隐喻先拆成平白意义；不用 AI 套话和空洞大词；论断配具体量级；术语先用白话讲清、再挂名字。'

# ---- 会话标识 --------------------------------------------------------------
session_key="${ZCODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
session_key="$(printf '%s' "$session_key" | tr -cd 'A-Za-z0-9_-')"
[ -n "$session_key" ] || session_key="shared"

# ---- 读规则；缺失/为空则可见地放行 ----------------------------------------
rules=""
if [ -r "$RULES_FILE" ]; then
  rules="$(tr -d '\r' < "$RULES_FILE")"
fi
if [ -z "$rules" ]; then
  err "规则文件缺失或为空：$RULES_FILE，本轮未注入说人话规则。"
  mkdir -p "$STATE_ROOT" 2>/dev/null || true
  notified="$STATE_ROOT/$session_key.notified"
  if [ -d "$STATE_ROOT" ] && [ ! -e "$notified" ] && : > "$notified" 2>/dev/null; then
    printf '{"systemMessage":"humanize: 规则文件缺失或为空（%s），本轮未注入说人话规则；本提示每会话只出现一次。"}\n' \
      "$(json_escape "$RULES_FILE")"
  fi
  exit 0
fi

# ---- 隔轮计数 --------------------------------------------------------------
inject_full=1
turn=1
if [ "$EVERY" -gt 1 ] && mkdir -p "$STATE_ROOT" 2>/dev/null && [ -d "$STATE_ROOT" ]; then
  cnt_file="$STATE_ROOT/$session_key.count"
  if [ -f "$cnt_file" ]; then
    now=$(date +%s)
    mt=$(date -r "$cnt_file" +%s 2>/dev/null || printf '%s' "$now")
    if [ $((now - mt)) -lt 21600 ]; then   # 6 小时内的计数才续用，更久视为新会话
      old=$(cat "$cnt_file" 2>/dev/null)
      case "$old" in ''|*[!0-9]*) old=0 ;; esac
      turn=$((old + 1))
    fi
  fi
  # 写失败就保持 inject_full=1：宁可每轮完整注入，也不能卡在提醒上漏掉规则。
  if printf '%s\n' "$turn" > "$cnt_file" 2>/dev/null; then
    if [ $(( (turn - 1) % EVERY )) -ne 0 ]; then
      inject_full=0
    fi
  fi
  find "$STATE_ROOT" -name '*.count' -mtime +2 -delete 2>/dev/null || true
  find "$STATE_ROOT" -name '*.notified' -mtime +2 -delete 2>/dev/null || true
fi

if [ "$DEBUG" = "1" ]; then
  mode=full; [ "$inject_full" = 1 ] || mode=reminder
  err "key=$session_key turn=$turn every=$EVERY mode=$mode rules_bytes=${#rules}"
fi

if [ "$inject_full" = 1 ]; then
  emit_context "$(json_escape "$rules")"
else
  emit_context "$(json_escape "$REMINDER")"
fi
exit 0
