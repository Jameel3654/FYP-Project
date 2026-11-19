import { generateAnswer as openai, LLMError } from './openai.service.js';
import { generateGeminiAnswer as gemini } from './gemini.service.js';

export { LLMError };
export function generateAnswer(request, options) {
  if (request.provider === 'gemini') return gemini(request, options);
  if (!request.provider || ['openai', 'gpt-4'].includes(request.provider)) return openai(request, options);
  throw new LLMError('Unsupported provider. Select OpenAI or Gemini.', 400);
}
