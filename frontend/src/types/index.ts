// API 响应类型定义
export interface ApiResponse<T = any> {
  success: boolean;
  error?: string;
  data?: T;
}

export interface Model {
  id: string;
  name: string;
  model_name: string;
  api_base: string;
  api_key: string;
}

export interface ModelsResponse extends ApiResponse {
  models: Model[];
}

export interface AppConfig {
  output_directory?: string;
  download_all_parts?: boolean;
  max_concurrent_tasks?: number;
  last_selected_model?: string;
  last_workspace_name?: string;
}

export interface ConfigResponse extends ApiResponse {
  config: AppConfig;
}

export interface CookiesConfigResponse extends ApiResponse {
  configured: boolean;
}

export interface Task {
  id: string;
  url: string;
  video_title?: string;
  status: TaskStatus;
  message: string;
  created_at: string;
  files?: TaskFiles;
}

export type TaskStatus =
  | 'pending'
  | 'downloading'
  | 'summarizing'
  | 'completed'
  | 'failed'
  | 'stopping'
  | 'stopped';

export interface TaskFiles {
  video_dir?: string;
  subtitle?: string;
  cover?: string;
  summary_json?: string;
  content_md?: string;
  exercises?: string;
  questions?: string;
}

export interface TasksResponse extends ApiResponse {
  tasks: Task[];
}

export interface CreateTaskRequest {
  urls: string[];
  workspace_name: string;
  model_name: string;
  download_all_parts: boolean;
  generate_options: GenerateOptions;
}

export interface GenerateOptions {
  summary: boolean;
  full_content: boolean;
  exercises: boolean;
  questions: boolean;
}

export interface CreateTaskResponse extends ApiResponse {
  task_ids: string[];
  total_videos?: number;
}

export interface AlertProps {
  message: string;
  type: 'success' | 'error' | 'warning';
  onClose?: () => void;
}

export interface ModelFormData {
  name: string;
  model_name: string;
  api_base: string;
  api_key: string;
}

export interface Workspace {
  name: string;
  path: string;
  created_at: string;
}

export interface WorkspacesResponse extends ApiResponse {
  workspaces: Workspace[];
}

// 课程数据结构类型定义
export interface ExerciseOption {
  option_id: string;
  text: string;
  is_correct: boolean;
}

export interface Exercise {
  exercise_id: string;
  question: string;
  score: number;
  type: string;
  /** 简答题的参考答案 */
  answer?: string;
  options: ExerciseOption[];
}

export interface LeadingQuestion {
  question_id: string;
  question: string;
}

export interface Section {
  section_id: string;
  title: string;
  order: number;
  estimated_time: number;
  video_url: string;
  /** 完整知识内容（通常为 Markdown），与生成管线中的全文总结一致 */
  knowledge_content?: string;
  leading_questions: LeadingQuestion[];
  exercises: Exercise[];
}

export interface Chapter {
  chapter_id: string;
  title: string;
  order: number;
  sections: Section[];
}

export interface AiPersona {
  persona_id: string;
  name: string;
  prompt: string;
  is_default_template: boolean;
}

/** course.json 中课程分类，仅允许以下取值 */
export type CourseCategory =
  | '职业技能'
  | '文化基础'
  | '工具使用'
  | '人文素养';

export const COURSE_CATEGORIES: readonly CourseCategory[] = [
  '职业技能',
  '文化基础',
  '工具使用',
  '人文素养',
] as const;

export interface CourseData {
  course_id: string;
  title: string;
  description: string;
  /** 课程 AI 人设，导入学习助手时按对象结构提交 */
  ai_persona: AiPersona;
  /** 兼容历史字段（旧版仅有字符串人设） */
  teacher_persona?: string;
  /** 课程分类，默认「职业技能」 */
  category: CourseCategory;
  icon_url?: string;  // 课程图标，支持base64或URL
  chapters: Chapter[];
}

export interface CookiesConfigResponse extends ApiResponse {
  configured: boolean;
  has_value?: boolean;  // 添加此项以表示是否有已保存的值
}

export interface UpdateCookiesRequest {
  sessdata: string;
}

export interface TestCookiesRequest {
  sessdata: string;
}

export interface TestCookiesResponse extends ApiResponse {
  message?: string;
}