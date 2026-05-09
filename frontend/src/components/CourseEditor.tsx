import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useForm, useFieldArray, useWatch, FormProvider, useFormContext } from 'react-hook-form';
import { v4 as uuidv4 } from 'uuid';
import {
  AiPersona,
  CourseData,
  CourseCategory,
  COURSE_CATEGORIES,
  Chapter,
  Section,
  Exercise,
  ExerciseOption,
  KnowledgePoint,
  KnowledgePoints,
  LeadingQuestion,
  VideoSubtitle,
  AppConfig,
  CreateTaskRequest,
  GenerateOptions,
  Task,
} from '../types';
import CourseLibraryManager from './CourseLibraryManager';

const DEFAULT_COURSE_CATEGORY: CourseCategory = '职业技能';

/** 始终挂载，保证 category 在任意选中节点下都参与 getValues/另存为 */
const CategoryHiddenField: React.FC = () => {
  const { register } = useFormContext();
  return <input type="hidden" {...register('category')} />;
};

function normalizeCourseCategory(raw: unknown): CourseCategory {
  if (typeof raw === 'string' && (COURSE_CATEGORIES as readonly string[]).includes(raw)) {
    return raw as CourseCategory;
  }
  return DEFAULT_COURSE_CATEGORY;
}

const createDefaultAiPersona = (courseTitle = '', prompt = ''): AiPersona => ({
  persona_id: uuidv4(),
  name: (courseTitle || '').trim() || 'default',
  prompt,
  is_default_template: true,
});

function readStringId(raw: unknown, primaryKey: string): string {
  if (!raw || typeof raw !== 'object') return uuidv4();
  const record = raw as Record<string, unknown>;
  const value = record[primaryKey] ?? record.id;
  return typeof value === 'string' && value.trim() ? value.trim() : uuidv4();
}

function sanitizeLeadingQuestion(r: LeadingQuestion): LeadingQuestion {
  const raw = r as LeadingQuestion & { id?: string };
  return {
    question_id: raw.question_id || raw.id || uuidv4(),
    question: r.question ?? '',
  };
}

function sanitizeExerciseOption(r: ExerciseOption): ExerciseOption {
  const raw = r as ExerciseOption & { id?: string };
  return {
    option_id: raw.option_id || raw.id || uuidv4(),
    text: r.text ?? '',
    is_correct: !!r.is_correct,
  };
}

function sanitizeExercise(r: Exercise): Exercise {
  const raw = r as Exercise & { id?: string };
  return {
    exercise_id: raw.exercise_id || raw.id || uuidv4(),
    question: r.question ?? '',
    score: typeof r.score === 'number' ? r.score : 0,
    type: r.type ?? '单选',
    answer: r.answer ?? '',
    options: (r.options ?? []).map(sanitizeExerciseOption),
  };
}

function sanitizeKnowledgePoint(raw: unknown): KnowledgePoint {
  if (!raw || typeof raw !== 'object') {
    return { title: '', description: '', time: '' };
  }
  const record = raw as Partial<KnowledgePoint>;
  return {
    title: typeof record.title === 'string' ? record.title : '',
    description: typeof record.description === 'string' ? record.description : '',
    time: typeof record.time === 'string' ? record.time : '',
  };
}

function normalizeKnowledgePoints(raw: unknown): KnowledgePoints {
  if (Array.isArray(raw)) {
    return { key_points: raw.map(sanitizeKnowledgePoint) };
  }
  if (!raw || typeof raw !== 'object') {
    return { key_points: [] };
  }
  const record = raw as { key_points?: unknown };
  if (Array.isArray(record.key_points)) {
    return { key_points: record.key_points.map(sanitizeKnowledgePoint) };
  }
  return { key_points: [] };
}

function sanitizeVideoSubtitle(raw: unknown, index: number): VideoSubtitle {
  if (!raw || typeof raw !== 'object') {
    return { seq: index + 1, start: '', end: '', text: '' };
  }
  const record = raw as Partial<VideoSubtitle>;
  return {
    seq: typeof record.seq === 'number' && Number.isFinite(record.seq) ? record.seq : index + 1,
    start: typeof record.start === 'string' ? record.start : '',
    end: typeof record.end === 'string' ? record.end : '',
    text: typeof record.text === 'string' ? record.text : '',
  };
}

function normalizeVideoSubtitles(raw: unknown): VideoSubtitle[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(sanitizeVideoSubtitle);
}

function sanitizeSection(raw: Section): Section {
  return {
    section_id: readStringId(raw, 'section_id'),
    title: raw.title ?? '',
    order: typeof raw.order === 'number' ? raw.order : 0,
    estimated_time: typeof raw.estimated_time === 'number' ? raw.estimated_time : 0,
    video_url: raw.video_url ?? '',
    knowledge_content: raw.knowledge_content ?? '',
    knowledge_points: normalizeKnowledgePoints(raw.knowledge_points),
    video_subtitles: normalizeVideoSubtitles(raw.video_subtitles),
    leading_questions: (raw.leading_questions ?? []).map(sanitizeLeadingQuestion),
    exercises: (raw.exercises ?? []).map(sanitizeExercise),
  };
}

function sanitizeChapter(raw: Chapter): Chapter {
  return {
    chapter_id: readStringId(raw, 'chapter_id'),
    title: raw.title ?? '',
    order: typeof raw.order === 'number' ? raw.order : 0,
    sections: (raw.sections ?? []).map(sanitizeSection),
  };
}

function sanitizeAiPersona(raw: unknown, courseTitle?: string, legacyTeacherPersona?: string): AiPersona {
  const fallback = createDefaultAiPersona((courseTitle ?? '').trim(), (legacyTeacherPersona ?? '').trim());
  if (!raw || typeof raw !== 'object') {
    return fallback;
  }

  const r = raw as Partial<AiPersona>;
  return {
    persona_id:
      typeof r.persona_id === 'string' && r.persona_id.trim()
        ? r.persona_id.trim()
        : fallback.persona_id,
    name: typeof r.name === 'string' && r.name.trim() ? r.name.trim() : fallback.name,
    prompt: typeof r.prompt === 'string' ? r.prompt : fallback.prompt,
    is_default_template:
      typeof r.is_default_template === 'boolean' ? r.is_default_template : fallback.is_default_template,
  };
}

function sanitizeCourseData(data: Partial<CourseData>): CourseData {
  const raw = data as Partial<CourseData> & { id?: string };
  return {
    course_id: data.course_id || raw.id || uuidv4(),
    title: data.title ?? '',
    description: data.description ?? '',
    ai_persona: sanitizeAiPersona(data.ai_persona, data.title, data.teacher_persona),
    category: normalizeCourseCategory(data.category),
    contributors: data.contributors ?? '志愿者',
    icon_url: data.icon_url ?? '',
    chapters: (data.chapters ?? []).map(sanitizeChapter),
  };
}

/**
 * 学习助手 delete/import 使用带连字符的标准 UUID。
 * 若 course_id 为 32 位 hex（无连字符），格式化为 8-4-4-4-12；已为 UUID 则规范化小写后原样使用。
 */
