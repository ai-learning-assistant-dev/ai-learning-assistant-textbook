/**
 * OneNote 页面预览弹层：渲染 / 源码切换。
 *
 */

import { useEffect } from 'react';
import { marked } from 'marked';
import type { RenderResult } from '../types';

interface Props {
  /** null 表示还在解析中，弹层先显示「解析中…」 */
  data: RenderResult | null;
  title: string;
  raw: boolean;
  onToggleRaw: (raw: boolean) => void;
  onClose: () => void;
  onUse: () => void;
}

export default function PreviewModal({ data, title, raw, onToggleRaw, onClose, onUse }: Props) {
  // Esc 关闭，与原实现一致
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const meta = data
    ? [
        `${data.chars} 字符`,
        data.images ? `${data.images} 张图片（不导出，仅占位）` : '',
        data.degraded ? '容错解析，内容可能不完整' : '',
        data.failed_pages ? `${data.failed_pages} 页渲染失败` : '',
      ]
        .filter(Boolean)
        .join(' · ')
    : '';

  const html = data ? (marked.parse(data.markdown, { async: false }) as string) : '';

  return (
    <div
      className="fixed inset-0 bg-black/55 flex items-center justify-center z-50 p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white border border-gray-200 rounded-xl w-[min(760px,100%)] max-h-[84vh] flex flex-col">
        <div className="flex justify-between items-center gap-2.5 px-3.5 py-2.5 border-b border-gray-200">
          <div className="text-[13.5px] font-medium break-all">{title || '—'}</div>
          <div className="flex gap-1.5">
            <button
              onClick={() => onToggleRaw(false)}
              className={`px-2.5 py-1.5 text-xs rounded-lg border ${
                !raw ? 'bg-blue-500 border-blue-500 text-white' : 'bg-gray-100 border-gray-300'
              }`}
            >
              渲染
            </button>
            <button
              onClick={() => onToggleRaw(true)}
              className={`px-2.5 py-1.5 text-xs rounded-lg border ${
                raw ? 'bg-blue-500 border-blue-500 text-white' : 'bg-gray-100 border-gray-300'
              }`}
            >
              源码
            </button>
            <button
              onClick={onClose}
              className="px-2.5 py-1.5 text-xs rounded-lg border bg-gray-100 border-gray-300"
            >
              关闭
            </button>
          </div>
        </div>

        <div className="p-3.5 overflow-y-auto text-[13.5px] leading-[1.7]">
          {!data ? (
            <p className="text-gray-400 text-xs p-2">解析中…</p>
          ) : raw ? (
            <pre className="whitespace-pre-wrap break-words font-mono text-xs">{data.markdown}</pre>
          ) : (
            <div
              className="markdown-body"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )}
        </div>

        <div className="flex justify-between items-center gap-2.5 px-3.5 py-2.5 border-t border-gray-200 text-xs">
          <span className="text-gray-500">{meta}</span>
          <button
            onClick={onUse}
            disabled={!data}
            className="px-3 py-1.5 bg-blue-500 border border-blue-500 text-white rounded-lg text-sm hover:brightness-110 disabled:opacity-50"
          >
            用此内容制卡
          </button>
        </div>
      </div>
    </div>
  );
}
