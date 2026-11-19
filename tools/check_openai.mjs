// A live connection check using synthetic data only. No PDF is transmitted.
import { readFileSync } from 'node:fs';
import { generateAnswer } from '../apps/server/src/services/openai.service.js';
const env = readFileSync(new URL('../apps/server/.env', import.meta.url), 'utf8');
const setting = key => env.match(new RegExp(`^${key}=(.*)$`, 'm'))?.[1].trim();
try {
  const result = await generateAnswer({
    context: 'Test customer: Demo User. Branch code: 0012.',
    question: 'What is the branch code? Answer with the code only.',
  }, { apiKey: setting('OPENAI_API_KEY'), model: setting('OPENAI_MODEL') });
  console.log(JSON.stringify({ connected: true, model: result.model,
    preservedLeadingZeros: result.answer.includes('0012'), usage: result.tokenStats }));
} catch (error) {
  console.log(JSON.stringify({ connected: false, error: error.message }));
  process.exitCode = 1;
}
