import test from 'node:test';
import assert from 'node:assert/strict';
import { generateAnswer } from '../src/services/openai.service.js';
import { submitQuery } from '../src/controllers/query.controller.js';
import Document from '../src/models/Document.js';
import QueryHistory from '../src/models/QueryHistory.js';

const fakeBody = {
  status: 'completed', model: 'gpt-4o-mini',
  output: [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'Test Holder: account 000123, branch 0012.' }] }],
  usage: { input_tokens: 80, output_tokens: 15, total_tokens: 95 },
};
const ok = async () => ({ ok: true, json: async () => fakeBody });
const options = { apiKey: 'unit-test-key', fetchImpl: ok };
const input = { context: 'NAME: Test Holder\nACCOUNT: 000123\nBRANCH: 0012', question: 'List the exact fields.' };

test('Responses request sends only optimized context and returns real token usage', async () => {
  const result = await generateAnswer(input, { ...options, fetchImpl: async (url, request) => {
    assert.equal(url, 'https://api.openai.com/v1/responses');
    const body = JSON.parse(request.body);
    assert.equal(body.store, false);
    assert.match(body.input[0].content, /ACCOUNT: 000123/);
    assert.match(body.input[0].content, /BRANCH: 0012/);
    assert.equal(body.input[1].content, input.question);
    assert.equal(body.model, 'gpt-4o-mini');
    return ok();
  } });
  assert.equal(result.answer, fakeBody.output[0].content[0].text);
  assert.deepEqual(result.tokenStats, { inputTokens: 80, outputTokens: 15, totalTokens: 95 });
});

test('OpenAI helper rejects other providers without a network call', async () => {
  await assert.rejects(generateAnswer({ ...input, provider: 'gemini' }, {
    ...options, fetchImpl: () => assert.fail('Gemini must not make requests'),
  }), /Unsupported provider/);
});

test('empty context and missing configuration fail before network access', async () => {
  await assert.rejects(generateAnswer({ context: ' ' }, options), /Process a document/);
  await assert.rejects(generateAnswer(input, { ...options, apiKey: '' }), /not configured/);
});

test('provider errors do not expose keys or raw error bodies', async () => {
  for (const [status, code, expected] of [[401, 'invalid_api_key', /rejected/], [429, 'insufficient_quota', /quota/]]) {
    await assert.rejects(generateAnswer(input, { ...options, fetchImpl: async () => ({
      ok: false, status, json: async () => ({ error: { code, message: 'secret request data' } }),
    }) }), error => expected.test(error.message) && !error.message.includes('secret'));
  }
  await assert.rejects(generateAnswer(input, { ...options, fetchImpl: async () => { throw Error('Bearer unit-test-key'); } }),
    error => !error.message.includes('unit-test-key') && /reach OpenAI/.test(error.message));
});

test('truncated and non-text responses are reported, not shown as successful answers', async () => {
  for (const body of [{ ...fakeBody, status: 'incomplete' }, { status: 'completed', output: [] }]) {
    await assert.rejects(generateAnswer(input, { ...options, fetchImpl: async () => ({ ok: true, json: async () => body }) }));
  }
});

test('saved document route sends finalContext, scopes ownership, and returns UI response shape', async () => {
  const oldFind = Document.findOne;
  const oldCreate = QueryHistory.create;
  const oldFetch = globalThis.fetch;
  const oldKey = process.env.OPENAI_API_KEY;
  try {
    process.env.OPENAI_API_KEY = 'unit-test-key';
    Document.findOne = async filter => {
      assert.equal(filter.userId, 'test-user');
      return { status: 'ready', pipelineResult: { finalContext: input.context }, chunks: ['WRONG RAW CHUNKS'] };
    };
    QueryHistory.create = async history => {
      assert.equal(history.inputTokens, 80);
      assert.equal(history.llmProvider, 'openai');
      return { _id: 'saved-history' };
    };
    globalThis.fetch = async (_url, request) => {
      const body = JSON.parse(request.body);
      assert.match(body.input[0].content, /000123/);
      assert.doesNotMatch(JSON.stringify(body), /WRONG RAW CHUNKS/);
      return ok();
    };
    let status, payload;
    const res = { status(code) { status = code; return this; }, json(body) { payload = body; return this; } };
    await submitQuery({ user: { _id: 'test-user' }, body: { documentId: '0123456789abcdef01234567', question: input.question } }, res);
    assert.equal(status, 200);
    assert.equal(payload.data.historyId, 'saved-history');
    assert.equal(payload.data.answer, fakeBody.output[0].content[0].text);
    assert.equal(payload.data.tokenStats.totalTokens, 95);

    // Text-only processing uses the same button without a saved document ID.
    await submitQuery({ user: { _id: 'test-user' }, body: { context: input.context } }, res);
    assert.equal(status, 200);
    assert.equal(payload.data.historyId, undefined);

    Document.findOne = async () => null;
    globalThis.fetch = () => assert.fail('Missing/foreign document must not call OpenAI');
    await submitQuery({ user: { _id: 'other-user' }, body: { documentId: '0123456789abcdef01234567' } }, res);
    assert.equal(status, 404);
  } finally {
    Document.findOne = oldFind;
    QueryHistory.create = oldCreate;
    globalThis.fetch = oldFetch;
    if (oldKey === undefined) delete process.env.OPENAI_API_KEY;
    else process.env.OPENAI_API_KEY = oldKey;
  }
});
