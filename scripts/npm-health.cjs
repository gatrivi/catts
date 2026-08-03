#!/usr/bin/env node
"use strict";

const port = process.env.CATTS_API_PORT || "59200";
const url = `http://127.0.0.1:${port}/health`;

fetch(url)
  .then(async (r) => {
    const body = await r.text();
    console.log(r.status, body);
    process.exit(r.ok ? 0 : 1);
  })
  .catch((e) => {
    console.error("DOWN", url, e.message);
    process.exit(1);
  });
