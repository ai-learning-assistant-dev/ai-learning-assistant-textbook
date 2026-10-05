/**
 * 服务端目录浏览。
 *
 * 浏览器选不了本地文件夹，所以目录由服务端列：空路径先出盘符，
 * 逐级点进去（单击同时把路径回填到输入框），「选定」确认。
 */

import { useCallback, useEffect, useState } from 'react';
import { browseDirs } from '../api';
import type { BrowseResult } from '../types';

interface Props {
  initialPath: string;
  onToast: (message: string, isError?: boolean) => void;
  onPick: (path: string) => void;
}

export default function DirectoryBrowser({ initialPath, onToast, onPick }: Props) {
  const [dir, setDir] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadDir = useCallback(
    async (path: string) => {
      setLoading(true);
      try {
        setDir(await browseDirs(path));
      } catch (e) {
        onToast(e instanceof Error ? e.message : '读取目录失败', true);
      } finally {
        setLoading(false);
      }
    },
    [onToast]
  );

  useEffect(() => {
    loadDir(initialPath);
  }, [initialPath, loadDir]);

  return (
    <div className="border border-dashed border-gray-600 rounded-lg p-2.5 mb-2.5">
      <div className="flex items-center gap-2 mb-1.5">
        <button
          disabled={!dir?.parent}
          onClick={() => dir?.parent && loadDir(dir.parent)}
          className="px-2.5 py-1.5 text-xs rounded-lg border bg-gray-700 border-gray-600 text-gray-200 hover:bg-gray-600 disabled:opacity-50 whitespace-nowrap"
        >
          ↑ 上级
        </button>
        <button
          disabled={!dir?.path}
          onClick={() => dir?.path && onPick(dir.path)}
          className="px-2.5 py-1.5 text-xs rounded-lg border bg-gray-700 border-gray-600 text-gray-200 hover:bg-gray-600 disabled:opacity-50 whitespace-nowrap"
        >
          选定
        </button>
        <span className="text-[11px] text-gray-400 break-all">
          {dir?.path || '（先选一个盘符）'}
        </span>
      </div>

      <div className="max-h-[190px] overflow-y-auto">
        {loading ? (
          <p className="text-xs text-gray-500 p-2">加载中…</p>
        ) : !dir || dir.dirs.length === 0 ? (
          <p className="text-xs text-gray-500 p-2">没有子目录</p>
        ) : (
          dir.dirs.map((item) => (
            <div
              key={item.path}
              onClick={() => {
                // 单击进入下一层，同时把路径回填到输入框，省一次复制粘贴
                onPick(item.path);
                loadDir(item.path);
              }}
              className="flex justify-between items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-[12.5px] hover:bg-gray-700"
            >
              <span>{item.name}</span>
              <span className="text-[11px] text-gray-400 whitespace-nowrap">
                {item.sections ? `${item.sections} 个分区` : ''}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
