/**
 * 左栏：1 · 选择笔记来源 → 提取卡片 → 3 · 导出。
 *
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { exportApkg, extractCards, scanNotebooks } from '../api';
import type { Card, ExtractMode, LLMForm, NoteSource, Report, ScanResult } from '../types';
import DirectoryBrowser from './DirectoryBrowser';
import SectionTree from './SectionTree';

const PATH_STORAGE_KEY = 'note2anki.onenote_path';

const DEFAULT_LLM: LLMForm = {
  base_url: 'https://api.siliconflow.cn/v1',
  api_key: '',
  model: 'deepseek-ai/DeepSeek-V3.2',
};

/** 模型候选，与原实现的 datalist 一致（已过滤图像/视频/音频/Embedding 类） */
const MODEL_OPTIONS = [
  'deepseek-ai/DeepSeek-V3.2',
  'deepseek-ai/DeepSeek-V3.1-Terminus',
  'deepseek-ai/DeepSeek-V3',
  'deepseek-ai/DeepSeek-R1',
  'Qwen/Qwen3.5-35B-A3B',
  'Qwen/Qwen3.5-27B',
  'Qwen/Qwen3.5-9B',
  'Qwen/Qwen3-32B',
  'Qwen/Qwen3-14B',
  'Qwen/Qwen3-30B-A3B-Instruct-2507',
  'Qwen/Qwen3-Coder-30B-A3B-Instruct',
  'Qwen/Qwen3-VL-32B-Instruct',
  'Qwen/Qwen3-VL-32B-Thinking',
  'Qwen/Qwen3-VL-30B-A3B-Instruct',
  'Qwen/Qwen3-VL-30B-A3B-Thinking',
  'Qwen/Qwen3-VL-8B-Instruct',
  'Qwen/Qwen3-VL-8B-Thinking',
  'Qwen/Qwen2.5-72B-Instruct',
  'Qwen/Qwen2.5-32B-Instruct',
  'Qwen/Qwen2.5-7B-Instruct',
  'zai-org/GLM-4.5-Air',
  'zai-org/GLM-4.5V',
  'THUDM/GLM-4-32B-0414',
  'inclusionAI/Ling-flash-2.0',
  'inclusionAI/Ling-mini-2.0',
  'ByteDance-Seed/Seed-OSS-36B-Instruct',
  'tencent/Hunyuan-A13B-Instruct',
];

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
  const [llm, setLlm] = useState<LLMForm>(DEFAULT_LLM);
  const [extracting, setExtracting] = useState<boolean>(false);

  const [deckName, setDeckName] = useState<string>('Note2Anki');
  const [exportHint, setExportHint] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // 记住上次用过的路径
  useEffect(() => {
    const saved = localStorage.getItem(PATH_STORAGE_KEY);
    if (saved) setOnPath(saved);
  }, []);

  /** 载入笔记正文：来源可能是 OneNote 页 / 文件 / 粘贴 */
  const setSource = useCallback(
    (text: string, filename: string, label: string) => {
      const next: NoteSource = {
        text: text || '',
        filename: filename || 'note.md',
        sourceLabel: label || filename || '',
      };
      onNoteChange(next);

      // 牌组名还是默认值时，用笔记文件名自动填一个
      if (!deckName || deckName === 'Note2Anki') {
        setDeckName(next.filename.replace(/\.(md|txt|markdown)$/i, '') || 'Note2Anki');
      }
    },
    [deckName, onNoteChange]
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
        ...(mode === 'llm'
          ? {
              llm: {
                base_url: llm.base_url.trim(),
                api_key: llm.api_key.trim(),
                model: llm.model.trim() || 'gpt-4o-mini',
              },
            }
          : {}),
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
  }, [note, mode, llm, onExtracted, onToast]);

  const handleExport = useCallback(async () => {
    if (!cards.length) {
      onToast('还没有卡片可以导出', true);
      return;
    }
    try {
      const d = await exportApkg(cards, deckName.trim() || 'Note2Anki');
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
    <section className="bg-white rounded-xl shadow-lg p-4">
      <h2 className="text-xs font-medium text-gray-500 mb-2">1 · 选择笔记来源</h2>

      {/* 来源 A：OneNote（默认展开） */}
      <div className="border border-gray-200 rounded-lg mb-2 bg-gray-50">
        <button
          onClick={() => toggleBlock('onenote')}
          className="w-full flex justify-between items-center px-3 py-2 text-[13px] rounded-lg hover:bg-blue-50"
        >
          OneNote
          <span className="text-gray-400 text-xs">{openBlocks.onenote ? '▾' : '▸'}</span>
        </button>

        {openBlocks.onenote && (
          <div className="px-3 pb-3">
            <label className="block text-xs text-gray-500 mb-2.5">
              OneNote 存储路径
              <div className="flex gap-2 items-end">
                <input
                  value={onPath}
                  onChange={(e) => setOnPath(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleScan();
                  }}
                  placeholder="例：G:/Software/OneNoteFiles/16.0/备份/我的笔记本"
                  className="flex-1 mt-1 px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-[13px] focus:outline-none focus:border-blue-500"
                />
                <button
                  onClick={() => setBrowseOpen((v) => !v)}
                  className="px-2.5 py-1.5 text-xs rounded-lg border bg-white border-gray-300 whitespace-nowrap"
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
              <label className="flex items-center gap-1.5 text-xs text-gray-500 whitespace-nowrap pb-1.5">
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
      <div className="border border-gray-200 rounded-lg mb-2 bg-gray-50">
        <button
          onClick={() => toggleBlock('file')}
          className="w-full flex justify-between items-center px-3 py-2 text-[13px] rounded-lg hover:bg-blue-50"
        >
          Markdown 文件
          <span className="text-gray-400 text-xs">{openBlocks.file ? '▾' : '▸'}</span>
        </button>
        {openBlocks.file && (
          <div className="px-3 pb-3">
            <label className="block text-xs text-gray-500 mb-2.5">
              选择本地 .md / .txt 文件
              <input
                ref={fileInputRef}
                type="file"
                accept=".md,.markdown,.mdown,.txt"
                onChange={(e) => handleFile(e.target.files?.[0])}
                className="w-full mt-1 px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-[13px]"
              />
            </label>
            <p className="text-xs text-gray-400">文件只在浏览器里读取，不会上传到任何地方。</p>
          </div>
        )}
      </div>

      {/* 来源 C：手动输入（折叠，占视觉空间大所以后置） */}
      <div className="border border-gray-200 rounded-lg mb-2.5 bg-gray-50">
        <button
          onClick={() => toggleBlock('paste')}
          className="w-full flex justify-between items-center px-3 py-2 text-[13px] rounded-lg hover:bg-blue-50"
        >
          手动输入
          <span className="text-gray-400 text-xs">{openBlocks.paste ? '▾' : '▸'}</span>
        </button>
        {openBlocks.paste && (
          <div className="px-3 pb-3">
            <label className="block text-xs text-gray-500">
              笔记内容（Markdown / TXT）
              <textarea
                rows={12}
                value={note.text}
                placeholder="粘贴你的笔记…"
                onChange={(e) => setSource(e.target.value, note.filename, note.sourceLabel)}
                className="w-full mt-1 px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-[13px] focus:outline-none focus:border-blue-500 resize-y"
              />
            </label>
          </div>
        )}
      </div>

      {/* 当前载入的笔记 */}
      <div className="text-xs text-gray-500 border border-dashed border-gray-300 rounded-lg px-2 py-1.5 my-2.5 break-all">
        {note.text.trim() ? (
          <>
            <span className="text-gray-800">{note.sourceLabel || note.filename}</span>
            {` · ${note.text.length} 字符`}
          </>
        ) : (
          <span className="text-gray-400">尚未载入笔记</span>
        )}
      </div>

      <label className="block text-xs text-gray-500 mb-2.5">
        提取方式
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as ExtractMode)}
          className="w-full mt-1 px-2.5 py-1.5 bg-gray-50 border border-gray-300 rounded-lg text-[13px] focus:outline-none focus:border-blue-500"
        >
          <option value="rule">规则提取 · 无需配置</option>
          <option value="llm">LLM 提取 · 需配置</option>
        </select>
      </label>

      {mode === 'llm' && (
        <div className="border border-dashed border-gray-300 rounded-lg p-2.5 mb-2.5">
          <label className="block text-xs text-gray-500 mb-2.5">
            Base URL
            <input
              value={llm.base_url}
              onChange={(e) => setLlm({ ...llm, base_url: e.target.value })}
              className="w-full mt-1 px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-[13px] focus:outline-none focus:border-blue-500"
            />
          </label>
          <label className="block text-xs text-gray-500 mb-2.5">
            API Key
            <input
              type="password"
              placeholder="sk-..."
              value={llm.api_key}
              onChange={(e) => setLlm({ ...llm, api_key: e.target.value })}
              className="w-full mt-1 px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-[13px] focus:outline-none focus:border-blue-500"
            />
          </label>
          <label className="block text-xs text-gray-500 mb-1">
            Model
            <input
              list="notecard-model-list"
              value={llm.model}
              onChange={(e) => setLlm({ ...llm, model: e.target.value })}
              className="w-full mt-1 px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-[13px] focus:outline-none focus:border-blue-500"
            />
            <datalist id="notecard-model-list">
              {MODEL_OPTIONS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </label>
          <p className="text-xs text-gray-400">
            只能用服务商给定列表内的模型；图像 / 视频 / 音频 / Embedding 类已过滤。
          </p>
        </div>
      )}

      <button
        onClick={handleExtract}
        disabled={extracting}
        className="w-full px-3 py-1.5 bg-blue-500 border border-blue-500 text-white rounded-lg text-sm hover:brightness-110 disabled:opacity-50"
      >
        {extracting ? '提取中…' : '提取卡片'}
      </button>

      <h2 className="text-xs font-medium text-gray-500 mt-5 mb-2">3 · 导出</h2>
      <label className="block text-xs text-gray-500 mb-2.5">
        牌组名称
        <input
          value={deckName}
          onChange={(e) => setDeckName(e.target.value)}
          className="w-full mt-1 px-2.5 py-1.5 bg-gray-50 border border-gray-300 rounded-lg text-[13px] focus:outline-none focus:border-blue-500"
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
