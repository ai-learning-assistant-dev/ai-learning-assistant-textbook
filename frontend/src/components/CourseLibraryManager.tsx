import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AiPersona,
  AppConfig,
  Chapter,
  ConfigResponse,
  CourseData,
  Exercise,
  ExerciseOption,
  LeadingQuestion,
  Section,
} from '../types';

type LibraryConnectionState = 'idle' | 'testing' | 'connected' | 'failed';
type BusyAction = 'none' | 'refresh' | 'upload' | 'delete' | 'verify' | 'export';

interface CourseLibraryManagerProps {
  isOpen: boolean;
  onClose: () => void;
  getCoursePayload: () => CourseData;
}

interface OnlineCourse {
  course_id?: string;
  id?: string;
  title?: string;
  name?: string;
  description?: string;
  category?: string;
  chapters?: unknown[];
  sections?: unknown[];
  created_at?: string;
  updated_at?: string;
}

interface BackendCourse {
  course_id: string;
  name?: string;
  title?: string;
  description?: string;
  category?: string;
  contributors?: string;
  icon_url?: string;
  default_ai_persona_id?: string | null;
}

interface BackendChapter {
  chapter_id: string;
  title: string;
  chapter_order?: number;
  order?: number;
  sections?: BackendSection[];
}

interface BackendSection {
  section_id: string;
  title: string;
  section_order?: number;
  order?: number;
  estimated_time?: number;
  video_url?: string;
  knowledge_content?: string;
  knowledge_points?: Section['knowledge_points'];
  video_subtitles?: Section['video_subtitles'];
}

interface BackendExercise {
  exercise_id: string;
  question: string;
  type_status?: string;
  type?: string;
  score?: number;
  answer?: string;
  options?: BackendExerciseOption[];
}

interface BackendExerciseOption {
  option_id: string;
  option_text?: string;
  text?: string;
  is_correct?: boolean;
}

interface BackendLeadingQuestion {
  question_id: string;
  question: string;
}

interface BackendAiPersona {
  persona_id: string;
  name: string;
  prompt?: string;
  is_default_template?: boolean;
}

interface DialogState {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  onConfirm?: () => void;
}

interface ValidationResult {
  level: 'ok' | 'warning' | 'error';
  label: string;
  detail: string;
}

const DEFAULT_COURSES_API_BASE = 'http://127.0.0.1:7100';

function courseIdForApi(raw: string): string {
  const s = raw.trim().toLowerCase();
  if (!s) return s;
  const hexOnly = s.replace(/-/g, '');
  if (hexOnly.length === 32 && /^[0-9a-f]+$/.test(hexOnly)) {
    return `${hexOnly.slice(0, 8)}-${hexOnly.slice(8, 12)}-${hexOnly.slice(12, 16)}-${hexOnly.slice(16, 20)}-${hexOnly.slice(20, 32)}`;
  }
  return s;
}

async function readJsonResponse(response: Response): Promise<Record<string, unknown>> {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return { message: text };
  }
}

async function postJson(path: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const body = await readJsonResponse(response);
  if (!response.ok || body.success === false) {
    throw new Error((body.message as string) || (body.error as string) || `HTTP ${response.status}`);
  }
  return body;
}

function pickData<T>(body: Record<string, unknown>): T {
  return body.data as T;
}

function createFallbackPersona(courseTitle: string, personaId?: string | null): AiPersona {
  return {
    persona_id: personaId || crypto.randomUUID(),
    name: courseTitle || 'default',
    prompt: '',
    is_default_template: true,
  };
}

function mapExerciseType(type: unknown): string {
  const raw = String(type ?? '').trim();
  if (raw === '0') return '单选';
  if (raw === '1') return '多选';
  if (raw === '2') return '简答';
  return raw || '单选';
}

