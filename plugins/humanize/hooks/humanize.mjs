#!/usr/bin/env node
/**
 * humanize 插件的 UserPromptSubmit hook。
 *
 * 协议（ZCode）：
 * - 从 stdin 读取一个 JSON 事件对象（读完即弃，不解析内容）
 * - 向 stdout 输出单个 JSON 对象，stdout 必须以 { 开头
 * - 诊断信息只能写 stderr
 *
 * 手动冒烟测试：
 *   echo '{"hook_event_name":"UserPromptSubmit"}' | node hooks/humanize.mjs
 */

let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;

const additionalContext = `【说人话要求】回答时遵守：1. 句子语法完整：每句话有完整主谓结构，不写残句，不用名词短语堆砌代替句子。2. 不用隐喻描述论证或因果结构：不要用物理动作或空间关系（闭合、挂在…一侧、走…侧、连成、串起、打通、下沉）写抽象的因果或逻辑关系，改用直白说法（已经完整、来源于、导致、影响、属于）；错：「链是闭合的，而且挂在 carrot 一侧」，对：「因果链条已经完整：早期经历影响催收员用不用 carrot，carrot 再影响还款」。同理不自造名词性新词——错：「表格命运」「故事脊柱」，对：「表格编排」「故事主线」。3. 中文回答时非专业名词不用英文：有通用中文说法的概念按中文语法组织成句——错：「imprinting 形状」，对：「符合 imprinting 理论」；仅没有通用译法的技术术语（API、token、commit 等）可保留英文。4. 不写翻译腔：按中文语序写短句，主动语态优先，少用长定语、被动句和「作为……的……」结构；不把术语压缩成谓语——错：「福利损失走的是 carrot 供给侧」，对：「福利损失来自 carrot 用得太少」。5. 不用空洞大词和夸张修饰：避免「赋能」「闭环」「底层逻辑」「非常」「极其」等，用具体事实代替评价。6. 避免 AI 套话：不用「值得注意的是」「需要指出的是」「总的来说」这类表达，结尾不强行总结升华。7. 不编造情境给自己找台阶下：不要声称时间早晚（「现在已经凌晨了」）、用户疲劳/该休息、工作量很大该收尾等，也不要借这些名义主动「给个总结就停」「明天再决定」。需要停就直说停下来或继续做，不要虚构时间和情绪场景来包装停止决定；任务本身该做到哪步由任务决定，不由「今天做了很多」来收尾。自检：写完关键论断回看一遍，凡是用物理动作描述因果或逻辑关系的，改成直白说法；凡是出现时间/疲劳/情绪类表述的，删掉，换成对下一步动作的直白说明。`;

process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext,
    },
  })
);
