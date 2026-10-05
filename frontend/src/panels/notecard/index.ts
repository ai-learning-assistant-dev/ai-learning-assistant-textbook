/**
 * 笔记制卡面板的对外出口。
 *
 * App.tsx 只需从 panels/notecard 导入 NotecardPanel
 */

export { default as NotecardPanel } from './NotecardPanel';
export type { Card, CardIssue, NoteSource, Report } from './types';
