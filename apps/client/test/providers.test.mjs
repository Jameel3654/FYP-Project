import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { build } from 'esbuild';
import { writeFile, mkdir } from 'node:fs/promises';

test('Gemini and OpenAI are enabled, and Gemini can be selected', async () => {
  const result = await build({ entryPoints: ['src/components/Query/LLMSelector.jsx'],
    bundle: true, platform: 'node', format: 'esm', write: false });
  const folder = new URL('../../../output/openai-ui-test/', import.meta.url);
  await mkdir(folder, { recursive: true });
  const bundle = new URL('selector.mjs', folder);
  await writeFile(bundle, result.outputFiles[0].text);
  const { default: Selector } = await import(bundle.href);
  const html = renderToStaticMarkup(React.createElement(Selector, { selected: 'gemini', onChange() {} }));
  const buttons = [...html.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/g)].map(match => match[0]);
  assert.equal(buttons.length, 2);
  assert.match(buttons[0], /aria-pressed="false"/);
  assert.doesNotMatch(buttons[0], / disabled(?:=|\s|>)/);
  assert.doesNotMatch(buttons[1], / disabled(?:=|\s|>)/);
  assert.match(buttons[1], /aria-pressed="true"/);
  assert.match(buttons[1], /Gemini/);
  assert.doesNotMatch(buttons[1], /coming soon/);
});
