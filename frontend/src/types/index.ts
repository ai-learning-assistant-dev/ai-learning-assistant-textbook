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
  id: string;
  text: string;
  is_correct: boolean;
}

export interface Exercise {
  id: string;
  question: string;
  score: number;
  type: string;
  options: ExerciseOption[];
}

export interface LeadingQuestion {
  id: string;
  question: string;
}

export interface Section {
  id: string;
  title: string;
  order: number;
  estimated_time: number;
  video_url: string;
  leading_questions: LeadingQuestion[];
  exercises: Exercise[];
}

export interface Chapter {
  id: string;
  title: string;
  order: number;
  sections: Section[];
}

export interface CourseData {
  id: string;
  title: string;
  description: string;
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