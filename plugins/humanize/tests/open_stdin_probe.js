#!/usr/bin/env node

const { spawn } = require("child_process");

const [bash, script] = process.argv.slice(2);
if (!bash || !script) {
  console.error("usage: node open_stdin_probe.js <bash> <script>");
  process.exit(2);
}

const child = spawn(bash, [script], { stdio: ["pipe", "pipe", "pipe"] });
let stdout = "";
let stderr = "";
child.stdout.setEncoding("utf8");
child.stderr.setEncoding("utf8");
child.stdout.on("data", (chunk) => { stdout += chunk; });
child.stderr.on("data", (chunk) => { stderr += chunk; });

let timedOut = false;
const timer = setTimeout(() => {
  timedOut = true;
  child.kill();
  setTimeout(() => child.kill("SIGKILL"), 1000).unref();
}, 5000);

child.on("error", (error) => {
  clearTimeout(timer);
  console.error(error.message);
  process.exit(1);
});

child.on("close", (code) => {
  clearTimeout(timer);
  process.stdout.write(stdout);
  process.stderr.write(stderr);
  if (timedOut) {
    console.error("humanize 在 stdin 保持打开时挂起");
    process.exit(1);
  }
  process.exit(code ?? 1);
});
