/** 右栏：单张卡片的编辑表单与问题列表。 */

import type { Card } from '../types';

interface Props {
  card: Card | null;
  onPatch: (patch: Partial<Pick<Card, 'front' | 'back' | 'tags'>>) => void;
  onSave: () => void;
  onDelete: () => void;
}

export default function CardDetail({ card, onPatch, onSave, onDelete }: Props) {
  if (!card) {
    return (
      <section className="bg-gray-800 rounded-xl shadow-lg p-4">
        <h2 className="text-xs font-medium text-gray-400 mb-2">卡片详情</h2>
        <p className="text-gray-400 text-[13px] py-5">从中间列表选一张卡片开始编辑</p>
      </section>
    );
  }

  return (
    <section className="bg-gray-800 rounded-xl shadow-lg p-4">
      <h2 className="text-xs font-medium text-gray-400 mb-2">卡片详情</h2>

      <label className="block text-xs text-gray-400 mb-2.5">
        正面（问题）
        <textarea
          rows={4}
          value={card.front}
          onChange={(e) => onPatch({ front: e.target.value })}
          className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400 resize-y"
        />
      </label>

      <label className="block text-xs text-gray-400 mb-2.5">
        反面（答案）
        <textarea
          rows={9}
          value={card.back}
          onChange={(e) => onPatch({ back: e.target.value })}
          className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400 resize-y"
        />
      </label>

      <label className="block text-xs text-gray-400 mb-2.5">
        标签（逗号分隔）
        <input
          value={card.tags.join(', ')}
          placeholder="networking, cs"
          onChange={(e) =>
            onPatch({
              tags: e.target.value
                .split(/[,，]/)
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
          className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400"
        />
      </label>

      <div className="mb-2.5">
        {card.issues.length === 0 ? (
          <p className="text-xs text-gray-400">这张卡没有发现问题</p>
        ) : (
          card.issues.map((issue, idx) => (
            <div
              key={`${issue.code}-${idx}`}
              className={`text-xs p-1.5 rounded mb-1.5 border-l-[3px] ${
                issue.level === 'error'
                  ? 'border-l-red-500 bg-red-500/10 text-red-300'
                  : 'border-l-amber-500 bg-amber-500/10 text-amber-300'
              }`}
            >
              [{issue.level === 'error' ? '错误' : '警告'}·{issue.code}] {issue.message}
            </div>
          ))
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={onSave}
          className="px-3 py-1.5 bg-blue-500 border border-blue-500 text-white rounded-lg text-sm hover:brightness-110"
        >
          保存
        </button>
        <button
          onClick={onDelete}
          className="px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-sm text-gray-200 hover:bg-gray-600 hover:text-red-400 hover:border-red-500"
        >
          删除
        </button>
      </div>
    </section>
  );
}
