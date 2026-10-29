#!/usr/bin/env node
// antigravity-bridge: exposes an OpenAI-compatible /v1/chat/completions endpoint
// and forwards it to an Anthropic Messages API (antigravity-claude-proxy).
// FreeLLMAPI custom providers speak OpenAI; the Antigravity proxy speaks
// Anthropic. This file is the translation layer between the two. Zero deps.

import http from 'node:http';
import { pathToFileURL } from 'node:url';

export function loadConfig(env = process.env) {
  return {
    host: env.BRIDGE_HOST || '127.0.0.1',
    port: Number(env.BRIDGE_PORT || 3005),
    upstream: (env.UPSTREAM_URL || 'http://127.0.0.1:8080').replace(/\/+$/, ''),
    upstreamKey: env.UPSTREAM_API_KEY || '',
    bridgeKey: env.BRIDGE_API_KEY || '',
    prefix: env.MODEL_PREFIX ?? 'antigravity-',
    defaultMaxTokens: Number(env.DEFAULT_MAX_TOKENS || 16384),
    timeoutMs: Number(env.REQUEST_TIMEOUT_MS || 600000),
  };
}

// ---------- OpenAI -> Anthropic ----------

function textOf(content) {
  if (content == null) return '';
  if (typeof content === 'string') return content;
  return content.filter(p => p.type === 'text').map(p => p.text).join('\n');
}

function convertPart(part) {
  if (part.type === 'text') return { type: 'text', text: part.text };
  if (part.type === 'image_url') {
    const url = typeof part.image_url === 'string' ? part.image_url : part.image_url?.url;
    const m = /^data:([^;]+);base64,(.*)$/s.exec(url || '');
    if (m) return { type: 'image', source: { type: 'base64', media_type: m[1], data: m[2] } };
    return { type: 'image', source: { type: 'url', url } };
  }
  return null;
}

function userBlocks(content) {
  if (typeof content === 'string') return content ? [{ type: 'text', text: content }] : [];
  return (content || []).map(convertPart).filter(Boolean);
}

function parseArgs(raw) {
  if (raw == null || raw === '') return {};
  if (typeof raw === 'object') return raw;
  try { return JSON.parse(raw); } catch { return { _raw: String(raw) }; }
}

export function toAnthropic(body, cfg) {
  const system = [];
  const out = [];
  const push = (role, blocks) => {
    if (!blocks.length) return;
    const last = out[out.length - 1];
    // Anthropic requires strictly alternating roles; merge consecutive turns.
    if (last && last.role === role) last.content.push(...blocks);
    else out.push({ role, content: [...blocks] });
  };

  for (const msg of body.messages || []) {
    switch (msg.role) {
      case 'system':
      case 'developer':
        system.push(textOf(msg.content));
        break;
      case 'user':
        push('user', userBlocks(msg.content));
        break;
      case 'assistant': {
        const blocks = [];
        const text = textOf(msg.content);
        if (text) blocks.push({ type: 'text', text });
        for (const tc of msg.tool_calls || []) {
          blocks.push({ type: 'tool_use', id: tc.id, name: tc.function?.name, input: parseArgs(tc.function?.arguments) });
        }
        push('assistant', blocks);
        break;
      }
      case 'tool':
        push('user', [{ type: 'tool_result', tool_use_id: msg.tool_call_id, content: textOf(msg.content) }]);
        break;
      default:
        break;
    }
  }

  const req = {
    model: stripPrefix(body.model, cfg.prefix),
    messages: out,
    max_tokens: body.max_completion_tokens || body.max_tokens || cfg.defaultMaxTokens,
    stream: !!body.stream,
  };
  const sys = system.filter(Boolean).join('\n\n');
  if (sys) req.system = sys;
  if (body.temperature != null) req.temperature = body.temperature;
  if (body.top_p != null) req.top_p = body.top_p;
  if (body.stop) req.stop_sequences = Array.isArray(body.stop) ? body.stop : [body.stop];

  const tools = (body.tools || []).filter(t => t.type === 'function' && t.function);
  if (tools.length) {
    req.tools = tools.map(t => ({
      name: t.function.name,
      description: t.function.description || '',
      input_schema: t.function.parameters || { type: 'object', properties: {} },
    }));
    const tc = body.tool_choice;
    if (tc === 'required') req.tool_choice = { type: 'any' };
    else if (tc === 'none') req.tool_choice = { type: 'none' };
    else if (tc && typeof tc === 'object' && tc.function?.name) req.tool_choice = { type: 'tool', name: tc.function.name };
  }
  return req;
}

