/**
 * 左栏：1 · 选择笔记来源 → 提取卡片 → 3 · 导出。
 *
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { exportApkg, extractCards, listModels, scanNotebooks } from '../api';
import type { Card, ExtractMode, ModelEntry, NoteSource, Report, ScanResult } from '../types';
import DirectoryBrowser from './DirectoryBrowser';
import SectionTree from './SectionTree';

const PATH_STORAGE_KEY = 'note2anki.onenote_path';
const MODEL_STORAGE_KEY = 'note2anki.llm_model';
const DEFAULT_DECK = 'Note2Anki';

/**
 * 从笔记对象推出默认牌组名：优先用界面上展示的笔记名（sourceLabel），其次文件名。
 * - 文件：文件名剥 .md/.txt 扩展名（如「英语语法.md」→「英语语法」）
 * - OneNote 单页：sourceLabel 形如「分区 / 页标题」，原样用作牌组名
 * - OneNote 整分区：sourceLabel 形如「分区名（整分区 N 页）」，剥掉尾部括号说明只留分区名
 * - 手动粘贴：sourceLabel 为空且 filename 是占位 note.md，回落默认 Note2Anki
 */
function deriveDeckName(note: NoteSource): string {
  const raw = (note.sourceLabel || note.filename || '').trim();
  let name = raw.replace(/\.(md|txt|markdown)$/i, '').trim();
  name = name.replace(/[（(][^()（）]*[)）]\s*$/, '').trim();
  if (!name || name.toLowerCase() === 'note') return DEFAULT_DECK;
  return name;
}

interface Props {
  note: NoteSource;
  onNoteChange: (note: NoteSource) => void;
  cards: Card[];
  onExtracted: (cards: Card[], report: Report) => void;
  onExported: (report: Report) => void;
  onToast: (message: string, isError?: boolean) => void;
  onPreviewPage: (section: string, index: number, title: string) => void;
  onPreviewSection: (section: string, name: string) => void;
}

