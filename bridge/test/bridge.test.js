import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createServer, loadConfig, toAnthropic } from '../server.js';

// Fake Anthropic upstream that records the last request and replies per scenario.
let lastRequest;
const upstream = http.createServer((req, res) => {
  let raw = '';
  req.on('data', c => (raw += c));
  req.on('end', () => {
    if (req.url === '/health') { res.writeHead(200); return res.end('{}'); }
    if (req.url === '/v1/models') {
      res.writeHead(200, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({ data: [{ id: 'claude-opus-4-6-thinking' }] }));
    }
    lastRequest = { headers: req.headers, body: JSON.parse(raw) };
    const user = lastRequest.body.messages.at(-1).content.at(-1).text || '';
    if (user === 'rate') {
      res.writeHead(429, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({ error: { type: 'rate_limit_error', message: 'slow down' } }));
    }
    if (!lastRequest.body.stream) {
      res.writeHead(200, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({
        id: 'msg_1', stop_reason: 'tool_use', usage: { input_tokens: 10, output_tokens: 5 },
        content: [{ type: 'thinking', thinking: 'hmm' }, { type: 'text', text: 'Reading.' }, { type: 'tool_use', id: 'tu_1', name: 'read_file', input: { path: 'a.txt' } }],
      }));
    }
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const ev = o => res.write(`event: ${o.type}\ndata: ${JSON.stringify(o)}\n\n`);
    ev({ type: 'message_start', message: { usage: { input_tokens: 7 } } });
    ev({ type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } });
    ev({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Hel' } });
    ev({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'lo' } });
    ev({ type: 'content_block_stop', index: 0 });
    ev({ type: 'content_block_start', index: 1, content_block: { type: 'tool_use', id: 'tu_2', name: 'ls', input: {} } });
    ev({ type: 'content_block_delta', index: 1, delta: { type: 'input_json_delta', partial_json: '{"dir":' } });
    ev({ type: 'content_block_delta', index: 1, delta: { type: 'input_json_delta', partial_json: '"."}' } });
    ev({ type: 'content_block_stop', index: 1 });
    ev({ type: 'message_delta', delta: { stop_reason: 'tool_use' }, usage: { output_tokens: 3 } });
    ev({ type: 'message_stop' });
    res.end();
  });
});

let bridge, base;
before(async () => {
  await new Promise(r => upstream.listen(0, '127.0.0.1', r));
  const cfg = loadConfig({ UPSTREAM_URL: `http://127.0.0.1:${upstream.address().port}`, BRIDGE_API_KEY: 'secret', UPSTREAM_API_KEY: 'up' });
  bridge = createServer(cfg);
  await new Promise(r => bridge.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${bridge.address().port}`;
});
after(() => { bridge.close(); upstream.close(); });

const post = (body, key = 'secret') => fetch(`${base}/v1/chat/completions`, {
  method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${key}` }, body: JSON.stringify(body),
});

test('converts messages, tools and tool results to Anthropic format', () => {
  const req = toAnthropic({
    model: 'antigravity-claude-opus-4-6-thinking',
    messages: [
      { role: 'system', content: 'be brief' },
      { role: 'user', content: 'hi' },
      { role: 'assistant', content: null, tool_calls: [{ id: 'c1', type: 'function', function: { name: 'f', arguments: '{"x":1}' } }] },
      { role: 'tool', tool_call_id: 'c1', content: 'r1' },
      { role: 'user', content: [{ type: 'text', text: 'and?' }, { type: 'image_url', image_url: { url: 'data:image/png;base64,AAA' } }] },
    ],
    tools: [{ type: 'function', function: { name: 'f', parameters: { type: 'object' } } }],
    tool_choice: 'required',
  }, loadConfig({}));
  assert.equal(req.model, 'claude-opus-4-6-thinking');
  assert.equal(req.system, 'be brief');
  assert.deepEqual(req.messages.map(m => m.role), ['user', 'assistant', 'user']);
  assert.deepEqual(req.messages[1].content[0], { type: 'tool_use', id: 'c1', name: 'f', input: { x: 1 } });
  // tool_result and the following user text are merged into one user turn
  assert.equal(req.messages[2].content[0].type, 'tool_result');
  assert.equal(req.messages[2].content[2].source.media_type, 'image/png');
  assert.deepEqual(req.tool_choice, { type: 'any' });
  assert.equal(req.tools[0].input_schema.type, 'object');
});

test('rejects a wrong bridge key', async () => {
  const r = await post({ model: 'x', messages: [] }, 'nope');
  assert.equal(r.status, 401);
});

test('non-streaming reply maps text, reasoning, tool calls and usage', async () => {
  const r = await post({ model: 'antigravity-claude-opus-4-6-thinking', messages: [{ role: 'user', content: 'go' }] });
  assert.equal(r.status, 200);
  const j = await r.json();
  assert.equal(lastRequest.headers['x-api-key'], 'up');
  const c = j.choices[0];
  assert.equal(c.finish_reason, 'tool_calls');
  assert.equal(c.message.content, 'Reading.');
  assert.equal(c.message.reasoning_content, 'hmm');
  assert.deepEqual(JSON.parse(c.message.tool_calls[0].function.arguments), { path: 'a.txt' });
  assert.equal(j.model, 'antigravity-claude-opus-4-6-thinking');
  assert.equal(j.usage.total_tokens, 15);
});

test('streaming reply is converted to OpenAI chunks', async () => {
  const r = await post({ model: 'antigravity-x', stream: true, stream_options: { include_usage: true }, messages: [{ role: 'user', content: 'go' }] });
  const text = await r.text();
  const events = text.split('\n\n').filter(Boolean).map(e => e.replace(/^data: /, ''));
  assert.equal(events.at(-1), '[DONE]');
  const chunks = events.slice(0, -1).map(e => JSON.parse(e));
  const content = chunks.map(c => c.choices[0]?.delta?.content || '').join('');
  assert.equal(content, 'Hello');
  const args = chunks.flatMap(c => c.choices[0]?.delta?.tool_calls || []).map(t => t.function.arguments).join('');
  assert.deepEqual(JSON.parse(args), { dir: '.' });
  assert.ok(chunks.some(c => c.choices[0]?.finish_reason === 'tool_calls'));
  assert.equal(chunks.at(-1).usage.completion_tokens, 3);
});

test('upstream 429 is passed through so FreeLLMAPI fails over', async () => {
  const r = await post({ model: 'antigravity-x', messages: [{ role: 'user', content: 'rate' }] });
  assert.equal(r.status, 429);
  assert.equal((await r.json()).error.message, 'slow down');
});

test('models are listed with the antigravity- prefix', async () => {
  const r = await fetch(`${base}/v1/models`, { headers: { authorization: 'Bearer secret' } });
  const j = await r.json();
  assert.equal(j.data[0].id, 'antigravity-claude-opus-4-6-thinking');
});