function downloadCourseJson(course: CourseData) {
  const json = JSON.stringify(course, null, 2);
  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `course-${course.course_id || Date.now()}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function pickCourseList(body: Record<string, unknown>): OnlineCourse[] {
  const data = body.data;
  if (Array.isArray(data)) return data as OnlineCourse[];
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.data)) return obj.data as OnlineCourse[];
    if (Array.isArray(obj.items)) return obj.items as OnlineCourse[];
    if (Array.isArray(obj.list)) return obj.list as OnlineCourse[];
    if (Array.isArray(obj.records)) return obj.records as OnlineCourse[];
  }
  if (Array.isArray(body.courses)) return body.courses as OnlineCourse[];
  if (Array.isArray(body.items)) return body.items as OnlineCourse[];
  return [];
}

function getOnlineCourseId(course: OnlineCourse): string {
  return (course.course_id || course.id || '').trim();
}

function getOnlineCourseTitle(course: OnlineCourse): string {
  return (course.name || course.title || '未命名课程').trim();
}

function countKnowledgePoints(course: CourseData): number {
  return course.chapters.reduce((sum, chapter) => {
    return sum + chapter.sections.reduce((sectionSum, section) => {
      return sectionSum + (section.knowledge_points?.key_points?.length ?? 0);
    }, 0);
  }, 0);
}

function countVideoSubtitles(course: CourseData): number {
  return course.chapters.reduce((sum, chapter) => {
    return sum + chapter.sections.reduce((sectionSum, section) => {
      return sectionSum + (Array.isArray(section.video_subtitles) ? section.video_subtitles.length : 0);
    }, 0);
  }, 0);
}

function mapOptions(options: BackendExerciseOption[] = []): ExerciseOption[] {
  return options.map((option) => ({
    option_id: option.option_id,
    text: option.text ?? option.option_text ?? '',
    is_correct: !!option.is_correct,
  }));
}

function mapExercises(exercises: BackendExercise[] = []): Exercise[] {
  return exercises.map((exercise) => ({
    exercise_id: exercise.exercise_id,
    question: exercise.question ?? '',
    score: typeof exercise.score === 'number' ? exercise.score : 0,
    type: mapExerciseType(exercise.type ?? exercise.type_status),
    answer: exercise.answer ?? '',
    options: mapOptions(exercise.options),
  }));
}

function mapLeadingQuestions(questions: BackendLeadingQuestion[] = []): LeadingQuestion[] {
  return questions.map((question) => ({
    question_id: question.question_id,
    question: question.question ?? '',
  }));
}

async function fetchSectionDetails(sectionId: string): Promise<{
  exercises: Exercise[];
  leading_questions: LeadingQuestion[];
}> {
  const [exerciseBody, questionBody] = await Promise.all([
    postJson('/api/exercises/getExercisesWithOptionsBySection', { section_id: sectionId }),
    postJson('/api/leading-questions/searchBySection', { section_id: sectionId, page: 1, limit: 1000 }),
  ]);

  return {
    exercises: mapExercises(pickData<BackendExercise[]>(exerciseBody) ?? []),
    leading_questions: mapLeadingQuestions(pickData<BackendLeadingQuestion[]>(questionBody) ?? []),
  };
}

async function buildExportCourse(courseId: string): Promise<CourseData> {
  const courseBody = await postJson('/api/courses/getById', { course_id: courseId });
  const course = pickData<BackendCourse>(courseBody);
  if (!course) {
    throw new Error('课程不存在或读取失败');
  }

  const title = course.name || course.title || '未命名课程';
  let aiPersona = createFallbackPersona(title, course.default_ai_persona_id);
  if (course.default_ai_persona_id) {
    try {
      const personaBody = await postJson('/api/ai-personas/getById', {
        persona_id: course.default_ai_persona_id,
      });
      const persona = pickData<BackendAiPersona>(personaBody);
      if (persona) {
        aiPersona = {
          persona_id: persona.persona_id,
          name: persona.name || title,
          prompt: persona.prompt ?? '',
          is_default_template: persona.is_default_template ?? true,
        };
      }
    } catch {
      aiPersona = createFallbackPersona(title, course.default_ai_persona_id);
    }
  }

  const treeBody = await postJson('/api/courses/getCourseChaptersSections', {
    course_id: courseId,
    user_id: '00000000-0000-4000-8000-000000000000',
  });
  const treeData = pickData<{ chapters?: BackendChapter[] }>(treeBody);
  const backendChapters = treeData?.chapters ?? [];

  const chapters: Chapter[] = [];
  for (const chapter of backendChapters) {
    const sections: Section[] = [];
    const backendSections = [...(chapter.sections ?? [])].sort(
      (a, b) => (a.section_order ?? a.order ?? 0) - (b.section_order ?? b.order ?? 0)
    );

    for (const section of backendSections) {
      const details = await fetchSectionDetails(section.section_id);
      sections.push({
        section_id: section.section_id,
        title: section.title ?? '',
        order: section.section_order ?? section.order ?? sections.length,
        estimated_time: section.estimated_time ?? 0,
        video_url: section.video_url ?? '',
        knowledge_content: section.knowledge_content ?? '',
        knowledge_points: section.knowledge_points ?? { key_points: [] },
        video_subtitles: section.video_subtitles ?? [],
        leading_questions: details.leading_questions,
        exercises: details.exercises,
      });
    }

    chapters.push({
      chapter_id: chapter.chapter_id,
      title: chapter.title ?? '',
      order: chapter.chapter_order ?? chapter.order ?? chapters.length,
      sections,
    });
  }

  return {
    course_id: course.course_id,
    title,
    description: course.description ?? '',
    ai_persona: aiPersona,
    category: (course.category as CourseData['category']) || '职业技能',
    contributors: course.contributors ?? '志愿者',
    icon_url: course.icon_url ?? '',
    chapters: chapters.sort((a, b) => a.order - b.order),
  };
}

function validateCourse(course: CourseData): ValidationResult[] {
  const results: ValidationResult[] = [];
  const chapterCount = course.chapters.length;
  const sectionCount = course.chapters.reduce((sum, chapter) => sum + chapter.sections.length, 0);
  const exerciseCount = course.chapters.reduce(
    (sum, chapter) => sum + chapter.sections.reduce((inner, section) => inner + section.exercises.length, 0),
    0
  );
  const leadingQuestionCount = course.chapters.reduce(
    (sum, chapter) => sum + chapter.sections.reduce((inner, section) => inner + section.leading_questions.length, 0),
    0
  );

  if (!course.course_id?.trim()) {
    results.push({ level: 'error', label: '课程 ID', detail: '缺少 course_id，不能导入课程库。' });
  }
  if (!course.title?.trim()) {
    results.push({ level: 'error', label: '课程标题', detail: '缺少 title，课程库无法建立名称索引。' });
  }
  if (!course.category?.trim()) {
    results.push({ level: 'warning', label: '课程分类', detail: '缺少 category，将依赖编辑器默认分类。' });
  }
  if (!course.ai_persona?.persona_id || !course.ai_persona?.name) {
    results.push({ level: 'warning', label: 'AI 人设', detail: 'AI persona 不完整，导入后默认助教体验可能不稳定。' });
  }
  if (chapterCount === 0 || sectionCount === 0) {
    results.push({ level: 'error', label: '课程结构', detail: '至少需要 1 个章节和 1 个小节。' });
  }

  const missingChapterId = course.chapters.some((chapter) => !chapter.chapter_id?.trim());
  const missingSectionId = course.chapters.some((chapter) =>
    chapter.sections.some((section) => !section.section_id?.trim())
  );
  if (missingChapterId || missingSectionId) {
    results.push({ level: 'error', label: '结构主键', detail: '章节或小节缺少主键，后端无法建立关联关系。' });
  }

  const emptyContent = course.chapters.some((chapter) =>
    chapter.sections.some((section) => !section.knowledge_content?.trim())
  );
  if (emptyContent) {
    results.push({ level: 'warning', label: '知识内容', detail: '存在小节正文为空，上传后可测试但学习内容会不完整。' });
  }

  results.push({
    level: 'ok',
    label: '内容统计',
    detail: `${chapterCount} 章 / ${sectionCount} 节 / ${exerciseCount} 题 / ${leadingQuestionCount} 个引导问题`,
  });
  results.push({
    level: 'ok',
    label: '扩展字段',
    detail: `${countKnowledgePoints(course)} 个知识点 / ${countVideoSubtitles(course)} 条字幕记录`,
  });

  return results;
}

const CourseLibraryManager: React.FC<CourseLibraryManagerProps> = ({ isOpen, onClose, getCoursePayload }) => {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_COURSES_API_BASE);
  const [connectionState, setConnectionState] = useState<LibraryConnectionState>('idle');
  const [statusMessage, setStatusMessage] = useState('请先测试课程库后端连接。');
  const [courses, setCourses] = useState<OnlineCourse[]>([]);
  const [busyAction, setBusyAction] = useState<BusyAction>('none');
  const [searchText, setSearchText] = useState('');
  const [dialog, setDialog] = useState<DialogState>({ isOpen: false, title: '', message: '' });
  const [lastVerifiedCourseId, setLastVerifiedCourseId] = useState('');

  const coursePayload = useMemo(() => getCoursePayload(), [getCoursePayload, isOpen, busyAction]);
  const validationResults = useMemo(() => validateCourse(coursePayload), [coursePayload]);
  const hasBlockingError = validationResults.some((item) => item.level === 'error');

  const filteredCourses = useMemo(() => {
    const q = searchText.trim().toLowerCase();
    if (!q) return courses;
    return courses.filter((course) => {
      const id = getOnlineCourseId(course).toLowerCase();
      const title = getOnlineCourseTitle(course).toLowerCase();
      return id.includes(q) || title.includes(q);
    });
  }, [courses, searchText]);

  const closeDialog = () => setDialog({ isOpen: false, title: '', message: '' });

  const saveBackendUrl = useCallback(async () => {
    const response = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ courses_api_base: backendUrl.trim() || DEFAULT_COURSES_API_BASE }),
    });
    const body = (await response.json()) as ConfigResponse;
    if (!response.ok || !body.success) {
      throw new Error(body.error || `保存配置失败：HTTP ${response.status}`);
    }
    setBackendUrl(body.config?.courses_api_base || backendUrl.trim() || DEFAULT_COURSES_API_BASE);
  }, [backendUrl]);

  const loadConfig = useCallback(async () => {
    try {
      const response = await fetch('/api/config');
      const body = (await response.json()) as ConfigResponse;
      if (body.success && body.config) {
        const config = body.config as AppConfig;
        setBackendUrl(config.courses_api_base || DEFAULT_COURSES_API_BASE);
      }
    } catch {
      setBackendUrl(DEFAULT_COURSES_API_BASE);
    }
  }, []);

  const refreshCourses = useCallback(async (saveConfigFirst = false) => {
    if (saveConfigFirst) {
      await saveBackendUrl();
    }

    setBusyAction('refresh');
    try {
      const response = await fetch('/api/courses/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page: 1, limit: 100 }),
      });
      const body = await readJsonResponse(response);
      if (!response.ok || body.success === false) {
        throw new Error((body.message as string) || (body.error as string) || `HTTP ${response.status}`);
      }

      const list = pickCourseList(body);
      setCourses(list);
      setConnectionState('connected');
      setStatusMessage(`已连接课程库，共读取 ${list.length} 门课程。`);
    } catch (error) {
      setConnectionState('failed');
      setStatusMessage(error instanceof Error ? error.message : '课程库连接失败。');
      setCourses([]);
    } finally {
      setBusyAction('none');
    }
  }, [saveBackendUrl]);

  const testConnection = useCallback(async () => {
    setConnectionState('testing');
    setStatusMessage('正在测试课程库连接...');
    await refreshCourses(true);
  }, [refreshCourses]);

  const verifyCourse = useCallback(async (courseId: string) => {
    const normalizedId = courseIdForApi(courseId);
    setBusyAction('verify');
    try {
      const response = await fetch('/api/courses/getById', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: normalizedId }),
      });
      const body = await readJsonResponse(response);
      if (!response.ok || body.success === false) {
        throw new Error((body.message as string) || (body.error as string) || `HTTP ${response.status}`);
      }
      setLastVerifiedCourseId(normalizedId);
      setStatusMessage(`课程 ${normalizedId} 可从学科培训后端读取。`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : '课程读取测试失败。');
    } finally {
      setBusyAction('none');
    }
  }, []);

  const uploadCourse = useCallback(async () => {
    const payload = getCoursePayload();
    const currentValidation = validateCourse(payload);
    const normalizedId = courseIdForApi(payload.course_id || '');
    if (!normalizedId || currentValidation.some((item) => item.level === 'error')) {
      setStatusMessage('当前课程存在阻塞问题，请先处理红色校验项。');
      return;
    }

    const sameId = courses.find((course) => courseIdForApi(getOnlineCourseId(course)) === normalizedId);
    const sameName = courses.find((course) => getOnlineCourseTitle(course) === payload.title);
    const existing = sameId || sameName;

    const doUpload = async () => {
      closeDialog();
      setBusyAction('upload');
      try {
        const response = await fetch('/api/courses/import?override=true', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...payload, course_id: normalizedId }),
        });
        const body = await readJsonResponse(response);
        if (!response.ok || body.success === false) {
          throw new Error((body.message as string) || (body.error as string) || `HTTP ${response.status}`);
        }
        setStatusMessage((body.message as string) || '当前课程已上传到学科培训课程库。');
        await refreshCourses(false);
        await verifyCourse(normalizedId);
      } catch (error) {
        setStatusMessage(error instanceof Error ? error.message : '课程上传失败。');
      } finally {
        setBusyAction('none');
      }
    };

    if (existing) {
      setDialog({
        isOpen: true,
        title: '覆盖线上课程',
        message: `线上课程库已存在「${getOnlineCourseTitle(existing)}」。继续上传会使用后端 override 流程覆盖该课程及其关联章节、小节、题目。`,
        confirmText: '覆盖并上传',
        onConfirm: () => void doUpload(),
      });
      return;
    }

    await doUpload();
  }, [courses, getCoursePayload, refreshCourses, verifyCourse]);

  const requestDeleteCourse = (course: OnlineCourse) => {
    const courseId = courseIdForApi(getOnlineCourseId(course));
    if (!courseId) {
      setStatusMessage('该线上课程缺少 course_id，无法删除。');
      return;
    }
    setDialog({
      isOpen: true,
      title: '删除线上课程',
      message: `确认删除「${getOnlineCourseTitle(course)}」吗？后端会同步删除该课程下的章节、小节、练习题和引导问题；本地正在编辑的课程不会被删除。`,
      confirmText: '确认删除',
      onConfirm: () => void deleteCourse(courseId),
    });
  };

  const exportCourse = async (course: OnlineCourse) => {
    const courseId = courseIdForApi(getOnlineCourseId(course));
    if (!courseId) {
      setStatusMessage('该线上课程缺少 course_id，无法导出。');
      return;
    }

    setBusyAction('export');
    try {
      const exportedCourse = await buildExportCourse(courseId);
      downloadCourseJson(exportedCourse);
      setStatusMessage(`已导出「${exportedCourse.title}」为 course.json。`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : '导出课程失败。');
    } finally {
      setBusyAction('none');
    }
  };

  const deleteCourse = async (courseId: string) => {
    closeDialog();
    setBusyAction('delete');
    try {
      const response = await fetch('/api/courses/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: courseId }),
      });
      const body = await readJsonResponse(response);
      if (!response.ok || body.success === false) {
        throw new Error((body.message as string) || (body.error as string) || `HTTP ${response.status}`);
      }
      setStatusMessage('线上课程已删除。');
      await refreshCourses(false);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : '删除线上课程失败。');
    } finally {
      setBusyAction('none');
    }
  };

  useEffect(() => {
    if (isOpen) {
      void loadConfig();
    }
  }, [isOpen, loadConfig]);

  if (!isOpen) return null;

  const currentCourseId = courseIdForApi(coursePayload.course_id || '');
  const isConnected = connectionState === 'connected';
  const isBusy = busyAction !== 'none' || connectionState === 'testing';

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30 backdrop-blur-sm">
      <div className="h-full w-full max-w-5xl bg-slate-50 shadow-2xl flex flex-col border-l border-slate-200">
        <div className="px-6 py-4 bg-white border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">课程库管理</h2>
            <p className="text-sm text-slate-500 mt-1">连接学科培训后端，上传、测试和删除线上课程。</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 rounded-md text-slate-600 hover:bg-slate-100 transition-colors"
          >
            关闭
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          <section className="bg-white border border-slate-200 rounded-lg p-4">
            <div className="flex flex-col lg:flex-row gap-3 lg:items-end">
              <label className="flex-1">
                <span className="block text-sm font-semibold text-slate-700 mb-1">学科培训后端地址</span>
                <input
                  value={backendUrl}
                  onChange={(event) => setBackendUrl(event.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  placeholder={DEFAULT_COURSES_API_BASE}
                />
              </label>
              <button
                type="button"
                onClick={testConnection}
                disabled={isBusy}
                className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
              >
                {connectionState === 'testing' ? '连接中...' : '测试连接'}
              </button>
              <button
                type="button"
                onClick={() => void refreshCourses(false)}
                disabled={!isConnected || isBusy}
                className="px-4 py-2 rounded-md bg-slate-800 text-white text-sm font-semibold hover:bg-slate-900 disabled:bg-slate-300 disabled:cursor-not-allowed"
              >
                刷新课程
              </button>
            </div>
            <div
              className={`mt-3 text-sm px-3 py-2 rounded-md ${
                connectionState === 'connected'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : connectionState === 'failed'
                    ? 'bg-red-50 text-red-700 border border-red-200'
                    : 'bg-slate-100 text-slate-600 border border-slate-200'
              }`}
            >
              {statusMessage}
            </div>
          </section>

          <section className="bg-white border border-slate-200 rounded-lg p-4">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">当前课程</h3>
                <p className="text-sm text-slate-500 mt-1">{coursePayload.title || '未命名课程'}</p>
                <p className="text-xs text-slate-400 mt-1 break-all">{currentCourseId || '未填写 course_id'}</p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={uploadCourse}
                  disabled={!isConnected || isBusy || hasBlockingError}
                  className="px-4 py-2 rounded-md bg-amber-500 text-white text-sm font-semibold hover:bg-amber-600 disabled:bg-slate-300 disabled:cursor-not-allowed"
                >
                  {busyAction === 'upload' ? '上传中...' : '上传当前课程'}
                </button>
                <button
                  type="button"
                  onClick={() => void verifyCourse(currentCourseId)}
                  disabled={!isConnected || isBusy || !currentCourseId}
                  className="px-4 py-2 rounded-md bg-white border border-slate-300 text-slate-700 text-sm font-semibold hover:bg-slate-50 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
                >
                  测试读取
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              {validationResults.map((item) => (
                <div
                  key={`${item.label}-${item.detail}`}
                  className={`rounded-md border px-3 py-2 ${
                    item.level === 'error'
                      ? 'bg-red-50 border-red-200'
                      : item.level === 'warning'
                        ? 'bg-amber-50 border-amber-200'
                        : 'bg-emerald-50 border-emerald-200'
                  }`}
                >
                  <div className="text-sm font-semibold text-slate-800">{item.label}</div>
                  <div className="text-xs text-slate-600 mt-1">{item.detail}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="bg-white border border-slate-200 rounded-lg p-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">线上课程库</h3>
                <p className="text-sm text-slate-500">已读取 {filteredCourses.length} / {courses.length} 门课程</p>
              </div>
              <input
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                className="w-full md:w-72 px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                placeholder="搜索课程标题或 ID"
              />
            </div>

            {!isConnected ? (
              <div className="text-sm text-slate-500 bg-slate-100 border border-slate-200 rounded-md p-4">
                需要先连接学科培训后端，才能查看和管理线上课程。
              </div>
            ) : filteredCourses.length === 0 ? (
              <div className="text-sm text-slate-500 bg-slate-100 border border-slate-200 rounded-md p-4">
                暂无匹配课程。
              </div>
            ) : (
              <div className="divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
                {filteredCourses.map((course) => {
                  const courseId = getOnlineCourseId(course);
                  const normalizedId = courseIdForApi(courseId);
                  const title = getOnlineCourseTitle(course);
                  const verified = lastVerifiedCourseId && lastVerifiedCourseId === normalizedId;
                  return (
                    <div key={normalizedId || title} className="p-4 flex flex-col lg:flex-row lg:items-center gap-3 bg-white">
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-slate-900 truncate">{title}</div>
                        <div className="text-xs text-slate-500 break-all mt-1">{normalizedId || '缺少 course_id'}</div>
                        <div className="text-xs text-slate-400 mt-1">
                          {course.category || '未分类'}{verified ? ' · 已通过读取测试' : ''}
                        </div>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => void verifyCourse(normalizedId)}
                          disabled={isBusy || !normalizedId}
                          className="px-3 py-2 rounded-md border border-slate-300 bg-white text-slate-700 text-sm hover:bg-slate-50 disabled:bg-slate-100 disabled:text-slate-400"
                        >
                          测试
                        </button>
                        <button
                          type="button"
                          onClick={() => void exportCourse(course)}
                          disabled={isBusy || !normalizedId}
                          className="px-3 py-2 rounded-md border border-blue-200 bg-blue-50 text-blue-700 text-sm hover:bg-blue-100 disabled:bg-slate-100 disabled:text-slate-400"
                        >
                          {busyAction === 'export' ? '导出中' : '导出'}
                        </button>
                        <button
                          type="button"
                          onClick={() => requestDeleteCourse(course)}
                          disabled={isBusy || !normalizedId}
                          className="px-3 py-2 rounded-md bg-red-600 text-white text-sm hover:bg-red-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>

      {dialog.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-2xl border border-slate-200 p-5 w-full max-w-md mx-4">
            <h3 className="text-lg font-bold text-slate-900">{dialog.title}</h3>
            <p className="text-sm text-slate-600 mt-3 whitespace-pre-line">{dialog.message}</p>
            <div className="flex justify-end gap-2 mt-5">
              <button
                type="button"
                onClick={closeDialog}
                className="px-4 py-2 rounded-md bg-slate-100 text-slate-700 text-sm hover:bg-slate-200"
              >
                取消
              </button>
              <button
                type="button"
                onClick={dialog.onConfirm}
                className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700"
              >
                {dialog.confirmText || '确认'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CourseLibraryManager;
