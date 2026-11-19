# LLM integration

The Node server reads `OPENAI_API_KEY` and `OPENAI_MODEL` from `apps/server/.env`.
The key must not be placed in a Vite variable or frontend file. Environment files
are ignored by Git. The default model is `gpt-4o-mini`; change `OPENAI_MODEL` on
the server to select another supported model.

After processing a document, use **Send to OpenAI** in the results panel. An
optional question focuses the answer; leaving it blank requests a summary with
exact records. Select OpenAI or Gemini in either the results panel or Questions
page. Gemini reads `GEMINI_API_KEY` and `GEMINI_MODEL` from the same server-only
environment file. Its default model is `gemini-3.8-flash` (the model Google
recommended when the live test rejected Gemini 2.5 for a new API user).

Only the optimized `finalContext` from the saved document is sent. Pasted-text
results can be sent directly from the results panel without saving a document.
Document processing itself never triggers an LLM request. No original PDF is
uploaded to OpenAI by this feature.

The request uses the [OpenAI Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses)
with `store: false`. Answers show the actual input/output token usage returned
by the API. Cost and original-token savings are not fabricated.

Run the backend from `apps/server` with `npm start`, and the frontend from
`apps/client` with `npm run dev`. Restart an existing Node process after changing
the environment. The normal app still requires its existing MongoDB/auth setup
and the Python engine for processing documents.

Checks:

```
cd apps/server
node --test test/openai.test.js test/gemini.test.js
cd ../client
node --test test/providers.test.mjs
npm run build
```

The live connection test uses synthetic text only (`node tools/check_openai.mjs`).
The initial check reached OpenAI but received HTTP 429 (rate limit). A successful
live answer remains unverified until the API project's limit allows a request.

Use `node tools/check_gemini.mjs` to test Gemini with synthetic data. The Gemini
integration uses Google's [generateContent API](https://ai.google.dev/api/generate-content).
Each request goes only to the selected provider; there is no automatic fallback
to another provider.

Gemini live checks: the key successfully listed available models (HTTP 200).
Generation with the recommended model returned HTTP 503 UNAVAILABLE: Google
reported high demand and asked to try again later. A successful live answer
has not yet been verified. The UI displays this error clearly. Local
request/response tests and the UI build pass.