function stripPrefix(model, prefix) {
  if (!model) return model;
  return prefix && model.startsWith(prefix) ? model.slice(prefix.length) : model;
}

// ---------- Anthropic -> OpenAI ----------

const FINISH = { end_turn: 'stop', stop_sequence: 'stop', max_tokens: 'length', tool_use: 'tool_calls', pause_turn: 'stop', refusal: 'content_filter' };

function usageOf(u = {}) {
  const prompt = (u.input_tokens || 0) + (u.cache_read_input_tokens || 0) + (u.cache_creation_input_tokens || 0);
  const completion = u.output_tokens || 0;
  return { prompt_tokens: prompt, completion_tokens: completion, total_tokens: prompt + completion };
}

export function toOpenAI(msg, requestedModel) {
  let text = '';
  let reasoning = '';
  const toolCalls = [];
  for (const block of msg.content || []) {
    if (block.type === 'text') text += block.text;
    else if (block.type === 'thinking') reasoning += block.thinking || '';
    else if (block.type === 'tool_use') {
      toolCalls.push({ id: block.id, type: 'function', function: { name: block.name, arguments: JSON.stringify(block.input ?? {}) } });
    }
  }
  const message = { role: 'assistant', content: text || (toolCalls.length ? null : '') };
  if (toolCalls.length) message.tool_calls = toolCalls;
  if (reasoning) message.reasoning_content = reasoning;
  return {
    id: `chatcmpl-${msg.id || Date.now()}`,
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model: requestedModel,
    choices: [{ index: 0, message, finish_reason: FINISH[msg.stop_reason] || 'stop' }],
    usage: usageOf(msg.usage),
  };
}

// Converts an Anthropic SSE stream into OpenAI chat.completion.chunk events.
export function createStreamConverter(requestedModel, includeUsage, write) {
  const id = `chatcmpl-${Date.now()}`;
  const created = Math.floor(Date.now() / 1000);
  const toolIndex = new Map(); // anthropic block index -> openai tool_calls index
  let usage = {};
  let finish = null;
  let started = false;

  const chunk = (delta, finishReason = null, extra = {}) =>
    write(`data: ${JSON.stringify({ id, object: 'chat.completion.chunk', created, model: requestedModel, choices: [{ index: 0, delta, finish_reason: finishReason }], ...extra })}\n\n`);

  const start = () => { if (!started) { started = true; chunk({ role: 'assistant', content: '' }); } };

  function handle(event) {
    switch (event.type) {
      case 'message_start':
        usage = { ...usage, ...(event.message?.usage || {}) };
        start();
        break;
      case 'content_block_start': {
        start();
        const b = event.content_block || {};
        if (b.type === 'tool_use') {
          const idx = toolIndex.size;
          toolIndex.set(event.index, idx);
          chunk({ tool_calls: [{ index: idx, id: b.id, type: 'function', function: { name: b.name, arguments: '' } }] });
        } else if (b.type === 'text' && b.text) {
          chunk({ content: b.text });
        }
        break;
      }
      case 'content_block_delta': {
        const d = event.delta || {};
        if (d.type === 'text_delta') chunk({ content: d.text });
        else if (d.type === 'thinking_delta') chunk({ reasoning_content: d.thinking });
        else if (d.type === 'input_json_delta' && toolIndex.has(event.index)) {
          chunk({ tool_calls: [{ index: toolIndex.get(event.index), function: { arguments: d.partial_json } }] });
        }
        break;
      }
      case 'message_delta':
        if (event.delta?.stop_reason) finish = FINISH[event.delta.stop_reason] || 'stop';
        usage = { ...usage, ...(event.usage || {}) };
        break;
      case 'message_stop':
        finishStream();
        break;
      case 'error':
        throw Object.assign(new Error(event.error?.message || 'upstream stream error'), { upstreamType: event.error?.type });
      default:
        break;
    }
  }

  let done = false;
  function finishStream() {
    if (done) return;
    done = true;
    start();
    chunk({}, finish || 'stop');
    if (includeUsage) write(`data: ${JSON.stringify({ id, object: 'chat.completion.chunk', created, model: requestedModel, choices: [], usage: usageOf(usage) })}\n\n`);
    write('data: [DONE]\n\n');
  }

  let buffer = '';
  return {
    push(text) {
      buffer += text;
      let sep;
      while ((sep = buffer.search(/\r?\n\r?\n/)) !== -1) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep).replace(/^\r?\n\r?\n/, '');
        const data = raw.split(/\r?\n/).filter(l => l.startsWith('data:')).map(l => l.slice(5).trimStart()).join('\n');
        if (!data || data === '[DONE]') continue;
        let event;
        try { event = JSON.parse(data); } catch { continue; }
        handle(event);
      }
    },
    end() { finishStream(); },
  };
}

