import test from 'node:test';
import assert from 'node:assert/strict';
import { generateAnswer } from '../src/services/llm.service.js';
import { submitQuery } from '../src/controllers/query.controller.js';
import Document from '../src/models/Document.js';
import QueryHistory from '../src/models/QueryHistory.js';

const input = { provider: 'gemini', context: 'NAME: Demo User\nACCOUNT: 000123\nBRANCH: 0012', question: 'List exact account fields.' };
const body = { modelVersion: 'gemini-test', candidates: [{ finishReason: 'STOP', content: { parts: [
  { thought: true, text: 'Internal thoughts must not be displayed.' }, { text: 'Demo User | 000123 | 0012' },
] } }], usageMetadata: { promptTokenCount: 80, candidatesTokenCount: 12, totalTokenCount: 100, thoughtsTokenCount: 8 } };
const ok = async () => ({ ok: true, json: async () => body });
const options = { apiKey: 'test-gemini-key', model: 'gemini-test', fetchImpl: ok };

test('selected Gemini request preserves context, puts key in header, and maps usage', async () => {
  const result = await generateAnswer(input, { ...options, fetchImpl: async (url, request) => {
    assert.match(url, /generativelanguage.googleapis.com\/v1beta\/models\/gemini-test:generateContent$/);
    assert.doesNotMatch(url, /test-gemini-key/);
    assert.equal(request.headers['x-goog-api-key'], 'test-gemini-key');
    const data = JSON.parse(request.body);
    assert.match(data.contents[0].parts[0].text, /ACCOUNT: 000123/);
    assert.match(data.contents[0].parts[0].text, /BRANCH: 0012/);
    assert.match(data.contents[0].parts[0].text, /List exact account fields/);
    return ok();
  } });
  assert.equal(result.provider, 'gemini');
  assert.equal(result.answer, 'Demo User | 000123 | 0012');
  assert.deepEqual(result.tokenStats, { inputTokens: 80, outputTokens: 12, totalTokens: 100, thinkingTokens: 8 });
});

test('Gemini reports missing keys and input without a request', async () => {
  await assert.rejects(generateAnswer(input, { ...options, apiKey: '' }), /not configured/);
  await assert.rejects(generateAnswer({ ...input, context: ' ' }, options), /Process a document/);
});

test('Gemini errors are useful and never expose raw keys or error messages', async () => {
  for (const [status, reason, expected] of [[400, 'API_KEY_INVALID', /rejected/], [403, '', /denied/], [429, '', /quota/], [404, '', /model is unavailable/], [503, '', /high demand/]]) {
    await assert.rejects(generateAnswer(input, { ...options, fetchImpl: async () => ({ ok: false, status,
      json: async () => ({ error: { message: 'test-gemini-key secret', details: [{ reason }] } }),
    }) }), error => expected.test(error.message) && !error.message.includes('test-gemini-key'));
  }
});

test('Gemini never displays blocked, empty or truncated responses as success', async () => {
  for (const data of [{ candidates: [] }, { candidates: [{ finishReason: 'MAX_TOKENS' }] }]) {
    await assert.rejects(generateAnswer(input, { ...options, fetchImpl: async () => ({ ok: true, json: async () => data }) }));
  }
});

test('query route uses Gemini for a saved document and saves its actual provider', async () => {
  const oldFind = Document.findOne, oldCreate = QueryHistory.create, oldFetch = globalThis.fetch;
  const oldKey = process.env.GEMINI_API_KEY;
  try {
    process.env.GEMINI_API_KEY = 'test-gemini-key';
    Document.findOne = async () => ({ status: 'ready', pipelineResult: { finalContext: input.context } });
    QueryHistory.create = async record => {
      assert.equal(record.llmProvider, 'gemini');
      assert.equal(record.model, 'gemini-test');
      assert.equal(record.totalTokens, 100);
      return { _id: 'history' };
    };
    globalThis.fetch = ok;
    let status, payload;
    const res = { status(code) { status = code; return this; }, json(data) { payload = data; return this; } };
    await submitQuery({ user: { _id: 'test-user' }, body: { documentId: '0123456789abcdef01234567', llmProvider: 'gemini', question: input.question } }, res);
    assert.equal(status, 200);
    assert.equal(payload.data.provider, 'gemini');
    assert.equal(payload.data.answer, 'Demo User | 000123 | 0012');
  } finally {
    Document.findOne = oldFind; QueryHistory.create = oldCreate; globalThis.fetch = oldFetch;
    if (oldKey === undefined) delete process.env.GEMINI_API_KEY; else process.env.GEMINI_API_KEY = oldKey;
  }
});
