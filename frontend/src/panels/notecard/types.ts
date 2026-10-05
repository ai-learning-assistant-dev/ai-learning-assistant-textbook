/**
 * 笔记制卡面板的类型定义。
 *
 * 字段名与后端 services/notecard/note2anki 的返回结构一一对应
 * （Card / validate 报告 / OneNote 树 / 渲染结果）。
 */

/** 卡片上的一条问题：error 阻断导出，warning 只提示 */
export interface CardIssue {
  level: 'error' | 'warning';
  code: string;
  message: string;
}

/** Basic 卡片：正面问句 + 反面答案 */
export interface Card {
  id: string;
  front: string;
  back: string;
  tags: string[];
  source: string;
  issues: CardIssue[];
}

/** validate 的汇总报告 */
export interface Report {
  total: number;
  clean: number;
  error: number;
  warning: number;
  by_code: Record<string, number>;
  blocking: boolean;
}

/**
 * 当前载入的笔记正文。
 *
 * 独立于 UI 持有：来源可能是 OneNote 页、文件、或粘贴，
 * 手动输入框折叠起来时内容也必须还在（迁移前 app.js 的同名约定）。
 */
export interface NoteSource {
  text: string;
  filename: string;
  sourceLabel: string;
}

export type ExtractMode = 'rule' | 'llm';

export interface ExtractPayload {
  text: string;
  filename: string;
  mode: ExtractMode;
  include_section_cards: boolean;
  /** LLM 模式下选中的共享模型（按 name 匹配 config/llm_models.json） */
  model?: string;
}

/** 视频下载面板共享的模型配置条目（config/llm_models.json 里的每一项） */
export interface ModelEntry {
  id: string;
  name: string;
  model_name: string;
  api_base: string;
  api_key?: string;
}

export interface ExtractResult {
  cards: Card[];
  report: Report;
}

export interface ValidateResult {
  cards: Card[];
  report: Report;
}

/** 导出结果：字段名是 written / skipped，不是 notes */
export interface ExportResult {
  written: number;
  skipped: number;
  bytes: number;
  filename: string;
  url: string;
  deck: string;
  report: Report;
}

// ───────────────────────── OneNote 源 ─────────────────────────

export interface BrowseDir {
  name: string;
  path: string;
  sections: number | null;
}

export interface BrowseResult {
  path: string;
  parent: string | null;
  dirs: BrowseDir[];
  one_files?: number;
}

export type TreeNodeType = 'notebook' | 'group' | 'section' | 'page' | 'section-all';

export interface TreeNode {
  type: TreeNodeType;
  name: string;
  path?: string;
  children?: TreeNode[];
  /** notebook：分区数 */
  sections?: number;
  /** section：体积与魔数校验 */
  size_mb?: number;
  valid?: boolean;
  modified?: string;
  /** page */
  index?: number;
  chars?: number;
  images?: number;
  /** section-all */
  pages?: number;
}

export interface ScanResult {
  root: string;
  notebooks: TreeNode[];
  section_count: number;
}

export interface PageMeta {
  index: number;
  title: string;
  chars: number;
  images: number;
}

export interface PagesResult {
  section: string;
  name: string;
  size_mb: number;
  load_seconds: number;
  /** 靠容错补丁解析出来的，内容可能不完整 */
  degraded: boolean;
  pages: PageMeta[];
}

/** 单页 / 整分区渲染结果 */
export interface RenderResult {
  markdown: string;
  title: string;
  source: string;
  filename: string;
  chars: number;
  images?: number;
  degraded?: boolean;
  page_count?: number;
  failed_pages?: number;
}
