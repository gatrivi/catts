import { appendFileSync } from 'node:fs';

export default function (pi) {
  const log = process.env.SMINI_LOOP_LOG;
  let previous = '';
  let repeats = 0;
  const canonical = value => {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
    }
    return value;
  };
  pi.on('tool_call', (event, ctx) => {
    const signature = JSON.stringify([event.toolName, canonical(event.input)]);
    repeats = signature === previous ? repeats + 1 : 1;
    previous = signature;
    if (log) appendFileSync(log, JSON.stringify({ call: event.toolName, repeats }) + '\n');
    if (repeats >= 2) {
      if (log) appendFileSync(log, JSON.stringify({ abort: 'identical consecutive tool call' }) + '\n');
      ctx.abort();
    }
  });
}
