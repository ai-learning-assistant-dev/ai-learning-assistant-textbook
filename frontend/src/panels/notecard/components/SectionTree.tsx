/**
 * OneNote 分区树：笔记本 → 分区组 → 分区 → 页。
 *
 * 页列表是点开分区时才拉的（大分区解析要几秒），所以每个分区有三态：
 * 解析中 / 解析失败 / 已解析。三态必须都写分支，否则 loading 时会掉进
 * 「取 list.length」的分支抛错，整棵树渲染中断。
 */

import { useCallback, useEffect, useRef, useState, type ReactElement } from 'react';
import { listPages } from '../api';
import type { PageMeta, TreeNode } from '../types';

type PagesState =
  | { loading: true }
  | { list: PageMeta[]; degraded: boolean }
  | { error: string };

interface Props {
  tree: { notebooks: TreeNode[] } | null;
  /** 当前 OneNote 路径框的值，解析成功后记进 localStorage */
  currentPath: string;
  onOpenPage: (section: string, index: number, title: string) => void;
  onOpenSection: (section: string, name: string) => void;
  onToast: (message: string, isError?: boolean) => void;
}

function nodeId(node: TreeNode, parentId: string): string {
  if (node.type === 'page') return `${parentId}#${node.index}`;
  if (node.type === 'section-all') return `${parentId}#all`;
  return node.path ? `${node.type}:${node.path}` : `${parentId}/${node.name}`;
}

export default function SectionTree({
  tree,
  currentPath,
  onOpenPage,
  onOpenSection,
  onToast,
}: Props) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [pages, setPages] = useState<Record<string, PagesState>>({});

  const toggle = useCallback(
    async (node: TreeNode, id: string) => {
      // 叶子节点直接触发预览，不参与展开态
      if (node.type === 'page') {
        onOpenPage(node.path || '', node.index || 1, node.name);
        return;
      }
      if (node.type === 'section-all') {
        onOpenSection(node.path || '', node.name);
        return;
      }

      setOpen((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });

      const alreadyOpen = open.has(id);
      if (alreadyOpen) return;

      if (node.type === 'section' && !pages[id]) {
        setPages((prev) => ({ ...prev, [id]: { loading: true } }));
        try {
          const d = await listPages(node.path || '');
          setPages((prev) => ({ ...prev, [id]: { list: d.pages, degraded: d.degraded } }));
          localStorage.setItem('note2anki.onenote_path', currentPath.trim());
          onToast(`「${d.name}」解析完成：${d.pages.length} 页（${d.load_seconds}s）`);
        } catch (e) {
          setPages((prev) => ({
            ...prev,
            [id]: { error: String(e instanceof Error ? e.message : e).slice(0, 140) },
          }));
        }
      }
    },
    [currentPath, onOpenPage, onOpenSection, onToast, open, pages]
  );

  // 直接指向单个笔记本 / 单个 .one 时，把层级自动展开到页，少点几次
  const autoDone = useRef<unknown>(null);
  useEffect(() => {
    if (!tree || autoDone.current === tree) return;
    autoDone.current = tree;

    const nb = tree.notebooks.length === 1 ? tree.notebooks[0] : null;
    if (!nb) return;

    const nbId = nodeId(nb, 'root');
    setOpen(new Set([nbId]));

    const sections = (nb.children || []).filter((c) => c.type === 'section');
    if (sections.length === 1) {
      // onNodeClick 内部已 try/catch 住接口调用，这里再兜一层防 unhandled rejection
      toggle(sections[0], nodeId(sections[0], 'root')).catch(() => {});
    }
  }, [tree, toggle]);

  const renderNode = (node: TreeNode, parentId: string): ReactElement => {
    const id = nodeId(node, parentId);
    const isOpen = open.has(id);

    const meta = (() => {
      if (node.type === 'notebook') return `${node.sections ?? 0} 分区`;
      if (node.type === 'section') return node.valid ? `${node.size_mb} MB` : '格式无效';
      if (node.type === 'section-all') return `${node.pages} 页`;
      if (node.type === 'page') return node.chars ? `${node.chars} 字` : '空页';
      return '';
    })();

    const state = pages[id];

    return (
      <div key={id} className="border-l border-gray-700 ml-1.5 pl-2">
        <div
          onClick={() => toggle(node, id)}
          className={`flex items-center gap-1.5 px-1.5 py-1 rounded-md cursor-pointer text-[12.5px] hover:bg-gray-700 ${
            node.type === 'notebook' ? 'font-medium' : ''
          } ${node.type === 'section' && !node.valid ? 'text-red-400' : ''}`}
        >
          <span className="text-gray-500 text-[10px] w-2.5">{isOpen ? '▾' : '▸'}</span>
          <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap">{node.name}</span>
          <span className="text-gray-500 text-[11px] whitespace-nowrap">{meta}</span>
        </div>

        {isOpen && node.type === 'section' && (
          <>
            {/* 顺序要紧：loading 态既没有 list 也没有 error */}
            {!state || ('loading' in state && state.loading) ? (
              <p className="text-xs text-gray-500 px-2 py-1">解析中…</p>
            ) : 'error' in state ? (
              <p className="text-[11.5px] text-red-600 px-2 py-1">{state.error}</p>
            ) : !('list' in state) ? (
              <p className="text-[11.5px] text-red-600 px-2 py-1">返回数据异常：缺少页列表</p>
            ) : (
              <>
                {state.degraded && (
                  <p className="text-[11.5px] text-amber-600 px-2 py-1">
                    容错解析：该文件有截断数据，内容可能不完整
                  </p>
                )}
                {state.list.length === 0 ? (
                  <p className="text-xs text-gray-500 px-2 py-1">该分区没有解析出页面</p>
                ) : (
                  <>
                    {renderNode(
                      {
                        type: 'section-all',
                        name: `整分区 · 全部 ${state.list.length} 页`,
                        path: node.path,
                        pages: state.list.length,
                      },
                      id
                    )}
                    {state.list.map((p) =>
                      renderNode(
                        {
                          type: 'page',
                          name: p.title,
                          index: p.index,
                          chars: p.chars,
                          images: p.images,
                          path: node.path,
                        },
                        id
                      )
                    )}
                  </>
                )}
              </>
            )}
          </>
        )}

        {isOpen && node.children?.map((c) => renderNode(c, id))}
      </div>
    );
  };

  if (!tree) return null;

  return (
    <div className="max-h-[300px] overflow-y-auto mt-2">
      {tree.notebooks.map((nb) => renderNode(nb, 'root'))}
    </div>
  );
}
