#!/usr/bin/env node
/** Stop CATTS API. Prefer: npm stop   · free more RAM: npm run stop:heavy */
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

const heavy = process.argv.includes("--heavy");
const script = path.join(__dirname, "stop_api.ps1");
const args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script];
if (heavy) args.push("-Heavy");

const r = spawnSync("powershell.exe", args, { stdio: "inherit" });
process.exit(r.status ?? 1);
