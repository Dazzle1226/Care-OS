import assert from 'node:assert/strict';
import test from 'node:test';

import { ApiError, getNetworkErrorMessage, getUserFacingApiError, isFamilyNotFoundError, resolveApiBase } from '../src/lib/api.ts';

test('isFamilyNotFoundError matches backend 404 family lookup failures', () => {
  const error = new ApiError({
    message: '404 Not Found: Family not found',
    status: 404,
    statusText: 'Not Found',
    detail: 'Family not found',
    bodyText: '{"detail":"Family not found"}'
  });

  assert.equal(isFamilyNotFoundError(error), true);
});

test('isFamilyNotFoundError ignores other API failures', () => {
  const error = new ApiError({
    message: '404 Not Found: Profile not found',
    status: 404,
    statusText: 'Not Found',
    detail: 'Profile not found',
    bodyText: '{"detail":"Profile not found"}'
  });

  assert.equal(isFamilyNotFoundError(error), false);
});

test('resolveApiBase prefers explicit env config when present', () => {
  const base = resolveApiBase('https://api.example.com/api/', {
    hostname: '192.168.1.8',
    origin: 'http://192.168.1.8:4173',
    port: '4173',
    protocol: 'http:'
  });

  assert.equal(base, 'https://api.example.com/api');
});

test('resolveApiBase uses vite proxy during local dev', () => {
  const devBase = resolveApiBase(undefined, {
    hostname: '192.168.1.8',
    origin: 'http://192.168.1.8:5173',
    port: '5173',
    protocol: 'http:'
  });

  assert.equal(devBase, '/api');
});

test('resolveApiBase maps local preview port to the current host on port 8000', () => {
  const previewBase = resolveApiBase(undefined, {
    hostname: '192.168.1.8',
    origin: 'http://192.168.1.8:4173',
    port: '4173',
    protocol: 'http:'
  });

  assert.equal(previewBase, 'http://192.168.1.8:8000/api');
});

test('resolveApiBase falls back to same-origin api path outside local dev ports', () => {
  const base = resolveApiBase(undefined, {
    hostname: 'care.example.com',
    origin: 'https://care.example.com',
    port: '',
    protocol: 'https:'
  });

  assert.equal(base, 'https://care.example.com/api');
});

test('getUserFacingApiError prefers backend detail for API failures', () => {
  const error = new ApiError({
    message: '422 Unprocessable Entity: 文件格式暂不支持，请改用图片、PDF 或常见音频格式。',
    status: 422,
    statusText: 'Unprocessable Entity',
    detail: '文件格式暂不支持，请改用图片、PDF 或常见音频格式。',
    bodyText: '{"detail":"文件格式暂不支持，请改用图片、PDF 或常见音频格式。"}'
  });

  assert.equal(
    getUserFacingApiError(error, '文档解析失败，请改用手动粘贴通知摘要。'),
    '文件格式暂不支持，请改用图片、PDF 或常见音频格式。'
  );
});

test('getUserFacingApiError falls back when the error has no structured detail', () => {
  assert.equal(
    getUserFacingApiError(new Error(''), '文档解析失败，请改用手动粘贴通知摘要。'),
    '文档解析失败，请改用手动粘贴通知摘要。'
  );
});

test('getNetworkErrorMessage distinguishes timeout from connection failures', () => {
  assert.equal(
    getNetworkErrorMessage(Object.assign(new Error('The operation was aborted.'), { name: 'AbortError' })),
    '请求超时：本地后端响应过慢。请确认后端已启动完成后重试。'
  );
  assert.equal(
    getNetworkErrorMessage(new TypeError('Failed to fetch')),
    '无法连接本地后端服务。请确认 http://localhost:8000 已启动，或检查 VITE_API_BASE_URL / Vite 代理配置。'
  );
});
