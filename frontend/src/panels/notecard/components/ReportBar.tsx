/** 顶栏右侧的校验报告：总数 / 无问题 / 错误 / 警告 + 出现最多的 6 个问题码。 */

import type { ReactNode } from 'react';
import type { Report } from '../types';

const TONE: Record<'ok' | 'warn' | 'err' | 'plain', string> = {
  ok: 'text-green-300 bg-green-500/15 border-green-500/30',
  warn: 'text-amber-300 bg-amber-500/15 border-amber-500/30',
  err: 'text-red-300 bg-red-500/15 border-red-500/30',
  plain: 'text-gray-300 bg-gray-700 border-gray-600',
};

function Badge({ tone, children }: { tone: keyof typeof TONE; children: ReactNode }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs border ${TONE[tone]}`}>
      {children}
    </span>
  );
}

export default function ReportBar({ report }: { report: Report | null }) {
  if (!report) {
    return <span className="text-xs text-gray-500">尚未提取</span>;
  }

  const codes = Object.entries(report.by_code || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div className="flex flex-wrap gap-2 items-center">
      <Badge tone="ok">共 {report.total} 张</Badge>
      <Badge tone={report.clean === report.total ? 'ok' : 'plain'}>无问题 {report.clean}</Badge>
      <Badge tone={report.error ? 'err' : 'ok'}>错误 {report.error}</Badge>
      <Badge tone={report.warning ? 'warn' : 'ok'}>警告 {report.warning}</Badge>
      {codes.map(([code, n]) => (
        <Badge key={code} tone="plain">
          {code} ×{n}
        </Badge>
      ))}
    </div>
  );
}
