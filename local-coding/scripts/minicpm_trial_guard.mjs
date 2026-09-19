import { appendFileSync, readFileSync, realpathSync } from 'node:fs';
import path from 'node:path';

export default function (pi) {
  const root = realpathSync(process.env.MINICPM_TRIAL_ROOT);
  const log = process.env.MINICPM_TRIAL_GUARD_LOG;
  const writable = new Set(JSON.parse(process.env.MINICPM_TRIAL_WRITABLE || '[]'));
  const seen = new Set();
  let previous = '';
  let repeats = 0;
  let calls = 0;
  const canonical = value => {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
    }
    return value;
  };
  const relative = input => {
    const target = realpathSync(path.resolve(root, input || '.'));
    const name = path.relative(root, target).replaceAll('\\', '/');
    if (name === '..' || name.startsWith('../') || path.isAbsolute(name)) throw new Error('outside fixture');
    return name;
  };
  appendFileSync(log, JSON.stringify({ type: 'guard_ready' }) + '\n');
  pi.on('tool_call', (event, ctx) => {
    let reason = '';
    let fatal = false;
    const signature = JSON.stringify([event.toolName, canonical(event.input)]);
    repeats = signature === previous ? repeats + 1 : 1;
    previous = signature;
    calls += 1;
    if (repeats >= 2 || calls > 24) {
      reason = repeats >= 2 ? 'identical consecutive tool calls' : 'tool call limit';
      fatal = true;
    }
    try {
      if (!['read', 'grep', 'glob', 'write'].includes(event.toolName)) throw new Error('tool not allowed');
      const name = relative(event.input.path);
      if (event.toolName === 'write') {
        if (!writable.has(name) || !seen.has(name)) throw new Error('protected or unread file');
        if (typeof event.input.content !== 'string' || event.input.content.length > 20000) throw new Error('invalid content');
      }
      if (event.toolName === 'read') readFileSync(path.join(root, name));
    } catch (error) {
      reason = reason || error.message;
    }
    appendFileSync(log, JSON.stringify({ type: 'call', name: event.toolName, input: event.input, blocked: !!reason, reason }) + '\n');
    if (fatal) ctx.abort();
    if (reason) return { block: true, reason };
  });
  pi.on('tool_result', event => {
    if (event.toolName === 'read' && !event.isError) {
      try { seen.add(relative(event.input.path)); } catch {}
    }
    appendFileSync(log, JSON.stringify({ type: 'result', name: event.toolName, isError: event.isError }) + '\n');
  });
}