// ---------- HTTP server ----------

function sendJson(res, status, obj) {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(obj));
}

function openAIError(res, status, message, type = 'upstream_error') {
  sendJson(res, status, { error: { message, type, code: status } });
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function upstreamHeaders(cfg) {
  const h = { 'content-type': 'application/json', 'anthropic-version': '2023-06-01' };
  if (cfg.upstreamKey) { h['x-api-key'] = cfg.upstreamKey; h.authorization = `Bearer ${cfg.upstreamKey}`; }
  return h;
}

function authorized(req, cfg) {
  if (!cfg.bridgeKey) return true;
  const bearer = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  return bearer === cfg.bridgeKey || req.headers['x-api-key'] === cfg.bridgeKey;
}

async function handleModels(res, cfg) {
  const r = await fetch(`${cfg.upstream}/v1/models`, { headers: upstreamHeaders(cfg) });
  if (!r.ok) return openAIError(res, r.status, `upstream /v1/models: ${await r.text()}`);
  const data = await r.json();
  const created = Math.floor(Date.now() / 1000);
  sendJson(res, 200, {
    object: 'list',
    data: (data.data || []).map(m => ({ id: `${cfg.prefix}${m.id}`, object: 'model', created, owned_by: 'antigravity' })),
  });
}

async function handleChat(req, res, cfg) {
  let body;
  try { body = JSON.parse(await readBody(req)); } catch { return openAIError(res, 400, 'invalid JSON body', 'invalid_request_error'); }
  if (!Array.isArray(body.messages)) return openAIError(res, 400, '`messages` must be an array', 'invalid_request_error');

  const requestedModel = body.model;
  const payload = toAnthropic(body, cfg);
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), cfg.timeoutMs);
  res.on('close', () => { if (!res.writableEnded) ac.abort(); });

  let upstream;
  try {
    upstream = await fetch(`${cfg.upstream}/v1/messages`, { method: 'POST', headers: upstreamHeaders(cfg), body: JSON.stringify(payload), signal: ac.signal });
  } catch (err) {
    clearTimeout(timer);
    return openAIError(res, 502, `cannot reach Antigravity proxy at ${cfg.upstream}: ${err.message}`);
  }

  if (!upstream.ok) {
    clearTimeout(timer);
    const text = await upstream.text();
    let message = text;
    try { message = JSON.parse(text).error?.message || text; } catch {}
    // Keep the status code: FreeLLMAPI fails over on 429/5xx.
    return openAIError(res, upstream.status, message);
  }

  if (!payload.stream) {
    const msg = await upstream.json();
    clearTimeout(timer);
    return sendJson(res, 200, toOpenAI(msg, requestedModel));
  }

  res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' });
  const conv = createStreamConverter(requestedModel, !!body.stream_options?.include_usage, s => res.write(s));
  const decoder = new TextDecoder();
  try {
    for await (const part of upstream.body) conv.push(decoder.decode(part, { stream: true }));
    conv.end();
  } catch (err) {
    if (!ac.signal.aborted) res.write(`data: ${JSON.stringify({ error: { message: err.message, type: err.upstreamType || 'upstream_error' } })}\n\n`);
  } finally {
    clearTimeout(timer);
    res.end();
  }
}

export function createServer(cfg = loadConfig()) {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://bridge');
    try {
      if (req.method === 'GET' && url.pathname === '/health') {
        let upstream = 'down';
        try { upstream = (await fetch(`${cfg.upstream}/health`, { signal: AbortSignal.timeout(3000) })).ok ? 'ok' : 'error'; } catch {}
        return sendJson(res, upstream === 'ok' ? 200 : 503, { status: upstream === 'ok' ? 'ok' : 'degraded', upstream, upstreamUrl: cfg.upstream });
      }
      if (!authorized(req, cfg)) return openAIError(res, 401, 'invalid bridge API key', 'authentication_error');
      if (req.method === 'GET' && url.pathname === '/v1/models') return await handleModels(res, cfg);
      if (req.method === 'POST' && url.pathname === '/v1/chat/completions') return await handleChat(req, res, cfg);
      return openAIError(res, 404, `no route for ${req.method} ${url.pathname}`, 'not_found');
    } catch (err) {
      if (!res.headersSent) openAIError(res, 500, err.message, 'bridge_error');
      else res.end();
    }
  });
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const cfg = loadConfig();
  createServer(cfg).listen(cfg.port, cfg.host, () => {
    console.log(`antigravity-bridge listening on http://${cfg.host}:${cfg.port} -> ${cfg.upstream}`);
  });
}