// ---------------------------------------------------------
// 通用确认/提示对话框组件
// ---------------------------------------------------------
interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  type?: 'info' | 'success' | 'warning' | 'error' | 'confirm';
  onConfirm?: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  type = 'info',
  onConfirm,
  onCancel,
  confirmText = '确定',
  cancelText = '取消'
}) => {
  if (!isOpen) return null;

  const getIconAndColor = () => {
    switch (type) {
      case 'success':
        return { icon: '✅', color: 'text-green-600', btnColor: 'bg-green-500 hover:bg-green-600' };
      case 'warning':
        return { icon: '⚠️', color: 'text-yellow-600', btnColor: 'bg-yellow-500 hover:bg-yellow-600' };
      case 'error':
        return { icon: '❌', color: 'text-red-600', btnColor: 'bg-red-500 hover:bg-red-600' };
      case 'confirm':
        return { icon: '❓', color: 'text-blue-600', btnColor: 'bg-blue-500 hover:bg-blue-600' };
      default:
        return { icon: 'ℹ️', color: 'text-gray-600', btnColor: 'bg-gray-500 hover:bg-gray-600' };
    }
  };

  const { icon, color, btnColor } = getIconAndColor();
  const showCancel = type === 'confirm' || type === 'error' || type === 'warning';

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl border border-gray-200 animate-scale-in">
        <div className="flex items-start gap-3 mb-4">
          <span className="text-2xl">{icon}</span>
          <div className="flex-1">
            <h3 className={`text-lg font-semibold ${color}`}>{title}</h3>
          </div>
        </div>
        <p className="text-gray-700 mb-6 ml-11 whitespace-pre-line">{message}</p>
        <div className="flex justify-end gap-3">
          {showCancel && onCancel && (
            <button
              onClick={onCancel}
              className="px-4 py-2 text-gray-700 bg-gray-200 rounded hover:bg-gray-300 transition-colors"
            >
              {cancelText}
            </button>
          )}
          <button
            onClick={() => {
              if (onConfirm) onConfirm();
              if (onCancel) onCancel();
            }}
            className={`px-4 py-2 text-white rounded transition-colors ${btnColor}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------
// 1. 左侧：递归树组件 (只负责导航和展示结构)
// ---------------------------------------------------------
interface SidebarTreeProps {
  control: any;
  onSelect: (path: string, type: 'course' | 'chapter' | 'section') => void;
  activePath: string | null;
  onAddSection: (chapterIndex: number) => void;
  onAddChapter: () => void;
  onMoveSection: (sourceChapterIndex: number, sourceSectionIndex: number, targetChapterIndex: number, targetSectionIndex: number) => void;
}

const isSectionIncomplete = (sec: Section) => {
  return !sec.video_subtitles?.length ||
         !sec.knowledge_points?.key_points?.length ||
         !sec.knowledge_content ||
         !sec.exercises?.length ||
         !sec.leading_questions?.length;
};

const isChapterIncomplete = (chapter: Chapter) => {
  if (!chapter.sections || chapter.sections.length === 0) return false;
  return chapter.sections.some(isSectionIncomplete);
};

const SidebarTree: React.FC<SidebarTreeProps> = ({ control, onSelect, activePath, onAddSection, onAddChapter, onMoveSection }) => {
  const chapters = useWatch({ control, name: "chapters" });
  const title = useWatch({ control, name: "title" });
  const [draggedSection, setDraggedSection] = useState<{ chapterIndex: number; sectionIndex: number } | null>(null);
  const [dragOverTarget, setDragOverTarget] = useState<{ chapterIndex: number; sectionIndex: number } | null>(null);

  // 计算最近的插入位置
  const calculateClosestInsertPosition = useCallback((mouseY: number, container: HTMLElement): number => {
    const containerRect = container.getBoundingClientRect();
    const sectionElements = Array.from(container.children).filter(
      child => child.classList.contains('section-item')
    ) as HTMLElement[];

    // 如果没有节，插入到索引0
    if (sectionElements.length === 0) {
      return 0;
    }

    let closestIndex = 0;
    let minDistance = Math.abs(mouseY - containerRect.top);

    // 遍历所有节，计算到每个插入点的距离
    sectionElements.forEach((element, idx) => {
      const rect = element.getBoundingClientRect();

      // 节之前的插入点
      const distanceToTop = Math.abs(mouseY - rect.top);
      if (distanceToTop < minDistance) {
        minDistance = distanceToTop;
        closestIndex = idx;
      }

      // 最后一个节之后的插入点
      if (idx === sectionElements.length - 1) {
        const distanceToBottom = Math.abs(mouseY - rect.bottom);
        if (distanceToBottom < minDistance) {
          closestIndex = idx + 1;
        }
      }
    });

    return closestIndex;
  }, []);

  return (
    <div className="w-80 border-r border-gray-300 p-4 bg-gray-50 overflow-y-auto h-full">
      <h3 className="text-lg font-semibold mb-4">课程大纲</h3>

      {/* 课程根节点 */}
      <div className="flex items-center gap-2 mb-2">
        <div
          onClick={() => onSelect('root', 'course')}
          className={`flex-1 p-3 cursor-pointer rounded ${activePath === 'root'
            ? 'bg-blue-500 text-white'
            : 'bg-blue-100 hover:bg-blue-200'
            }`}
        >
          📚 <strong>{title || '未命名课程'}</strong>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAddChapter();
          }}
          className="px-2 py-1 text-xs bg-indigo-500 text-white rounded hover:bg-indigo-600"
          title="添加章"
        >
          +
        </button>
      </div>

      {/* 章节点 */}
      {chapters?.map((chapter: Chapter, cIdx: number) => (
        <div key={chapter.chapter_id || cIdx} className="mb-3">
          <div className="flex items-center gap-2">
            <div
              onClick={() => onSelect(`chapters.${cIdx}`, 'chapter')}
              className={`flex-1 p-2 cursor-pointer rounded mb-1 flex items-center justify-between ${activePath === `chapters.${cIdx}`
                ? 'bg-indigo-500 text-white'
                : 'bg-indigo-100 hover:bg-indigo-200'
                }`}
            >
              <span>📂 <strong>{chapter.title || `第${cIdx + 1}章`}</strong></span>
              {isChapterIncomplete(chapter) && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${activePath === `chapters.${cIdx}` ? 'bg-white/20 border-white/40 text-white' : 'bg-red-100 text-red-600 border-red-200'}`} title="该章存在缺失内容的小节">
                  ⚠️ 需补全
                </span>
              )}
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAddSection(cIdx);
              }}
              className="px-2 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600"
              title="添加节"
            >
              +
            </button>
          </div>

          {/* 节节点 (缩进) */}
          <div
            className="pl-6 mt-1 min-h-[40px]"
            onDragOver={(e) => {
              if (!draggedSection) return;
              e.preventDefault();
              e.stopPropagation();
              e.dataTransfer.dropEffect = 'move';

              const closestIndex = calculateClosestInsertPosition(e.clientY, e.currentTarget);

              // 只在目标位置真正改变时更新状态
              if (dragOverTarget?.chapterIndex !== cIdx || dragOverTarget?.sectionIndex !== closestIndex) {
                setDragOverTarget({ chapterIndex: cIdx, sectionIndex: closestIndex });
              }
            }}
            onDragLeave={(e) => {
              // 检查是否真正离开了容器
              const relatedTarget = e.relatedTarget as HTMLElement;
              if (!relatedTarget || !e.currentTarget.contains(relatedTarget)) {
                setDragOverTarget(null);
              }
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();

              const data = e.dataTransfer.getData('text/plain');
              if (data && draggedSection && dragOverTarget) {
                const [sourceChapterIndex, sourceSectionIndex] = data.split('-').map(Number);
                const targetIndex = dragOverTarget.sectionIndex;

                // 只有当位置真正改变时才移动
                if (sourceChapterIndex !== dragOverTarget.chapterIndex || sourceSectionIndex !== targetIndex) {
                  onMoveSection(sourceChapterIndex, sourceSectionIndex, dragOverTarget.chapterIndex, targetIndex);
                }
              }

              setDraggedSection(null);
              setDragOverTarget(null);
            }}
          >
            {/* 拖拽放置指示器 - 只在空章时显示 */}
            {dragOverTarget?.chapterIndex === cIdx &&
              dragOverTarget.sectionIndex === 0 &&
              (!chapter.sections || chapter.sections.length === 0) && (
                <div className="h-1 bg-blue-500 rounded mb-1" />
              )}

            {chapter.sections?.map((section: Section, sIdx: number) => {
              // 计算全局节序号
              let globalSectionIndex = 0;
              for (let i = 0; i < cIdx; i++) {
                globalSectionIndex += (chapters?.[i]?.sections?.length || 0);
              }
              globalSectionIndex += sIdx;

              const isDragging = draggedSection?.chapterIndex === cIdx && draggedSection?.sectionIndex === sIdx;

              return (
                <React.Fragment key={section.section_id || sIdx}>
                  {/* 拖拽放置指示器 - 在节之前 */}
                  {dragOverTarget?.chapterIndex === cIdx &&
                    dragOverTarget.sectionIndex === sIdx &&
                    !(draggedSection?.chapterIndex === cIdx && draggedSection?.sectionIndex === sIdx) && (
                      <div className="h-1 bg-blue-500 rounded mb-1" />
                    )}
                  <div
                    draggable
                    className={`section-item p-2 cursor-move rounded mb-1 border-l-2 border-gray-300 transition-all ${isDragging
                      ? 'opacity-50 bg-gray-200'
                      : activePath === `chapters.${cIdx}.sections.${sIdx}`
                        ? 'bg-green-500 text-white border-green-600'
                        : 'bg-green-50 hover:bg-green-100'
                      }`}
                    onDragStart={(e) => {
                      setDraggedSection({ chapterIndex: cIdx, sectionIndex: sIdx });
                      e.dataTransfer.effectAllowed = 'move';
                      e.dataTransfer.setData('text/plain', `${cIdx}-${sIdx}`);
                    }}
                    onDragEnd={() => {
                      // 清理所有拖动状态
                      setDraggedSection(null);
                      setDragOverTarget(null);
                    }}
                    onClick={() => onSelect(`chapters.${cIdx}.sections.${sIdx}`, 'section')}
                  >
                    <div className="flex items-center justify-between">
                      <span className="truncate flex-1" title={section.title || `第${globalSectionIndex + 1}节`}>
                        🎥 {section.title || `第${globalSectionIndex + 1}节`}
                      </span>
                      {isSectionIncomplete(section) && (
                        <span className="ml-1 text-[10px]" title="存在缺失内容">⚠️</span>
                      )}
                    </div>
                  </div>
                </React.Fragment>
              );
            })}
            {/* 拖拽放置指示器 - 在章的最后一个节之后（排除空章） */}
            {dragOverTarget?.chapterIndex === cIdx &&
              dragOverTarget.sectionIndex === (chapter.sections?.length || 0) &&
              chapter.sections && chapter.sections.length > 0 && (
                <div className="h-1 bg-blue-500 rounded mb-1" />
              )}
          </div>
        </div>
      ))}
      <div className="text-gray-500 text-xs mt-4">点击节点在右侧编辑属性</div>
    </div>
  );
};

// ---------------------------------------------------------
// 2. 右侧：属性编辑器 (根据节点类型渲染不同表单)
// ---------------------------------------------------------
interface PropertyEditorProps {
  activePath: string | null;
  activeType: 'course' | 'chapter' | 'section' | null;
  onDelete?: (path: string, type: 'chapter' | 'section') => void;
  onAutoComplete?: (path: string) => void;
}

