#!/usr/bin/env node
/** Lift CATTS API (uvicorn). Prefer: npm start */
"use strict";

const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const root = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";
const py = isWin
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");

if (!fs.existsSync(py)) {
  console.error("Missing venv python:", py);
  console.error("Create it first, then: npm start");
  process.exit(1);
}

const host = process.env.CATTS_API_HOST || "0.0.0.0";
const port = process.env.CATTS_API_PORT || "59200";

console.log(`CATTS API → http://127.0.0.1:${port}/  (engine from .env)`);
const child = spawn(
  py,
  ["-m", "uvicorn", "api.main:app", "--host", host, "--port", String(port)],
  { cwd: root, stdio: "inherit", env: process.env }
);
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});