export default function SourcePanel({
  note,
  onNoteChange,
  cards,
  onExtracted,
  onExported,
  onToast,
  onPreviewPage,
  onPreviewSection,
}: Props) {
  const [openBlocks, setOpenBlocks] = useState({ onenote: true, file: false, paste: false });

  const [onPath, setOnPath] = useState<string>('');
  const [includeRecycle, setIncludeRecycle] = useState<boolean>(false);
  const [browseOpen, setBrowseOpen] = useState<boolean>(false);
  const [tree, setTree] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState<boolean>(false);
  const [hint, setHint] = useState<string>(
    '填入路径后扫描，展开分区选页；图片不导出，仅保留占位。'
  );

  const [mode, setMode] = useState<ExtractMode>('rule');
  const [extracting, setExtracting] = useState<boolean>(false);

  // LLM 模式下从「视频下载」共享配置里选模型：加载列表 + 记住上次选的
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [model, setModel] = useState<string>('');
  const [modelsLoading, setModelsLoading] = useState<boolean>(false);
  const [modelError, setModelError] = useState<string>('');

  const [deckName, setDeckName] = useState<string>(DEFAULT_DECK);
  const [exportHint, setExportHint] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // 记住上次用过的路径
  useEffect(() => {
    const saved = localStorage.getItem(PATH_STORAGE_KEY);
    if (saved) setOnPath(saved);
  }, []);

  // 载入「视频下载」面板共享的模型列表，供 LLM 模式下拉选择
  useEffect(() => {
    let alive = true;
    setModelsLoading(true);
    setModelError('');
    listModels()
      .then((list) => {
        if (!alive) return;
        setModels(list);
        const saved = localStorage.getItem(MODEL_STORAGE_KEY);
        const initial = saved && list.some((m) => m.name === saved) ? saved : (list[0]?.name || '');
        setModel(initial);
      })
      .catch((e) => {
        // 加载失败要显式提示，而不是静默让下拉停在「（未配置模型）」
        if (alive) setModelError(e instanceof Error ? e.message : '加载模型列表失败');
      })
      .finally(() => {
        if (alive) setModelsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // 载入笔记（文件 / OneNote 页 / 整分区 / 粘贴）后，若牌组名仍是默认值，
  // 自动用界面上显示的笔记名称（sourceLabel 优先，其次文件名）作为默认导出名。
  // 放在这里可覆盖全部三种来源——OneNote 走 usePreviewContent→setNote，并不经过 setSource。
  useEffect(() => {
    if (deckName && deckName !== DEFAULT_DECK) return;
    const suggested = deriveDeckName(note);
    if (suggested !== deckName) setDeckName(suggested);
  }, [note, deckName]);

  /** 载入笔记正文：来源可能是 OneNote 页 / 文件 / 粘贴 */
  const setSource = useCallback(
    (text: string, filename: string, label: string) => {
      const next: NoteSource = {
        text: text || '',
        filename: filename || 'note.md',
        sourceLabel: label || filename || '',
      };
      onNoteChange(next);
    },
    [onNoteChange]
  );

  const handleScan = useCallback(async () => {
    const path = onPath.trim();
    if (!path) {
      onToast('先填入 OneNote 路径，或用「浏览」选一个目录', true);
      return;
    }
    setScanning(true);
    setHint('扫描中…');
    try {
      const d = await scanNotebooks(path, includeRecycle);
      setTree(d);
      localStorage.setItem(PATH_STORAGE_KEY, path);
      setHint(
        `${d.notebooks.length} 个笔记本 / ${d.section_count} 个分区 · 点分区展开页列表`
      );
    } catch (e) {
      setTree(null);
      setHint('扫描失败：' + (e instanceof Error ? e.message : e));
      onToast(e instanceof Error ? e.message : '扫描失败', true);
    } finally {
      setScanning(false);
    }
  }, [onPath, includeRecycle, onToast]);

  const handleExtract = useCallback(async () => {
    if (!note.text.trim()) {
      onToast('还没有笔记内容：从 OneNote 选一页，或载入 Markdown 文件 / 手动输入', true);
      return;
    }
    setExtracting(true);
    try {
      const payload = {
        text: note.text,
        filename: note.filename || 'note.md',
        mode,
        // 章节汇总卡的开关已从界面移除：实测与列表项 / 定义卡高度重复。
        // 后端逻辑仍在（include_section_cards），tests/test_section_cards.py 有用例。
        include_section_cards: false,
        // LLM 模式：把下拉里选中的共享模型名发给后端（按 name 匹配）；
        // 不在这里发任何 Key，模型配置直接复用 config/llm_models.json。
        ...(mode === 'llm' ? { model } : {}),
      };
      const d = await extractCards(payload);
      onExtracted(d.cards, d.report);
      onToast(
        `提取到 ${d.cards.length} 张卡，其中 ${d.report.error} 处错误、${d.report.warning} 处警告`
      );
    } catch (e) {
      onToast(e instanceof Error ? e.message : '提取失败', true);
    } finally {
      setExtracting(false);
    }
  }, [note, mode, model, onExtracted, onToast]);

  const handleExport = useCallback(async () => {
    if (!cards.length) {
      onToast('还没有卡片可以导出', true);
      return;
    }
    try {
      const d = await exportApkg(cards, deckName.trim() || DEFAULT_DECK);
      onExported(d.report);
      const a = document.createElement('a');
      a.href = d.url;
      a.download = d.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();

      const kb = (d.bytes / 1024).toFixed(1);
      let msg = `已导出 ${d.written} 张卡 → out/${d.filename}（${kb} KB）`;
      if (d.skipped) msg += `，跳过 ${d.skipped} 张空卡`;
      setExportHint(msg);
      onToast(msg);
    } catch (e) {
      onToast(e instanceof Error ? e.message : '导出失败', true);
    }
  }, [cards, deckName, onExported, onToast]);

  const handleFile = useCallback(
    (file: File | undefined) => {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => setSource(String(reader.result || ''), file.name, file.name);
      reader.onerror = () => onToast('读取文件失败', true);
      reader.readAsText(file, 'utf-8');
    },
    [onToast, setSource]
  );

  const toggleBlock = (key: keyof typeof openBlocks) =>
    setOpenBlocks((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <section className="bg-gray-800 rounded-xl shadow-lg p-4">
      <h2 className="text-xs font-medium text-gray-400 mb-2">1 · 选择笔记来源</h2>

      {/* 来源 A：OneNote（默认展开） */}
      <div className="border border-gray-700 rounded-lg mb-2 bg-gray-900/40">
        <button
          onClick={() => toggleBlock('onenote')}
          className="w-full flex justify-between items-center px-3 py-2 text-[13px] rounded-lg hover:bg-gray-700"
        >
          OneNote
          <span className="text-gray-400 text-xs">{openBlocks.onenote ? '▾' : '▸'}</span>
        </button>

        {openBlocks.onenote && (
          <div className="px-3 pb-3">
            <label className="block text-xs text-gray-400 mb-2.5">
              OneNote 存储路径
              <div className="flex gap-2 items-end">
                <input
                  value={onPath}
                  onChange={(e) => setOnPath(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleScan();
                  }}
                  placeholder="例：G:/Software/OneNoteFiles/16.0/备份/我的笔记本"
                  className="flex-1 mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400"
                />
                <button
                  onClick={() => setBrowseOpen((v) => !v)}
                  className="px-2.5 py-1.5 text-xs rounded-lg border bg-gray-700 border-gray-600 text-gray-200 whitespace-nowrap hover:bg-gray-600"
                >
                  浏览
                </button>
              </div>
            </label>

            {browseOpen && (
              <DirectoryBrowser
                initialPath={onPath}
                onToast={onToast}
                onPick={(p) => setOnPath(p)}
              />
            )}

            <div className="flex gap-2 items-end">
              <button
                onClick={handleScan}
                disabled={scanning}
                className="flex-1 px-3 py-1.5 bg-blue-500 border border-blue-500 text-white rounded-lg text-sm hover:brightness-110 disabled:opacity-50"
              >
                {scanning ? '扫描中…' : '扫描笔记本'}
              </button>
              <label className="flex items-center gap-1.5 text-xs text-gray-400 whitespace-nowrap pb-1.5">
                <input
                  type="checkbox"
                  checked={includeRecycle}
                  onChange={(e) => setIncludeRecycle(e.target.checked)}
                />
                含回收站
              </label>
            </div>

            <SectionTree
              tree={tree}
              currentPath={onPath}
              onOpenPage={onPreviewPage}
              onOpenSection={onPreviewSection}
              onToast={onToast}
            />
            <p className="text-xs text-gray-400 mt-2">{hint}</p>
          </div>
        )}
      </div>

      {/* 来源 B：Markdown 文件（折叠） */}
      <div className="border border-gray-700 rounded-lg mb-2 bg-gray-900/40">
        <button
          onClick={() => toggleBlock('file')}
          className="w-full flex justify-between items-center px-3 py-2 text-[13px] rounded-lg hover:bg-gray-700"
        >
          Markdown 文件
          <span className="text-gray-400 text-xs">{openBlocks.file ? '▾' : '▸'}</span>
        </button>
        {openBlocks.file && (
          <div className="px-3 pb-3">
            <label className="block text-xs text-gray-400 mb-2.5">
              选择本地 .md / .txt 文件
              <input
                ref={fileInputRef}
                type="file"
                accept=".md,.markdown,.mdown,.txt"
                onChange={(e) => handleFile(e.target.files?.[0])}
                className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100"
              />
            </label>
            <p className="text-xs text-gray-400">文件只在浏览器里读取，不会上传到任何地方。</p>
          </div>
        )}
      </div>

      {/* 来源 C：手动输入（折叠，占视觉空间大所以后置） */}
      <div className="border border-gray-700 rounded-lg mb-2.5 bg-gray-900/40">
        <button
          onClick={() => toggleBlock('paste')}
          className="w-full flex justify-between items-center px-3 py-2 text-[13px] rounded-lg hover:bg-gray-700"
        >
          手动输入
          <span className="text-gray-400 text-xs">{openBlocks.paste ? '▾' : '▸'}</span>
        </button>
        {openBlocks.paste && (
          <div className="px-3 pb-3">
            <label className="block text-xs text-gray-400">
              笔记内容（Markdown / TXT）
              <textarea
                rows={12}
                value={note.text}
                placeholder="粘贴你的笔记…"
                onChange={(e) => setSource(e.target.value, note.filename, note.sourceLabel)}
                className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400 resize-y"
              />
            </label>
          </div>
        )}
      </div>

      {/* 当前载入的笔记 */}
      <div className="text-xs text-gray-400 border border-dashed border-gray-600 rounded-lg px-2 py-1.5 my-2.5 break-all">
        {note.text.trim() ? (
          <>
            <span className="text-gray-100">{note.sourceLabel || note.filename}</span>
            {` · ${note.text.length} 字符`}
          </>
        ) : (
          <span className="text-gray-400">尚未载入笔记</span>
        )}
      </div>

      <label className="block text-xs text-gray-400 mb-2.5">
        提取方式
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as ExtractMode)}
          className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400"
        >
          <option value="rule">规则提取 · 无需配置</option>
          <option value="llm">LLM 提取 · 选择模型</option>
        </select>
      </label>

      {mode === 'llm' && (
        <div className="mb-2.5">
          <label className="block text-xs text-gray-400 mb-2.5">
            使用模型（来自视频下载的共享配置）
            <select
              value={model}
              onChange={(e) => {
                setModel(e.target.value);
                localStorage.setItem(MODEL_STORAGE_KEY, e.target.value);
              }}
              disabled={modelsLoading || models.length === 0}
              className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400"
            >
              {models.length === 0 ? (
                <option value="">（未配置模型）</option>
              ) : (
                models.map((m) => (
                  <option key={m.id} value={m.name}>
                    {m.name} · {m.model_name}
                  </option>
                ))
              )}
            </select>
          </label>
          {models.length === 0 ? (
            <p className="text-xs text-gray-400">
              {modelError
                ? `加载模型列表失败：${modelError}`
                : '尚未在「视频下载」面板添加任何模型。去视频下载添加一个模型后，这里即可选择，无需在此输入 Key。'}
            </p>
          ) : (
            <p className="text-xs text-gray-400">
              模型配置（config/llm_models.json）。
            </p>
          )}
        </div>
      )}

      <button
        onClick={handleExtract}
        disabled={extracting || (mode === 'llm' && !model)}
        className="w-full px-3 py-1.5 bg-blue-500 border border-blue-500 text-white rounded-lg text-sm hover:brightness-110 disabled:opacity-50"
      >
        {extracting ? '提取中…' : '提取卡片'}
      </button>

      <h2 className="text-xs font-medium text-gray-400 mt-5 mb-2">3 · 导出</h2>
      <label className="block text-xs text-gray-400 mb-2.5">
        牌组名称
        <input
          value={deckName}
          onChange={(e) => setDeckName(e.target.value)}
          className="w-full mt-1 px-2.5 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-[13px] text-gray-100 focus:outline-none focus:border-blue-400"
        />
      </label>
      <button
        onClick={handleExport}
        className="w-full px-3 py-1.5 bg-blue-500 border border-blue-500 text-white rounded-lg text-sm hover:brightness-110"
      >
        导出 .apkg
      </button>
      <p className="text-xs text-gray-400 mt-2">{exportHint}</p>
    </section>
  );
}
