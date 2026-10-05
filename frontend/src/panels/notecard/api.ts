/**
 * 笔记制卡面板的 API 客户端。
 *
 */

import type {
  BrowseResult,
  ExportResult,
  ExtractPayload,
  ExtractResult,
  PagesResult,
  RenderResult,
  ScanResult,
  ValidateResult,
} from './types';

const BASE = '/api/notecard';

async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({ error: '服务端返回的不是 JSON' }));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data as T;
}

/** 提取卡片 */
export const extractCards = (payload: ExtractPayload) => api<ExtractResult>('/extract', payload);

/** 重新校验编辑后的卡片（整份回传，服务端无状态） */
export const validateCards = (cards: unknown) => api<ValidateResult>('/validate', { cards });

export const exportApkg = (cards: unknown, deckName: string) =>
  api<ExportResult>('/export', { cards, deck_name: deckName });

/** OneNote 源：路径 → 目录 / 分区树 → Markdown */
export const browseDirs = (path: string) => api<BrowseResult>('/onenote/browse', { path });

export const scanNotebooks = (path: string, includeRecycle: boolean) =>
  api<ScanResult>('/onenote/scan', { path, include_recycle: includeRecycle });

export const listPages = (section: string) => api<PagesResult>('/onenote/pages', { section });

export const renderPage = (section: string, index: number) =>
  api<RenderResult>('/onenote/page', { section, index });

export const renderSection = (section: string) => api<RenderResult>('/onenote/section', { section });