const PropertyEditor: React.FC<PropertyEditorProps> = ({ activePath, activeType, onDelete, onAutoComplete }) => {
  const { register, control, setValue } = useFormContext();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [sectionTab, setSectionTab] = useState<'basic' | 'content' | 'points' | 'subtitles' | 'questions' | 'exercises'>('basic');

  // 获取所有章节用于计算索引
  const chapters = useWatch({ control, name: 'chapters' });

  // 计算当前章或节的索引
  const getChapterIndex = (path: string | null): number | null => {
    if (!path) return null;
    const match = path.match(/chapters\.(\d+)/);
    return match ? parseInt(match[1], 10) : null;
  };

  const getSectionIndex = (path: string | null): { chapterIndex: number; sectionIndex: number } | null => {
    if (!path) return null;
    const match = path.match(/chapters\.(\d+)\.sections\.(\d+)/);
    if (!match) return null;
    return {
      chapterIndex: parseInt(match[1], 10),
      sectionIndex: parseInt(match[2], 10)
    };
  };

  // 获取当前section的order值用于显示
  // 始终调用useWatch，使用条件路径或安全的默认路径（使用chapters作为后备，因为它总是存在）
  const sectionOrderWatchPath = (activePath && activeType === 'section'
    ? `${activePath}.order`
    : 'chapters') as any;
  const sectionOrderValue = useWatch({
    control,
    name: sectionOrderWatchPath,
    defaultValue: null
  });

  // 获取当前章的order值
  const chapterOrderWatchPath = (activePath && activeType === 'chapter'
    ? `${activePath}.order`
    : 'chapters') as any;
  const chapterOrderValue = useWatch({
    control,
    name: chapterOrderWatchPath,
    defaultValue: null
  });

  // 获取当前节点标题用于确认对话框和显示
  const titleWatchPath = (activePath === 'root'
    ? 'title'
    : (activePath ? `${activePath}.title` : 'title')) as any;
  const currentTitle = useWatch({
    control,
    name: titleWatchPath,
    defaultValue: ''
  });

  const categoryValue = useWatch({
    control,
    name: 'category',
    defaultValue: DEFAULT_COURSE_CATEGORY,
  });

  useEffect(() => {
    if (activeType !== 'section') {
      setSectionTab('basic');
    }
  }, [activeType, activePath]);

  // 根据activeType和activePath决定使用哪个order值
  const currentOrder = activeType === 'section' && activePath ? sectionOrderValue : null;
  const currentChapterOrder = activeType === 'chapter' && activePath ? chapterOrderValue : null;

  // 获取默认名称
  const getDefaultTitle = (): string => {
    if (activeType === 'chapter') {
      const chapterIndex = getChapterIndex(activePath);
      return chapterIndex !== null ? `第${chapterIndex + 1}章` : '章';
    } else if (activeType === 'section') {
      const sectionInfo = getSectionIndex(activePath);
      if (sectionInfo) {
        // 计算全局节序号
        let globalSectionIndex = 0;
        for (let i = 0; i < sectionInfo.chapterIndex; i++) {
          globalSectionIndex += (chapters?.[i]?.sections?.length || 0);
        }
        globalSectionIndex += sectionInfo.sectionIndex;
        return `第${globalSectionIndex + 1}节`;
      }
      return '节';
    }
    return '';
  };

  // 显示标题（如果有则显示，否则显示默认名称）
  const displayTitle = currentTitle || getDefaultTitle();

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  const handleConfirmDelete = () => {
    if (activePath && activeType && (activeType === 'chapter' || activeType === 'section') && onDelete) {
      onDelete(activePath, activeType);
      setShowDeleteConfirm(false);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteConfirm(false);
  };

  if (!activePath || !activeType) {
    return (
      <div className="flex-1 p-10 text-gray-500 text-center">
        <p className="text-lg">请点击左侧目录节点进行编辑</p>
      </div>
    );
  }

  return (
    <div key={activePath} className="flex-1 p-8 overflow-y-auto">
      <div className="border-b border-gray-200 pb-3 mb-6 flex items-center justify-between">
        <div>
          <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${activeType === 'course' ? 'bg-blue-500 text-white' :
            activeType === 'chapter' ? 'bg-indigo-500 text-white' :
              'bg-green-500 text-white'
            }`}>
            {activeType === 'course' ? '课程编辑' : activeType === 'chapter' ? '章编辑' : '节编辑'}
          </span>
          <span className="ml-3 text-gray-500 text-sm">路径: {activePath}</span>
        </div>
        <div className="flex gap-2">
          {(activeType === 'section' || activeType === 'chapter') && onAutoComplete && (
            <button
              onClick={() => onAutoComplete(activePath!)}
              className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors shadow-sm"
              title={`自动补全此${activeType === 'chapter' ? '章的所有节' : '节'}的缺失数据`}
            >
              ✨ 自动补全
            </button>
          )}
          {(activeType === 'chapter' || activeType === 'section') && (
            <button
              onClick={handleDeleteClick}
              className="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors shadow-sm"
            >
              删除
            </button>
          )}
        </div>
      </div>

      {/* 删除确认对话框 */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl border border-gray-200">
            <h3 className="text-lg font-semibold mb-4">确认删除</h3>
            <p className="text-gray-700 mb-6">
              确定要删除{activeType === 'chapter' ? '章' : '节'} <strong>"{displayTitle}"</strong> 吗？
              {activeType === 'chapter' && '删除章将同时删除该章下的所有节。'}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleCancelDelete}
                className="px-4 py-2 text-gray-700 bg-gray-200 rounded hover:bg-gray-300 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleConfirmDelete}
                className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============== 课程 (Course) 编辑器 ============== */}
      {activeType === 'course' && (
        <div className="space-y-4">
          {/* ID字段隐藏，但保留在表单中 */}
          <input type="hidden" {...register('course_id')} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">课程标题</label>
            <input
              {...register('title')}
              placeholder="输入课程标题..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">课程描述</label>
            <textarea
              {...register('description')}
              rows={4}
              placeholder="输入课程描述..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              AI 人设配置
              <span className="text-xs text-gray-500 font-normal ml-2">将按 ai_persona 对象格式保存并同步课程库</span>
            </label>
            {/* 隐藏字段：保留结构完整性，但不在前端展示 */}
            <input type="hidden" {...register('ai_persona.persona_id')} />
            <input type="hidden" {...register('ai_persona.is_default_template')} value="true" />
            <div>
              <label className="block text-xs text-gray-600 mb-1">name</label>
              <input
                {...register('ai_persona.name')}
                placeholder="例如：严谨导师"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="mt-3">
              <label className="block text-xs text-gray-600 mb-1">prompt</label>
              <textarea
                {...register('ai_persona.prompt')}
                rows={4}
                placeholder="例如：你是一名严谨、耐心的学习导师，回答应结构化并给出下一步建议。"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">persona_id 自动保留，is_default_template 默认按 true 保存。</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">课程分类</label>
            <select
              value={normalizeCourseCategory(categoryValue)}
              onChange={(e) =>
                setValue('category', e.target.value as CourseCategory, {
                  shouldDirty: true,
                })
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {COURSE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* 课程图标上传 */}
          <CourseIconUploader />
        </div>
      )}

      {/* ============== 章 (Chapter) 编辑器 ============== */}
      {activeType === 'chapter' && (
        <div className="space-y-4">
          {/* ID字段隐藏，但保留在表单中 */}
          <input type="hidden" {...register(`${activePath}.chapter_id`)} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              章标题 {!currentTitle && <span className="text-gray-400 text-xs">(默认: {getDefaultTitle()})</span>}
            </label>
            <input
              {...register(`${activePath}.title`)}
              placeholder={getDefaultTitle()}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {!currentTitle && (
              <p className="text-xs text-gray-500 mt-1">当前显示名称: {getDefaultTitle()}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">排序（自动计算）</label>
            <input
              type="number"
              {...register(`${activePath}.order`, { valueAsNumber: true })}
              value={currentChapterOrder ?? 0}
              readOnly
              disabled
              className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100 text-gray-600 cursor-not-allowed"
            />
            <p className="text-xs text-gray-500 mt-1">排序序号由系统自动计算，按章节顺序单调递增（从0开始）</p>
          </div>
        </div>
      )}

      {/* ============== 节 (Section) 编辑器 ============== */}
      {activeType === 'section' && (
        <div className="space-y-4">
          {/* ID字段隐藏，但保留在表单中 */}
          <input type="hidden" {...register(`${activePath}.section_id`)} />
          <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-2">
            {[
              ['basic', '基础信息'],
              ['content', '知识正文'],
              ['points', '知识要点'],
              ['subtitles', '视频字幕'],
              ['questions', '引导问题'],
              ['exercises', '练习题'],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setSectionTab(key as typeof sectionTab)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${sectionTab === key
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
              >
                {label}
              </button>
            ))}
          </div>

          {sectionTab === 'basic' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  节标题 {!currentTitle && <span className="text-gray-400 text-xs">(默认: {getDefaultTitle()})</span>}
                </label>
                <input
                  {...register(`${activePath}.title`)}
                  placeholder={getDefaultTitle()}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                />
                {!currentTitle && (
                  <p className="text-xs text-gray-500 mt-1">当前显示名称: {getDefaultTitle()}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">排序（自动计算）</label>
                <input
                  type="number"
                  {...register(`${activePath}.order`, { valueAsNumber: true })}
                  value={currentOrder ?? 0}
                  readOnly
                  disabled
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100 text-gray-600 cursor-not-allowed"
                />
                <p className="text-xs text-gray-500 mt-1">排序序号由系统自动计算，按课程中所有节的顺序单调递增（从0开始）</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">预计时长（分钟）</label>
                <input
                  type="number"
                  {...register(`${activePath}.estimated_time`, { valueAsNumber: true })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">视频URL</label>
                <input
                  {...register(`${activePath}.video_url`)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
            </div>
          )}

          {sectionTab === 'content' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                知识全文（Markdown）
              </label>
              <textarea
                {...register(`${activePath}.knowledge_content`)}
                rows={28}
                placeholder="支持 Markdown，可与生成管线产出的全文总结一致..."
                className="w-full min-h-[min(70vh,36rem)] px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-sm resize-y"
              />
              <p className="text-xs text-gray-500 mt-1">
                保存课程到工作区时，将随节数据一并写入 course.json。
              </p>
            </div>
          )}

          {sectionTab === 'points' && (
            <KnowledgePointsManager key={`points-${activePath}`} activePath={activePath} />
          )}

          {sectionTab === 'subtitles' && (
            <VideoSubtitlesManager key={`subtitles-${activePath}`} activePath={activePath} />
          )}

          {sectionTab === 'questions' && (
            <LeadingQuestionsManager key={`questions-${activePath}`} activePath={activePath} />
          )}

          {sectionTab === 'exercises' && (
            <ExercisesManager key={`exercises-${activePath}`} activePath={activePath} />
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------
// 子组件：课程图标上传器
// ---------------------------------------------------------
const CourseIconUploader: React.FC = () => {
  const { register, control, setValue } = useFormContext();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 监听icon_url的变化以实时预览
  const iconUrl = useWatch({
    control,
    name: 'icon_url',
    defaultValue: ''
  });

  // 处理文件选择
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 验证文件类型
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件！');
      return;
    }

    // 验证文件大小（限制为2MB）
    const maxSize = 2 * 1024 * 1024; // 2MB
    if (file.size > maxSize) {
      alert('图片大小不能超过2MB！');
      return;
    }

    // 读取文件并转换为base64
    const reader = new FileReader();
    reader.onload = (event) => {
      const base64String = event.target?.result as string;
      setValue('icon_url', base64String, { shouldDirty: true });
    };
    reader.onerror = () => {
      alert('读取图片失败，请重试！');
    };
    reader.readAsDataURL(file);
  };

  // 触发文件选择
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  // 清除图标
  const handleClearIcon = () => {
    setValue('icon_url', '', { shouldDirty: true });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">课程图标</label>
      <div className="flex items-start gap-4">
        {/* 预览区域 */}
        <div className="flex-shrink-0">
          {iconUrl ? (
            <div className="relative w-32 h-32 border-2 border-gray-300 rounded-lg overflow-hidden bg-gray-50">
              <img
                src={iconUrl}
                alt="课程图标预览"
                className="w-full h-full object-cover"
              />
              <button
                type="button"
                onClick={handleClearIcon}
                className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center hover:bg-red-600 transition-colors"
                title="清除图标"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="w-32 h-32 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center bg-gray-50">
              <span className="text-gray-400 text-sm text-center px-2">暂无图标</span>
            </div>
          )}
        </div>

        {/* 操作按钮和说明 */}
        <div className="flex-1">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*"
            className="hidden"
          />
          <button
            type="button"
            onClick={handleUploadClick}
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors mb-2"
          >
            {iconUrl ? '更换图标' : '上传图标'}
          </button>
          <div className="text-xs text-gray-500 space-y-1">
            <p>• 支持 JPG、PNG、GIF 等图片格式</p>
            <p>• 图片大小不超过 2MB</p>
            <p>• 推荐尺寸：正方形，至少 256x256 像素</p>
            <p>• 图片将以 Base64 格式保存在课程数据中</p>
          </div>
        </div>
      </div>
      {/* 隐藏字段保存base64值 */}
      <input type="hidden" {...register('icon_url')} />
    </div>
  );
};

// ---------------------------------------------------------
// 子组件：知识要点管理器
// ---------------------------------------------------------
interface KnowledgePointsManagerProps {
  activePath: string;
}

const KnowledgePointsManager: React.FC<KnowledgePointsManagerProps> = ({ activePath }) => {
  const { control, register } = useFormContext();
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: `${activePath}.knowledge_points.key_points`,
  });

  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <div className="flex flex-wrap justify-between items-center gap-2 mb-3">
        <div>
          <h3 className="text-lg font-semibold">知识要点</h3>
          <p className="text-xs text-gray-500">保存为 knowledge_points.key_points，上传课程库时直接进入小节数据。</p>
        </div>
        <button
          type="button"
          onClick={() => append({ time: '', title: '', description: '' })}
          className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
        >
          + 添加要点
        </button>
      </div>

      {fields.length === 0 ? (
        <p className="text-gray-400 text-sm">暂无知识要点，点击上方按钮添加</p>
      ) : (
        <div className="space-y-3">
          {fields.map((field, index) => (
            <div key={field.id} className="bg-white p-3 rounded border border-gray-200">
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold text-sm">要点 {index + 1}</span>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => index > 0 && move(index, index - 1)}
                    disabled={index === 0}
                    className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-40"
                  >
                    上移
                  </button>
                  <button
                    type="button"
                    onClick={() => index < fields.length - 1 && move(index, index + 1)}
                    disabled={index === fields.length - 1}
                    className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-40"
                  >
                    下移
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(index)}
                    className="px-2 py-1 text-xs rounded text-red-600 hover:bg-red-50"
                  >
                    删除
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">时间</label>
                  <input
                    {...register(`${activePath}.knowledge_points.key_points.${index}.time`)}
                    placeholder="00:03"
                    className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-xs text-gray-600 mb-1">标题</label>
                  <input
                    {...register(`${activePath}.knowledge_points.key_points.${index}.title`)}
                    placeholder="要点标题"
                    className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">描述</label>
                <textarea
                  {...register(`${activePath}.knowledge_points.key_points.${index}.description`)}
                  rows={3}
                  placeholder="说明这个知识点的核心内容"
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm resize-y"
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

function parseSrtToSubtitles(text: string): VideoSubtitle[] {
  const normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
  if (!normalized) return [];

  const blocks = normalized.split(/\n\s*\n/);
  const subtitles: VideoSubtitle[] = [];
  for (const block of blocks) {
    const lines = block.split('\n').map((line) => line.trimEnd()).filter(Boolean);
    if (lines.length < 2) continue;

    let timeLineIndex = 0;
    if (/^\d+$/.test(lines[0].trim())) {
      timeLineIndex = 1;
    }

    const timeLine = lines[timeLineIndex];
    const match = timeLine?.match(/^(.+?)\s*-->\s*(.+?)(?:\s+.*)?$/);
    if (!match) continue;

    const textLines = lines.slice(timeLineIndex + 1);
    if (textLines.length === 0) continue;

    subtitles.push({
      seq: subtitles.length + 1,
      start: match[1].trim(),
      end: match[2].trim(),
      text: textLines.join('\n'),
    });
  }
  return subtitles;
}

// ---------------------------------------------------------
// 子组件：视频字幕管理器
// ---------------------------------------------------------
interface VideoSubtitlesManagerProps {
  activePath: string;
}

const SUBTITLE_PAGE_SIZE = 50;

const VideoSubtitlesManager: React.FC<VideoSubtitlesManagerProps> = ({ activePath }) => {
  const { control, register, setValue, getValues } = useFormContext();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [searchText, setSearchText] = useState('');
  const [page, setPage] = useState(1);
  const { fields, append, remove } = useFieldArray({
    control,
    name: `${activePath}.video_subtitles`,
  });

  const subtitles = (useWatch({
    control,
    name: `${activePath}.video_subtitles`,
    defaultValue: [],
  }) ?? []) as VideoSubtitle[];

  const filteredIndexes = subtitles
    .map((subtitle, index) => ({ subtitle, index }))
    .filter(({ subtitle }) => {
      const q = searchText.trim().toLowerCase();
      if (!q) return true;
      return (
        String(subtitle.seq ?? '').includes(q) ||
        (subtitle.start || '').toLowerCase().includes(q) ||
        (subtitle.end || '').toLowerCase().includes(q) ||
        (subtitle.text || '').toLowerCase().includes(q)
      );
    })
    .map(({ index }) => index);

  const pageCount = Math.max(1, Math.ceil(filteredIndexes.length / SUBTITLE_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visibleIndexes = filteredIndexes.slice(
    (currentPage - 1) * SUBTITLE_PAGE_SIZE,
    currentPage * SUBTITLE_PAGE_SIZE
  );

  useEffect(() => {
    setPage(1);
  }, [searchText, activePath]);

  const renumberSubtitles = () => {
    const current = ((getValues(`${activePath}.video_subtitles`) ?? []) as VideoSubtitle[]).map((subtitle, index) => ({
      ...subtitle,
      seq: index + 1,
    }));
    setValue(`${activePath}.video_subtitles`, current, { shouldDirty: true });
  };

  const handleRemove = (index: number) => {
    remove(index);
    setTimeout(renumberSubtitles, 0);
  };

  const handleAppend = () => {
    append({ seq: fields.length + 1, start: '', end: '', text: '' });
    setPage(pageCount);
  };

  const handleImportSrt = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const parsed = parseSrtToSubtitles(String(reader.result ?? ''));
      setValue(`${activePath}.video_subtitles`, parsed, {
        shouldDirty: true,
        shouldValidate: true,
      });
      setSearchText('');
      setPage(1);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    };
    reader.readAsText(file, 'utf-8');
  };

  const handleClear = () => {
    if (window.confirm('确认清空当前小节的全部字幕记录吗？')) {
      setValue(`${activePath}.video_subtitles`, [], { shouldDirty: true });
      setSearchText('');
      setPage(1);
    }
  };

  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3 mb-3">
        <div>
          <h3 className="text-lg font-semibold">视频字幕</h3>
          <p className="text-xs text-gray-500">
            共 {subtitles.length} 条，当前筛选 {filteredIndexes.length} 条；保存为 video_subtitles。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="搜索字幕内容、时间或序号"
            className="w-64 px-3 py-1.5 border border-gray-300 rounded text-sm"
          />
          <button
            type="button"
            onClick={handleAppend}
            className="px-3 py-1.5 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
          >
            + 添加字幕
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="px-3 py-1.5 bg-slate-700 text-white rounded hover:bg-slate-800 text-sm"
          >
            导入 SRT
          </button>
          <button
            type="button"
            onClick={handleClear}
            disabled={subtitles.length === 0}
            className="px-3 py-1.5 bg-red-500 text-white rounded hover:bg-red-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-sm"
          >
            清空
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".srt,text/plain"
            onChange={handleImportSrt}
            className="hidden"
          />
        </div>
      </div>

      {subtitles.length === 0 ? (
        <p className="text-gray-400 text-sm">暂无字幕记录，可手动添加或导入 SRT 文件</p>
      ) : visibleIndexes.length === 0 ? (
        <p className="text-gray-400 text-sm">没有匹配的字幕记录</p>
      ) : (
        <div className="space-y-2">
          {visibleIndexes.map((index) => (
            <div key={fields[index]?.id || index} className="bg-white p-3 rounded border border-gray-200">
              <div className="grid grid-cols-1 md:grid-cols-[80px_1fr_1fr_auto] gap-2 items-end mb-2">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">序号</label>
                  <input
                    type="number"
                    {...register(`${activePath}.video_subtitles.${index}.seq`, { valueAsNumber: true })}
                    className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">开始</label>
                  <input
                    {...register(`${activePath}.video_subtitles.${index}.start`)}
                    placeholder="00:00:01,000"
                    className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">结束</label>
                  <input
                    {...register(`${activePath}.video_subtitles.${index}.end`)}
                    placeholder="00:00:05,000"
                    className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => handleRemove(index)}
                  className="px-2 py-1.5 text-red-600 hover:bg-red-50 rounded text-sm"
                >
                  删除
                </button>
              </div>
              <textarea
                {...register(`${activePath}.video_subtitles.${index}.text`)}
                rows={2}
                placeholder="字幕文本"
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm resize-y"
              />
            </div>
          ))}
        </div>
      )}

      {filteredIndexes.length > SUBTITLE_PAGE_SIZE && (
        <div className="flex justify-between items-center mt-4 text-sm">
          <button
            type="button"
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            disabled={currentPage <= 1}
            className="px-3 py-1.5 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-40"
          >
            上一页
          </button>
          <span className="text-gray-600">
            第 {currentPage} / {pageCount} 页
          </span>
          <button
            type="button"
            onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
            disabled={currentPage >= pageCount}
            className="px-3 py-1.5 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
};

function getSectionKnowledgePointCount(section: Section): number {
  const points = section.knowledge_points?.key_points;
  return Array.isArray(points) ? points.length : 0;
}

function getSectionSubtitleCount(section: Section): number {
  return Array.isArray(section.video_subtitles) ? section.video_subtitles.length : 0;
}

// ---------------------------------------------------------
// 3. 子组件：引导问题管理器
// ---------------------------------------------------------
interface LeadingQuestionsManagerProps {
  activePath: string;
}

const LeadingQuestionsManager: React.FC<LeadingQuestionsManagerProps> = ({ activePath }) => {
  const { control, register } = useFormContext();
  const { fields, append, remove } = useFieldArray({
    control,
    name: `${activePath}.leading_questions`
  });

  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-lg font-semibold">引导问题</h3>
        <button
          type="button"
          onClick={() => append({ question_id: uuidv4(), question: "" })}
          className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
        >
          + 添加问题
        </button>
      </div>
      {fields.map((field, index) => (
        <div key={field.id} className="flex gap-2 mb-2 items-start">
          <span className="font-semibold mt-2">Q{index + 1}:</span>
          <div className="flex-1">
            {/* ID字段隐藏，但保留在表单中 */}
            <input type="hidden" {...register(`${activePath}.leading_questions.${index}.question_id`)} />
            <input
              {...register(`${activePath}.leading_questions.${index}.question`)}
              placeholder="问题描述"
              className="w-full px-2 py-1 border border-gray-300 rounded"
            />
          </div>
          <button
            type="button"
            onClick={() => remove(index)}
            className="px-2 py-1 text-red-500 hover:bg-red-50 rounded text-sm"
          >
            删除
          </button>
        </div>
      ))}
      {fields.length === 0 && (
        <p className="text-gray-400 text-sm">暂无引导问题，点击上方按钮添加</p>
      )}
    </div>
  );
};

// ---------------------------------------------------------
// 4. 子组件：练习题管理器
// ---------------------------------------------------------
interface ExercisesManagerProps {
  activePath: string;
}

const ExercisesManager: React.FC<ExercisesManagerProps> = ({ activePath }) => {
  const { control } = useFormContext();
  const { fields, append, remove } = useFieldArray({
    control,
    name: `${activePath}.exercises`
  });

  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-lg font-semibold">练习题</h3>
        <button
          type="button"
          onClick={() => append({
            exercise_id: uuidv4(),
            question: "",
            score: 0,
            type: "单选",
            answer: "",
            options: []
          })}
          className="px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600 text-sm"
        >
          + 添加练习题
        </button>
      </div>
      {fields.map((field, index) => (
        <ExerciseItem
          key={field.id}
          activePath={activePath}
          index={index}
          onRemove={() => remove(index)}
        />
      ))}
      {fields.length === 0 && (
        <p className="text-gray-400 text-sm">暂无练习题，点击上方按钮添加</p>
      )}
    </div>
  );
};

interface ExerciseItemProps {
  activePath: string;
  index: number;
  onRemove: () => void;
}

const ExerciseItem: React.FC<ExerciseItemProps> = ({ activePath, index, onRemove }) => {
  const { register, control } = useFormContext();
  const exerciseType = useWatch({
    control,
    name: `${activePath}.exercises.${index}.type` as const,
  });
  const { fields, append, remove } = useFieldArray({
    control,
    name: `${activePath}.exercises.${index}.options`
  });

  return (
    <div className="bg-white p-3 rounded border border-gray-200 mb-3">
      <div className="flex justify-between items-center mb-2">
        <span className="font-semibold">题目 {index + 1}</span>
        <button
          type="button"
          onClick={onRemove}
          className="px-2 py-1 text-red-500 hover:bg-red-50 rounded text-sm"
        >
          删除题目
        </button>
      </div>
      <div className="space-y-2">
        {/* ID字段隐藏，但保留在表单中 */}
        <input type="hidden" {...register(`${activePath}.exercises.${index}.exercise_id`)} />
        <input
          {...register(`${activePath}.exercises.${index}.question`)}
          placeholder="问题描述"
          className="w-full px-2 py-1 border border-gray-300 rounded"
        />
        <div className="flex gap-2">
          <div className="flex items-center gap-1">
            <label className="text-sm text-gray-700">分值:</label>
            <input
              type="number"
              {...register(`${activePath}.exercises.${index}.score`, { valueAsNumber: true })}
              className="w-20 px-2 py-1 border border-gray-300 rounded"
            />
          </div>
          <select
            {...register(`${activePath}.exercises.${index}.type`)}
            className="flex-1 px-2 py-1 border border-gray-300 rounded"
          >
            <option value="单选">单选</option>
            <option value="多选">多选</option>
            <option value="简答">简答</option>
          </select>
        </div>

        {exerciseType === '简答' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">参考答案</label>
            <textarea
              {...register(`${activePath}.exercises.${index}.answer`)}
              rows={2}
              placeholder="简答题的参考答案描述"
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30"
            />
            <p className="text-xs text-gray-500 mt-1">保存在题目的 answer 字段，供学习助手判分使用</p>
          </div>
        )}

        {/* 选项列表 */}
        <div className="mt-3 pl-4 border-l-2 border-gray-300">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium">选项</span>
            <button
              type="button"
              onClick={() => append({ option_id: uuidv4(), text: "", is_correct: false })}
              className="px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-xs"
            >
              + 添加选项
            </button>
          </div>
          {fields.map((optionField, optIdx) => (
            <div key={optionField.id} className="flex gap-2 mb-2 items-center">
              <input
                type="checkbox"
                {...register(`${activePath}.exercises.${index}.options.${optIdx}.is_correct`)}
                className="w-4 h-4"
              />
              {/* ID字段隐藏，但保留在表单中 */}
              <input type="hidden" {...register(`${activePath}.exercises.${index}.options.${optIdx}.option_id`)} />
              <input
                {...register(`${activePath}.exercises.${index}.options.${optIdx}.text`)}
                placeholder="选项文本"
                className="flex-1 px-2 py-1 border border-gray-300 rounded"
              />
              <button
                type="button"
                onClick={() => remove(optIdx)}
                className="px-2 py-1 text-red-500 hover:bg-red-50 rounded text-xs"
              >
                删除
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------
// 5. Section 展示面板
// ---------------------------------------------------------
interface SectionPanelProps {
  sections: Section[];
  onInsertSection: (sectionData: Section) => void;
}

const SectionPanel: React.FC<SectionPanelProps> = ({ sections, onInsertSection }) => {
  return (
    <div className="w-80 border-l border-gray-300 p-4 bg-gray-50 overflow-y-auto h-full">
      <h3 className="text-lg font-semibold mb-4">可用节 (Sections)</h3>
      <div className="space-y-2">
        {sections.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无可用的节</p>
        ) : (
          sections.map((section, idx) => (
            <div key={section.section_id || idx} className="bg-white p-3 rounded border border-gray-200">
              <div className="flex justify-between items-start gap-2">
                <div className="flex-1">
                  <div className="font-medium text-sm mb-1">
                    {section.title || `节 ${idx + 1}`}
                  </div>
                  <div className="text-xs text-gray-500">
                    section_id: {section.section_id}
                  </div>
                  {section.estimated_time && (
                    <div className="text-xs text-gray-500">
                      时长: {section.estimated_time}分钟
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-1">
                    知识点: {getSectionKnowledgePointCount(sanitizeSection(section))} · 字幕: {getSectionSubtitleCount(sanitizeSection(section))}
                  </div>
                  <div className="text-xs text-gray-500">
                    题目: {section.exercises?.length ?? 0} · 引导问题: {section.leading_questions?.length ?? 0}
                  </div>
                </div>
                <button
                  onClick={() => onInsertSection(section)}
                  className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 whitespace-nowrap"
                >
                  插入
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------
// 6. 主入口组件
// ---------------------------------------------------------
interface CourseEditorProps {
  initialData?: CourseData;
  onSave?: (data: CourseData) => void;
  workspaces?: Array<{ name: string; path: string; created_at?: string }>;
  models?: Model[];
  appConfig?: AppConfig;
  onConfigChange?: (updates: Partial<AppConfig>) => void;
  onTaskSubmit?: (request: CreateTaskRequest) => Promise<void>;
  tasks?: Task[];
}

const CourseEditor: React.FC<CourseEditorProps> = ({ 
  initialData, 
  onSave: _onSave, 
  workspaces = [],
  models = [],
  appConfig,
  onConfigChange,
  onTaskSubmit,
  tasks = []
}) => {
  const defaultValues: CourseData = initialData
    ? sanitizeCourseData(initialData)
    : {
      course_id: uuidv4(),
      title: "",
      description: "",
      ai_persona: createDefaultAiPersona(""),
      category: DEFAULT_COURSE_CATEGORY,
      contributors: "志愿者",
      icon_url: "",
      chapters: []
    };

  const methods = useForm<CourseData>({
    defaultValues,
    shouldUnregister: false,
  });

  // 当initialData变化时，更新表单数据
  useEffect(() => {
    if (initialData) {
      methods.reset(sanitizeCourseData(initialData));
    }
  }, [initialData, methods]);


  const [activeNode, setActiveNode] = useState<{ path: string | null; type: 'course' | 'chapter' | 'section' | null }>({
    path: null,
    type: null
  });

  // 新增状态
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [availableSections, setAvailableSections] = useState<Section[]>([]);
  const [openMode, setOpenMode] = useState<'workspace' | 'file' | null>(null); // 打开模式

  const [autoCompleteConfig, setAutoCompleteConfig] = useState<{
    isOpen: boolean;
    type: 'section' | 'chapter' | 'course';
    targetPath?: string;
  }>({ isOpen: false, type: 'course' });

  // 统一对话框状态
  const [isCourseLibraryOpen, setIsCourseLibraryOpen] = useState(false);

  const [dialog, setDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    type: 'info' | 'success' | 'warning' | 'error' | 'confirm';
    onConfirm?: () => void;
    confirmText?: string;
    cancelText?: string;
  }>({
    isOpen: false,
    title: '',
    message: '',
    type: 'info'
  });

  // ---------- 自动同步已完成的补全任务数据 ----------
  const prevTasksRef_sync = useRef<Task[]>([]);

  useEffect(() => {
    if (!tasks || tasks.length === 0 || openMode !== 'workspace' || !selectedWorkspace) {
      prevTasksRef_sync.current = tasks || [];
      return;
    }

    const newlyCompletedTasks = tasks.filter(task => {
      const prevTask = prevTasksRef_sync.current.find(t => t.id === task.id);
      return task.status === 'completed' && (!prevTask || prevTask.status !== 'completed');
    });

    prevTasksRef_sync.current = tasks;

    if (newlyCompletedTasks.length > 0) {
      fetch(`/api/course/${selectedWorkspace}`)
        .then(res => res.json())
        .then(data => {
          if (data.success && data.sections) {
            setAvailableSections(data.sections);

            const completedUrls = newlyCompletedTasks.map(t => t.url);
            const currentChapters = methods.getValues('chapters') || [];
            let chaptersChanged = false;

            const updatedChapters = currentChapters.map((chapter: Chapter) => {
              if (!chapter.sections) return chapter;
              const updatedSections = chapter.sections.map((sec: Section) => {
                if (sec.video_url && completedUrls.includes(sec.video_url)) {
                  const diskSection = data.sections.find((s: Section) => s.video_url === sec.video_url);
                  if (diskSection) {
                    let changed = false;
                    const newSec = { ...sec };

                    if (!newSec.video_subtitles?.length && diskSection.video_subtitles?.length) {
                      newSec.video_subtitles = diskSection.video_subtitles;
                      changed = true;
                    }
                    if (!newSec.knowledge_points?.key_points?.length && diskSection.knowledge_points?.key_points?.length) {
                      newSec.knowledge_points = diskSection.knowledge_points;
                      changed = true;
                    }
                    if (!newSec.knowledge_content && diskSection.knowledge_content) {
                      newSec.knowledge_content = diskSection.knowledge_content;
                      changed = true;
                    }
                    if (!newSec.exercises?.length && diskSection.exercises?.length) {
                      newSec.exercises = diskSection.exercises;
                      changed = true;
                    }
                    if (!newSec.leading_questions?.length && diskSection.leading_questions?.length) {
                      newSec.leading_questions = diskSection.leading_questions;
                      changed = true;
                    }

                    if (changed) {
                      chaptersChanged = true;
                      return newSec;
                    }
                  }
                }
                return sec;
              });
              return { ...chapter, sections: updatedSections };
            });

            if (chaptersChanged) {
              methods.setValue('chapters', updatedChapters, { shouldDirty: true });
              // 自动保存到工作区
              setTimeout(() => {
                saveCourseToWorkspace(true);
              }, 500);
            }
          }
        })
        .catch(err => console.error('Failed to sync completed tasks to course editor:', err));
    }
  }, [tasks, openMode, selectedWorkspace, methods]);
  // ------------------------------------------------


  // 显示对话框的辅助函数
  const showDialog = (
    title: string,
    message: string,
    type: 'info' | 'success' | 'warning' | 'error' | 'confirm' = 'info',
    onConfirm?: () => void,
    confirmText?: string,
    cancelText?: string
  ) => {
    setDialog({
      isOpen: true,
      title,
      message,
      type,
      onConfirm,
      confirmText,
      cancelText
    });
  };

  const closeDialog = () => {
    setDialog({ ...dialog, isOpen: false });
  };

  const { control } = methods;

  /** 与另存为/课程库管理共用：保证 category 写入快照（含 normalize 默认值） */
  const getSanitizedCoursePayload = (): CourseData => {
    const raw = methods.getValues();
    return sanitizeCourseData({
      ...raw,
      category: raw.category ?? methods.getValues('category'),
    });
  };

  // 从工作区加载课程和sections
  const loadCourseFromWorkspace = async (workspaceName: string) => {
    try {
      const response = await fetch(`/api/course/${workspaceName}`);
      const data = await response.json();

      if (data.success) {
        methods.reset(sanitizeCourseData(data.course));
        setAvailableSections(data.sections);
        setOpenMode('workspace');
      } else {
        showDialog('加载失败', data.error || '未知错误', 'error');
      }
    } catch (error) {
      showDialog('加载失败', error instanceof Error ? error.message : '未知错误', 'error');
    }
  };

  // 保存课程到工作区
  const saveCourseToWorkspace = async (silent = false) => {
    if (!selectedWorkspace) {
      showDialog('提示', '请选择工作区', 'warning');
      return;
    }

    const courseData = getSanitizedCoursePayload();
    try {
      const response = await fetch(`/api/course/${selectedWorkspace}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course: courseData }),
      });

      const data = await response.json();
      if (data.success) {
        if (!silent) showDialog('保存成功', '课程已成功保存到工作区', 'success');
      } else {
        showDialog('保存失败', data.error || '未知错误', 'error');
      }
    } catch (error) {
      showDialog('保存失败', error instanceof Error ? error.message : '未知错误', 'error');
    }
  };

  // 另存为JSON文件
  const exportCourseJSON = () => {
    const courseData = getSanitizedCoursePayload();
    const jsonStr = JSON.stringify(courseData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `course-${courseData.course_id || Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 打开JSON文件
  const openJSONFile = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const jsonStr = event.target?.result as string;
          const data = JSON.parse(jsonStr) as CourseData;
          methods.reset(sanitizeCourseData(data));
          // 自动关联匹配的工作区
          const matchedWorkspace = workspaces.find(ws => ws.name === data.title);
          if (matchedWorkspace) {
            setSelectedWorkspace(matchedWorkspace.name);
            setOpenMode('workspace');
            // 加载 available sections
            fetch(`/api/course/${matchedWorkspace.name}`).then(res => res.json()).then(wsData => {
                if (wsData.success) {
                    setAvailableSections(wsData.sections);
                }
            });
            showDialog('加载成功', `JSON文件已加载，并自动关联到同名工作区: ${matchedWorkspace.name}，可直接使用补全功能。`, 'success');
          } else {
            setAvailableSections([]); // 清空可用sections
            setSelectedWorkspace(''); // 清空工作区选择
            setOpenMode('file');
            showDialog('加载成功', 'JSON文件已加载（未找到同名工作区）。在执行自动补全时将自动保存到目标工作区。', 'success');
          }
        } catch (error) {
          showDialog('格式错误', error instanceof Error ? error.message : 'JSON文件格式错误', 'error');
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const handleAutoCompleteConfirm = async (config: { workspaceName: string; modelName: string; maxConcurrent: number }) => {
    if (!onTaskSubmit || !onConfigChange) {
       showDialog('错误', '任务提交流程未就绪', 'error');
       return;
    }
    
    // update global config
    onConfigChange({
      max_concurrent_tasks: config.maxConcurrent,
      last_workspace_name: config.workspaceName,
      last_selected_model: config.modelName
    });

    if (openMode !== 'workspace') {
      const courseData = getSanitizedCoursePayload();
      try {
        await fetch(`/api/course/${config.workspaceName}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ course: courseData }),
        });
        setSelectedWorkspace(config.workspaceName);
        setOpenMode('workspace');
      } catch (err) {
        showDialog('保存失败', '自动保存到工作区失败，无法继续补全。', 'error');
        return;
      }
    }

    const sectionsToProcess: Section[] = [];
    if (autoCompleteConfig.type === 'section') {
      const section = methods.getValues(autoCompleteConfig.targetPath as any) as Section;
      if (section) sectionsToProcess.push(section);
    } else if (autoCompleteConfig.type === 'chapter') {
      const chapter = methods.getValues(autoCompleteConfig.targetPath as any) as Chapter;
      if (chapter && chapter.sections) {
        sectionsToProcess.push(...chapter.sections);
      }
    } else {
      const chapters = methods.getValues('chapters') || [];
      chapters.forEach((c: Chapter) => {
        if (c.sections) {
          sectionsToProcess.push(...c.sections);
        }
      });
    }

    if (sectionsToProcess.length === 0) {
      showDialog('提示', '未找到可补全的节。', 'info');
      setAutoCompleteConfig({ ...autoCompleteConfig, isOpen: false });
      return;
    }

    const groups = new Map<string, string[]>(); // JSON.stringify(options) -> urls
    let totalUrls = 0;

    sectionsToProcess.forEach(sec => {
      if (!sec.video_url) return;
      const opts: GenerateOptions = {
        summary: !sec.knowledge_points?.key_points?.length,
        full_content: !sec.knowledge_content,
        exercises: !sec.exercises?.length,
        questions: !sec.leading_questions?.length,
      };
      
      const missingSubtitles = !sec.video_subtitles?.length;
      
      if (!opts.summary && !opts.full_content && !opts.exercises && !opts.questions && !missingSubtitles) return;
      
      const key = JSON.stringify(opts);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(sec.video_url);
      totalUrls++;
    });

    if (totalUrls === 0) {
      showDialog('提示', '所选内容无需补全，或未配置视频链接(video_url)。', 'info');
      setAutoCompleteConfig({ ...autoCompleteConfig, isOpen: false });
      return;
    }

    setAutoCompleteConfig({ ...autoCompleteConfig, isOpen: false });
    
    try {
      for (const [key, urls] of groups.entries()) {
        const opts = JSON.parse(key) as GenerateOptions;
        await onTaskSubmit({
          urls,
          workspace_name: config.workspaceName,
          model_name: config.modelName,
          download_all_parts: false,
          generate_options: opts
        });
      }
      showDialog('补全任务已提交', `已为您生成 ${groups.size} 批相关任务（共 ${totalUrls} 个视频）。请前往"视频下载"标签页查看进度。完成后您可以在对应工作区重新加载以查看最新数据。`, 'success');
    } catch (e) {
      showDialog('提交失败', e instanceof Error ? e.message : '未知错误', 'error');
    }
  };

  // 插入section到最后一章
  const handleInsertSection = (sectionData: Section) => {
    const chapters = methods.getValues('chapters') || [];

    if (chapters.length === 0) {
      showDialog('提示', '请先创建章！', 'warning');
      return;
    }

    const normalizedSection = sanitizeSection(sectionData);

    // 检查 section_id 是否重复
    const allSectionIds = chapters.flatMap((chapter: Chapter) =>
      (chapter.sections || []).map((section: Section) => section.section_id)
    );

    if (allSectionIds.includes(normalizedSection.section_id)) {
      showDialog(
        'ID冲突',
        `节 section_id "${normalizedSection.section_id}" 已存在，不允许插入重复 ID 的节！`,
        'error'
      );
      return;
    }

    // 获取最后一章
    const lastChapterIndex = chapters.length - 1;
    const lastChapter = chapters[lastChapterIndex];
    const sections = lastChapter.sections || [];

    // 添加section到最后一章
    const updatedChapters = [...chapters];
    updatedChapters[lastChapterIndex] = {
      ...lastChapter,
      sections: [...sections, normalizedSection]
    };

    methods.setValue('chapters', updatedChapters);

    // 重新计算order
    setTimeout(() => {
      recalculateSectionOrders();
      setActiveNode({
        path: `chapters.${lastChapterIndex}.sections.${sections.length}`,
        type: 'section'
      });
    }, 0);
  };

  // 重新计算所有section的order（全局单调递增）
  const recalculateSectionOrders = useCallback(() => {
    const chapters = methods.getValues('chapters') || [];
    let globalOrder = 0;
    const updatedChapters = chapters.map((chapter: Chapter) => {
      const sections = chapter.sections || [];
      const updatedSections = sections.map((section: Section) => {
        const updatedSection = { ...section, order: globalOrder };
        globalOrder++;
        return updatedSection;
      });
      return { ...chapter, sections: updatedSections };
    });
    methods.setValue('chapters', updatedChapters, { shouldValidate: false, shouldDirty: false });
  }, [methods]);

  // 监听chapters中所有sections的数量变化，自动重新计算order
  const chapters = useWatch({ control, name: 'chapters' });
  const totalSections = chapters?.reduce((total: number, chapter: Chapter) =>
    total + (chapter.sections?.length || 0), 0) || 0;

  // 使用ref来跟踪上一次的sections总数，避免不必要的重新计算
  const prevTotalSectionsRef = useRef(totalSections);

  useEffect(() => {
    // 只在sections总数真正变化时重新计算，避免循环更新
    if (chapters && chapters.length > 0 && prevTotalSectionsRef.current !== totalSections) {
      prevTotalSectionsRef.current = totalSections;
      recalculateSectionOrders();
    }
  }, [totalSections, recalculateSectionOrders, chapters]);

  // 添加章（默认标题写入 JSON，与界面「第N章」一致）
  const handleAddChapter = () => {
    const chapters = methods.getValues('chapters') || [];
    const nextIndex = chapters.length;
    const newChapter: Chapter = {
      chapter_id: uuidv4(),
      title: `第${nextIndex + 1}章`,
      order: nextIndex,
      sections: []
    };
    methods.setValue('chapters', [...chapters, newChapter]);
    setActiveNode({ path: `chapters.${chapters.length}`, type: 'chapter' });
  };

  // 添加节
  const handleAddSection = (chapterIndex: number) => {
    const chapters = methods.getValues('chapters') || [];
    const chapter = chapters[chapterIndex];
    if (!chapter) return;

    const sections = chapter.sections || [];
    // order会在recalculateSectionOrders中自动计算
    const newSection: Section = {
      section_id: uuidv4(),
      title: "",
      order: 0, // 临时值，会被自动计算覆盖
      estimated_time: 0,
      video_url: "",
      knowledge_content: '',
      leading_questions: [],
      exercises: []
    };

    const updatedChapters = [...chapters];
    updatedChapters[chapterIndex] = {
      ...chapter,
      sections: [...sections, newSection]
    };
    methods.setValue('chapters', updatedChapters);

    // 重新计算所有section的order
    setTimeout(() => {
      recalculateSectionOrders();
      setActiveNode({ path: `chapters.${chapterIndex}.sections.${sections.length}`, type: 'section' });
    }, 0);
  };

  // 移动节
  const handleMoveSection = useCallback((
    sourceChapterIndex: number,
    sourceSectionIndex: number,
    targetChapterIndex: number,
    targetSectionIndex: number
  ) => {
    const chapters = methods.getValues('chapters') || [];
    const sourceChapter = chapters[sourceChapterIndex];
    const targetChapter = chapters[targetChapterIndex];

    if (!sourceChapter || !targetChapter) return;

    const sourceSections = [...(sourceChapter.sections || [])];
    const targetSections = sourceChapterIndex === targetChapterIndex
      ? sourceSections
      : [...(targetChapter.sections || [])];

    // 获取要移动的节
    const sectionToMove = sourceSections[sourceSectionIndex];
    if (!sectionToMove) return;

    // 同章内移动：检查是否是无效移动
    if (sourceChapterIndex === targetChapterIndex) {
      if (targetSectionIndex === sourceSectionIndex || targetSectionIndex === sourceSectionIndex + 1) {
        return;
      }
    }

    // 从源位置移除
    sourceSections.splice(sourceSectionIndex, 1);

    // 计算插入位置
    const insertIndex = sourceChapterIndex === targetChapterIndex && targetSectionIndex > sourceSectionIndex
      ? targetSectionIndex - 1  // 同章且目标在后，需要-1
      : targetSectionIndex;

    // 插入到目标位置
    targetSections.splice(insertIndex, 0, sectionToMove);

    // 更新章节数据
    const updatedChapters = [...chapters];
    updatedChapters[sourceChapterIndex] = {
      ...sourceChapter,
      sections: sourceSections
    };
    if (sourceChapterIndex !== targetChapterIndex) {
      updatedChapters[targetChapterIndex] = {
        ...targetChapter,
        sections: targetSections
      };
    }
    methods.setValue('chapters', updatedChapters);

    // 重新计算所有section的order并更新选中状态
    setTimeout(() => {
      recalculateSectionOrders();
      setActiveNode({
        path: `chapters.${targetChapterIndex}.sections.${insertIndex}`,
        type: 'section'
      });
    }, 0);
  }, [methods, recalculateSectionOrders]);

  // 删除章或节
  const handleDelete = (path: string, type: 'chapter' | 'section') => {
    const chapters = methods.getValues('chapters') || [];

    if (type === 'chapter') {
      // 删除章：解析路径 chapters.0 -> 0
      const match = path.match(/chapters\.(\d+)/);
      if (!match) return;
      const chapterIndex = parseInt(match[1], 10);

      // 从数组中删除该章
      const updatedChapters = chapters.filter((_: Chapter, index: number) => index !== chapterIndex);

      // 重新计算章的order
      const reorderedChapters = updatedChapters.map((chapter: Chapter, index: number) => ({
        ...chapter,
        order: index
      }));

      methods.setValue('chapters', reorderedChapters);

      // 重新计算所有section的order
      setTimeout(() => {
        recalculateSectionOrders();
      }, 0);

      // 清除选中状态或选中第一个章
      if (reorderedChapters.length > 0) {
        setActiveNode({ path: 'chapters.0', type: 'chapter' });
      } else {
        setActiveNode({ path: 'root', type: 'course' });
      }
    } else if (type === 'section') {
      // 删除节：解析路径 chapters.0.sections.1 -> chapterIndex=0, sectionIndex=1
      const match = path.match(/chapters\.(\d+)\.sections\.(\d+)/);
      if (!match) return;
      const chapterIndex = parseInt(match[1], 10);
      const sectionIndex = parseInt(match[2], 10);

      const chapter = chapters[chapterIndex];
      if (!chapter) return;

      // 从该章的sections数组中删除该节
      const sections = chapter.sections || [];
      const updatedSections = sections.filter((_: Section, index: number) => index !== sectionIndex);

      const updatedChapters = [...chapters];
      updatedChapters[chapterIndex] = {
        ...chapter,
        sections: updatedSections
      };

      methods.setValue('chapters', updatedChapters);

      // 重新计算所有section的order
      setTimeout(() => {
        recalculateSectionOrders();
      }, 0);

      // 清除选中状态或选中该章或该章的其他节
      if (updatedSections.length > 0) {
        // 选中该章的下一个节，如果没有下一个则选中该章
        const nextSectionIndex = sectionIndex < updatedSections.length ? sectionIndex : sectionIndex - 1;
        setActiveNode({ path: `chapters.${chapterIndex}.sections.${nextSectionIndex}`, type: 'section' });
      } else {
        setActiveNode({ path: `chapters.${chapterIndex}`, type: 'chapter' });
      }
    }
  };

  return (
    <FormProvider {...methods}>
      <CategoryHiddenField />
      <div className="flex flex-col h-screen bg-white">
        <header className="px-6 py-4 border-b border-gray-300 bg-gradient-to-r from-blue-500 to-indigo-600 text-white">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">📚 课程结构编辑器</h2>

            <div className="flex items-center gap-4">
              {/* 操作按钮组 */}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    setAutoCompleteConfig({ isOpen: true, type: 'course' });
                  }}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium transition-colors border border-blue-400 shadow-sm"
                  title="一键补全全课缺失数据"
                >
                  ✨ 一键补全
                </button>
                <div className="w-px h-6 bg-white/30 self-center mx-1"></div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    openJSONFile();
                  }}
                  className="px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white rounded text-sm font-medium transition-colors border border-white/30"
                  title="从本地文件打开JSON"
                >
                  📂 选中JSON
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    saveCourseToWorkspace();
                  }}
                  disabled={openMode !== 'workspace'}
                  className={`px-3 py-1.5 text-white rounded text-sm font-medium transition-colors ${openMode !== 'workspace'
                    ? 'bg-white/10 cursor-not-allowed opacity-50'
                    : 'bg-white/20 hover:bg-white/30 border border-white/30'
                    }`}
                  title={openMode !== 'workspace' ? '只能在从工作区打开时保存' : '保存到工作区'}
                >
                  💾 保存
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    exportCourseJSON();
                  }}
                  className="px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white rounded text-sm font-medium transition-colors border border-white/30"
                  title="导出JSON文件"
                >
                  📥 另存为
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    setIsCourseLibraryOpen(true);
                  }}
                  className="px-3 py-1.5 text-white rounded text-sm font-medium transition-colors border border-white/30 bg-amber-500/90 hover:bg-amber-500"
                  title="打开学科培训课程库管理面板"
                >
                  课程库管理
                </button>
              </div>

              {/* 工作区选择 */}
              <div className="flex items-center gap-3 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-lg">
                <span className="text-sm font-medium">📁 工作区</span>
                <select
                  value={selectedWorkspace}
                  onChange={(e) => {
                    const workspace = e.target.value;
                    setSelectedWorkspace(workspace);
                    if (workspace) {
                      loadCourseFromWorkspace(workspace);
                    }
                  }}
                  className="px-3 py-2 rounded-md text-gray-800 text-sm font-medium border-2 border-blue-200 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 min-w-[200px] bg-white"
                >
                  <option value="">请选择工作区...</option>
                  {workspaces.map((ws) => (
                    <option key={ws.name} value={ws.name}>
                      {ws.name}
                    </option>
                  ))}
                </select>
                {selectedWorkspace && (
                  <span className="text-xs bg-green-400 text-green-900 px-2 py-1 rounded-full font-medium">
                    已连接
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* 当前打开模式提示 */}
          {openMode && (
            <div className="mt-2 text-xs opacity-90">
              {openMode === 'workspace' ? (
                <span className="bg-white/20 px-2 py-1 rounded">
                  💾 工作区模式 - 可保存到服务器
                </span>
              ) : (
                <span className="bg-yellow-400/30 px-2 py-1 rounded">
                  📄 文件模式 - 只能另存为导出
                </span>
              )}
            </div>
          )}
        </header>

        <div className="flex flex-1 overflow-hidden">
          {/* 左侧：结构导航 */}
          <SidebarTree
            control={control}
            onSelect={(path, type) => setActiveNode({ path, type })}
            activePath={activeNode.path}
            onAddSection={handleAddSection}
            onAddChapter={handleAddChapter}
            onMoveSection={handleMoveSection}
          />

          {/* 中间：数据编辑 */}
          <PropertyEditor
            activePath={activeNode.path}
            activeType={activeNode.type}
            onDelete={handleDelete}
            onAutoComplete={(path) => setAutoCompleteConfig({ 
              isOpen: true, 
              type: activeNode.type === 'chapter' ? 'chapter' : 'section', 
              targetPath: path 
            })}
          />

          {/* 右侧：Section展示面板 */}
          <SectionPanel sections={availableSections} onInsertSection={handleInsertSection} />
        </div>

        {/* 底部状态栏 */}
        <div className="px-6 py-2 border-t border-gray-300 bg-gray-50">
          <div className="text-sm text-gray-600">
            {activeNode.path ? `当前编辑: ${activeNode.path}` : '请选择左侧节点进行编辑'}
          </div>
        </div>

        {/* 统一对话框 */}
        <ConfirmDialog
          isOpen={dialog.isOpen}
          title={dialog.title}
          message={dialog.message}
          type={dialog.type}
          onConfirm={dialog.onConfirm}
          onCancel={closeDialog}
          confirmText={dialog.confirmText}
          cancelText={dialog.cancelText}
        />

        <CourseLibraryManager
          isOpen={isCourseLibraryOpen}
          onClose={() => setIsCourseLibraryOpen(false)}
          getCoursePayload={getSanitizedCoursePayload}
        />

        {/* 计算补全统计数据 */}
        {(() => {
          const missingStats = {
            sectionsWithMissing: 0,
            missingSummary: 0,
            missingContent: 0,
            missingExercises: 0,
            missingQuestions: 0,
            missingVideoUrl: 0,
            missingSubtitles: 0,
            details: [] as Array<{title: string, missing: string[], noUrl: boolean}>
          };

          if (autoCompleteConfig.isOpen) {
            const sectionsToProcess: Section[] = [];
            if (autoCompleteConfig.type === 'section') {
              const section = methods.getValues(autoCompleteConfig.targetPath as any) as Section;
              if (section) sectionsToProcess.push(section);
            } else if (autoCompleteConfig.type === 'chapter') {
              const chapter = methods.getValues(autoCompleteConfig.targetPath as any) as Chapter;
              if (chapter && chapter.sections) {
                sectionsToProcess.push(...chapter.sections);
              }
            } else {
              const chapters = methods.getValues('chapters') || [];
              chapters.forEach((c: Chapter) => {
                if (c.sections) {
                  sectionsToProcess.push(...c.sections);
                }
              });
            }

            sectionsToProcess.forEach(sec => {
              const missing = [];
              let noUrl = false;
              if (!sec.video_url) {
                noUrl = true;
                missingStats.missingVideoUrl++;
              } else {
                if (!sec.video_subtitles?.length) { missing.push('字幕'); missingStats.missingSubtitles++; }
                if (!sec.knowledge_points?.key_points?.length) { missing.push('知识点'); missingStats.missingSummary++; }
                if (!sec.knowledge_content) { missing.push('完整文档'); missingStats.missingContent++; }
                if (!sec.exercises?.length) { missing.push('练习题'); missingStats.missingExercises++; }
                if (!sec.leading_questions?.length) { missing.push('引导问题'); missingStats.missingQuestions++; }
              }

              if (missing.length > 0 || noUrl) {
                missingStats.sectionsWithMissing++;
                missingStats.details.push({
                  title: sec.title || '未命名小节',
                  missing,
                  noUrl
                });
              }
            });
          }

          return (
            <React.Fragment>
              {autoCompleteConfig.isOpen && (
                <div className="fixed inset-0 flex items-center justify-center z-[60] bg-black/40 backdrop-blur-sm">
                  <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl border border-gray-100 animate-scale-in max-h-[90vh] overflow-y-auto">
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-2xl">✨</span>
                      <h3 className="text-xl font-bold text-gray-800">自动补全配置</h3>
                    </div>
                    <p className="text-sm text-gray-600 mb-4 bg-blue-50 p-3 rounded-lg border border-blue-100">
                      {autoCompleteConfig.type === 'course' 
                        ? '系统将检查全课所有视频，自动过滤已有内容，仅对缺失的字幕、知识点、练习题等向 AI 发起生成任务。' 
                        : autoCompleteConfig.type === 'chapter'
                          ? '系统将检查当前章的所有视频，自动对缺失的内容向 AI 发起生成任务。'
                          : '系统将检查当前节，自动对缺失的内容向 AI 发起生成任务。'}
                    </p>

                    {/* 统计信息显示 */}
                    {missingStats.sectionsWithMissing > 0 ? (
                      <div className="mb-5 text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                        <div className="bg-gray-100 px-3 py-2 border-b border-gray-200 font-semibold flex justify-between items-center">
                          <span>待补全情况统计</span>
                          <span className="text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full text-xs">共 {missingStats.sectionsWithMissing} 节需处理</span>
                        </div>
                        <div className="p-3 max-h-40 overflow-y-auto space-y-2">
                          {missingStats.details.map((detail, i) => (
                            <div key={i} className="flex flex-col border-b border-gray-100 last:border-0 pb-2 last:pb-0">
                               <span className="font-medium text-gray-800">{detail.title}</span>
                               {detail.noUrl ? (
                                 <span className="text-red-500 text-xs mt-1">⚠️ 缺失视频链接(video_url)，无法补全</span>
                               ) : (
                                 <span className="text-gray-500 text-xs mt-1">将补全: <span className="text-blue-600">{detail.missing.join('、')}</span></span>
                               )}
                            </div>
                          ))}
                        </div>
                        <div className="bg-blue-50/50 px-3 py-2 border-t border-gray-200 text-xs text-blue-800 flex flex-wrap gap-x-3 gap-y-1">
                          <span className="font-medium">总计生成:</span>
                          {missingStats.missingSubtitles > 0 && <span>字幕 x{missingStats.missingSubtitles}</span>}
                          {missingStats.missingSummary > 0 && <span>知识点 x{missingStats.missingSummary}</span>}
                          {missingStats.missingContent > 0 && <span>文档 x{missingStats.missingContent}</span>}
                          {missingStats.missingExercises > 0 && <span>练习题 x{missingStats.missingExercises}</span>}
                          {missingStats.missingQuestions > 0 && <span>预设问题 x{missingStats.missingQuestions}</span>}
                        </div>
                      </div>
                    ) : (
                      <div className="mb-5 p-3 bg-green-50 text-green-700 border border-green-200 rounded-lg text-sm flex items-center gap-2">
                        <span>✅</span> 所选内容非常完整，无需进行任何补全！
                      </div>
                    )}
                    
                    <div className="space-y-4">
                      <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">目标工作区 <span className="text-red-500">*</span></label>
                  <select
                    id="ac-workspace"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow bg-white"
                    defaultValue={selectedWorkspace || appConfig?.last_workspace_name || ''}
                  >
                    <option value="" disabled>请选择存放生成结果的工作区...</option>
                    {workspaces.map(ws => (
                      <option key={ws.name} value={ws.name}>{ws.name}</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1.5 ml-1">生成的数据将保存在此工作区中。</p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">AI 模型 <span className="text-red-500">*</span></label>
                  <select
                    id="ac-model"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow bg-white"
                    defaultValue={appConfig?.last_selected_model || ''}
                  >
                    <option value="" disabled>请选择用于总结的AI模型...</option>
                    {models.map(m => (
                      <option key={m.model_name} value={m.model_name}>{m.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">并发处理数</label>
                  <input
                    id="ac-concurrent"
                    type="number"
                    min="1"
                    max="5"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow"
                    defaultValue={appConfig?.max_concurrent_tasks || 2}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-8 pt-4 border-t border-gray-100">
                <button
                  onClick={() => setAutoCompleteConfig({ ...autoCompleteConfig, isOpen: false })}
                  className="px-5 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors font-medium"
                >
                  取消
                </button>
                <button
                  onClick={() => {
                    const wsSelect = document.getElementById('ac-workspace') as HTMLSelectElement;
                    const modSelect = document.getElementById('ac-model') as HTMLSelectElement;
                    const concInput = document.getElementById('ac-concurrent') as HTMLInputElement;
                    
                    if (!wsSelect.value) {
                      showDialog('提示', '请选择目标工作区', 'warning');
                      return;
                    }
                    if (!modSelect.value) {
                      showDialog('提示', '请选择AI模型', 'warning');
                      return;
                    }
                    
                    handleAutoCompleteConfirm({
                      workspaceName: wsSelect.value,
                      modelName: modSelect.value,
                      maxConcurrent: parseInt(concInput.value, 10) || 2
                    });
                  }}
                  className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium shadow-sm hover:shadow"
                >
                  开始补全
                </button>
              </div>
            </div>
          </div>
        )}
        </React.Fragment>
        );
      })()}
      </div>
    </FormProvider>
  );
};

export default CourseEditor;

