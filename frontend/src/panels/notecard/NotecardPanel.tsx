/**
 * 笔记制卡面板布局：左（来源 + 提取 + 导出）/ 中（校验列表）/ 右（卡片详情）。
 *
 * 请注意：服务端无状态，卡片列表由本组件持有。
 */

import { useCallback, useRef, useState } from 'react';
import { renderPage, renderSection, validateCards } from './api';
import type { Card, NoteSource, RenderResult, Report } from './types';
import CardDetail from './components/CardDetail';
import CardList from './components/CardList';
import PreviewModal from './components/PreviewModal';
import ReportBar from './components/ReportBar';
import SourcePanel from './components/SourcePanel';
import Toast from './components/Toast';

const EMPTY_NOTE: NoteSource = { text: '', filename: 'note.md', sourceLabel: '' };

interface PreviewState {
  open: boolean;
  data: RenderResult | null;
  title: string;
  raw: boolean;
}

export default function NotecardPanel() {
  const [note, setNote] = useState<NoteSource>(EMPTY_NOTE);
  const [cards, setCards] = useState<Card[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  const [preview, setPreview] = useState<PreviewState>({
    open: false,
    data: null,
    title: '',
    raw: false,
  });
  const [toast, setToast] = useState<{ message: string; isError: boolean } | null>(null);
  const toastTimer = useRef<number | null>(null);

  const onToast = useCallback((message: string, isError = false) => {
    setToast({ message, isError });
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 4000);
  }, []);

  /** 重新校验：整份回传后端，拿回带 issues 的卡片与新报告 */
  const recheck = useCallback(
    async (list: Card[]) => {
      if (!list.length) {
        setCards([]);
        setReport(null);
        return;
      }
      try {
        const d = await validateCards(list);
        setCards(d.cards);
        setReport(d.report);
      } catch (e) {
        onToast(e instanceof Error ? e.message : '校验失败', true);
      }
    },
    [onToast]
  );

  const onExtracted = useCallback((next: Card[], nextReport: Report) => {
    setCards(next);
    setReport(nextReport);
    setSelectedId(next.length ? next[0].id : null);
  }, []);

  const updateCard = useCallback((id: string, patch: Partial<Card>) => {
    setCards((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  }, []);

  const addCard = useCallback(() => {
    const card: Card = {
      id: 'n' + Math.random().toString(36).slice(2, 10),
      front: '',
      back: '',
      tags: [],
      source: 'manual',
      issues: [],
    };
    setCards((prev) => [...prev, card]);
    setSelectedId(card.id);
    recheck([...cards, card]);
  }, [cards, recheck]);

  const dropBad = useCallback(() => {
    const before = cards.length;
    const kept = cards.filter((c) => !c.issues.some((i) => i.level === 'error'));
    if (selectedId && !kept.some((c) => c.id === selectedId)) {
      setSelectedId(kept.length ? kept[0].id : null);
    }
    recheck(kept);
    onToast(`已剔除 ${before - kept.length} 张错误卡`);
  }, [cards, selectedId, recheck, onToast]);

  const deleteCard = useCallback(() => {
    if (!selectedId) return;
    const kept = cards.filter((c) => c.id !== selectedId);
    setSelectedId(kept.length ? kept[0].id : null);
    recheck(kept);
  }, [cards, selectedId, recheck]);

  const selected = cards.find((c) => c.id === selectedId) || null;

  /** 预览：先开弹层显示「解析中…」，拿到数据再填充 */
  const openPage = useCallback(
    async (section: string, index: number, title: string) => {
      setPreview({ open: true, data: null, title, raw: false });
      try {
        const d = await renderPage(section, index);
        setPreview({ open: true, data: d, title: d.source, raw: false });
      } catch (e) {
        setPreview({ open: false, data: null, title: '', raw: false });
        onToast('渲染失败：' + (e instanceof Error ? e.message : e), true);
      }
    },
    [onToast]
  );

  const openSection = useCallback(
    async (section: string, name: string) => {
      setPreview({ open: true, data: null, title: name, raw: false });
      try {
        const d = await renderSection(section);
        const title = d.failed_pages ? `${d.source}（${d.failed_pages} 页渲染失败）` : d.source;
        setPreview({ open: true, data: d, title, raw: false });
      } catch (e) {
        setPreview({ open: false, data: null, title: '', raw: false });
        onToast('渲染失败：' + (e instanceof Error ? e.message : e), true);
      }
    },
    [onToast]
  );

  /** 弹层里「用此内容制卡」 */
  const usePreviewContent = useCallback(() => {
    const d = preview.data;
    if (!d) return;
    setNote({ text: d.markdown, filename: d.filename, sourceLabel: d.source });
    setPreview({ open: false, data: null, title: '', raw: false });
    onToast(`已载入「${d.source}」${d.chars} 字符，选提取方式后点「提取卡片」`);
  }, [preview.data, onToast]);

  return (
    <div className="notecard-dark h-full overflow-auto p-3.5 bg-gray-900 text-gray-100">
      {/* 标题条 + 报告徽章 */}
      <div className="mb-3.5 bg-gray-800 rounded-xl shadow-lg overflow-hidden">
        {/* 改为 OneNote 紫渐变（violet-600 → purple-800）：原来 emerald-500 → teal-600 的高饱和翠绿太跳，
            紫色更贴近 OneNote 品牌色。两处模糊光斑用来打破大面积平涂的平板感，同时不提高整体明度。 */}
        <div className="relative overflow-hidden bg-gradient-to-r from-violet-600 via-purple-700 to-purple-800 p-5 text-white">
          <div className="pointer-events-none absolute -right-6 -top-12 h-32 w-32 rounded-full bg-purple-300/20 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-16 left-1/4 h-32 w-52 rounded-full bg-violet-200/10 blur-3xl" />
          <h1 className="relative text-xl font-bold tracking-wide">🗂️ 笔记制卡</h1>
          <p className="relative mt-1.5 text-xs text-purple-50/75">
            OneNote / Markdown / 粘贴内容 → 问答题卡片
          </p>
        </div>
        <div className="px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap">
          <ReportBar report={report} />
          {report?.blocking && (
            <span className="text-xs text-red-400">存在结构性错误，修复后才能导出</span>
          )}
        </div>
      </div>

      {/* 三栏：来源 / 校验列表 / 详情 */}
      <div className="grid grid-cols-1 xl:grid-cols-[320px_minmax(360px,1fr)_380px] gap-3.5 items-start">
        <SourcePanel
          note={note}
          onNoteChange={setNote}
          cards={cards}
          onExtracted={onExtracted}
          onExported={setReport}
          onToast={onToast}
          onPreviewPage={openPage}
          onPreviewSection={openSection}
        />

        <CardList
          cards={cards}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onAdd={addCard}
          onDropBad={dropBad}
          onRecheck={() => recheck(cards)}
        />

        <CardDetail
          card={selected}
          onPatch={(patch) => selected && updateCard(selected.id, patch)}
          onSave={() => {
            recheck(cards);
            onToast('已保存并重新校验');
          }}
          onDelete={deleteCard}
        />
      </div>

      {preview.open && (
        <PreviewModal
          data={preview.data}
          title={preview.title}
          raw={preview.raw}
          onToggleRaw={(raw) => setPreview((p) => ({ ...p, raw }))}
          onClose={() => setPreview({ open: false, data: null, title: '', raw: false })}
          onUse={usePreviewContent}
        />
      )}

      {toast && <Toast message={toast.message} isError={toast.isError} />}
    </div>
  );
}
