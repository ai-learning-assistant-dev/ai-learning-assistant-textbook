/**
 * 中栏：卡片校验列表。
 *
 * 每行左侧色条表示校验结果（红=error 阻断导出 / 黄=warning / 绿=无问题），
 * 行尾挂 source、标签与问题码——与原实现一致，问题只标注不静默丢弃。
 */

import type { Card } from '../types';

interface Props {
  cards: Card[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
  onDropBad: () => void;
  onRecheck: () => void;
}

/** 去掉 HTML 标签，列表里只显示纯文本摘要 */
function stripTags(html: string): string {
  return (html || '').replace(/<[^>]+>/g, '');
}

function rowTone(card: Card): string {
  if (card.issues.some((i) => i.level === 'error')) return 'border-l-red-500';
  if (card.issues.some((i) => i.level === 'warning')) return 'border-l-amber-500';
  return 'border-l-green-500';
}

export default function CardList({
  cards,
  selectedId,
  onSelect,
  onAdd,
  onDropBad,
  onRecheck,
}: Props) {
  return (
    <section className="bg-white rounded-xl shadow-lg p-4">
      <h2 className="text-xs font-medium text-gray-500 mb-2">
        2 · 校验并编辑
        <span className="ml-2 text-gray-400">{cards.length ? `（${cards.length}）` : ''}</span>
      </h2>

      <div className="flex gap-2 mb-2.5 flex-wrap">
        <button
          onClick={onAdd}
          className="px-3 py-1.5 bg-gray-100 border border-gray-300 rounded-lg text-sm hover:border-blue-500"
        >
          + 新增
        </button>
        <button
          onClick={onDropBad}
          className="px-3 py-1.5 bg-gray-100 border border-gray-300 rounded-lg text-sm hover:border-blue-500"
        >
          剔除问题卡
        </button>
        <button
          onClick={onRecheck}
          className="px-3 py-1.5 bg-gray-100 border border-gray-300 rounded-lg text-sm hover:border-blue-500"
        >
          重新校验
        </button>
      </div>

      <div className="max-h-[68vh] overflow-y-auto">
        {cards.length === 0 ? (
          <p className="text-gray-400 text-[13px] py-5">还没有卡片。先在左侧输入笔记并提取。</p>
        ) : (
          cards.map((card, idx) => (
            <div
              key={card.id}
              onClick={() => onSelect(card.id)}
              className={`border border-l-[3px] border-gray-200 rounded-lg p-2 mb-1.5 cursor-pointer bg-gray-50 hover:border-blue-500 ${
                rowTone(card)
              } ${card.id === selectedId ? '!border-blue-500 bg-blue-50' : ''}`}
            >
              <span className="block text-[13px] mb-0.5">
                <span className="text-gray-400 text-xs mr-1.5">{idx + 1}.</span>
                {card.front || '(空正面)'}
              </span>
              <span className="block text-xs text-gray-500 overflow-hidden text-ellipsis whitespace-nowrap">
                {stripTags(card.back) || '(空反面)'}
              </span>
              <div className="flex gap-1.5 mt-1.5 flex-wrap">
                <span className="text-[11px] px-1.5 rounded bg-blue-100 text-blue-700">
                  {card.source || 'unknown'}
                </span>
                {(card.tags || []).map((t) => (
                  <span key={t} className="text-[11px] px-1.5 rounded bg-gray-200 text-gray-600">
                    {t}
                  </span>
                ))}
                {(card.issues || []).map((i, k) => (
                  <span
                    key={`${i.code}-${k}`}
                    title={i.message}
                    className={`text-[11px] px-1.5 rounded ${
                      i.level === 'error' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                    }`}
                  >
                    {i.code}
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
