// Live check uses synthetic text only, never the uploaded PDF or real records.
import { readFileSync } from 'node:fs';
import { generateAnswer } from '../apps/server/src/services/llm.service.js';
const env = readFileSync(new URL('../apps/server/.env', import.meta.url), 'utf8');
const setting = key => env.match(new RegExp(`^${key}=(.*)$`, 'm'))?.[1].trim();
const apiKey = setting('GEMINI_API_KEY');
const diagnosticFetch = async (...args) => {
  const timeout = process.argv.includes('--full-timeout') ? 90000 : 20000;
  const response = await fetch(args[0], { ...args[1], signal: AbortSignal.timeout(timeout) });
  if (!response.ok) {
    const body = await response.clone().json().catch(() => ({}));
    console.log(JSON.stringify({ httpStatus: response.status, status: body.error?.status,
      reasons: (body.error?.details || []).map(d => d.reason).filter(Boolean),
      message: String(body.error?.message || '').split(apiKey).join('[redacted]').slice(0, 700) }));
  }
  return response;
};
try {
  const result = await generateAnswer({ provider: 'gemini',
    context: 'Test customer: Demo User. Account number: 000123. Branch code: 0012.',
    question: 'Return the account number and branch code exactly, preserving leading zeros. No other text.',
  }, { apiKey, model: process.argv[2] || setting('GEMINI_MODEL'), fetchImpl: diagnosticFetch });
  console.log(JSON.stringify({ connected: true, provider: result.provider, model: result.model,
    preservedAccount: result.answer.includes('000123'), preservedBranch: result.answer.includes('0012'),
    answer: result.answer, usage: result.tokenStats }));
} catch (error) {
  console.log(JSON.stringify({ connected: false, error: error.message }));
  process.exitCode = 1;
}
