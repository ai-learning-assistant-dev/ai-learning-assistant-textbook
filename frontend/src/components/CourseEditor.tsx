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
  LeadingQuestion,
} from '../types';

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

/** 不兼容旧版 JSON（含通用 id 字段）；仅整理缺省的非主键字段，主键须已为 course_id / chapter_id 等 */
function sanitizeLeadingQuestion(r: LeadingQuestion): LeadingQuestion {
  return {
    question_id: r.question_id,
    question: r.question ?? '',
  };
}

function sanitizeExerciseOption(r: ExerciseOption): ExerciseOption {
  return {
    option_id: r.option_id,
    text: r.text ?? '',
    is_correct: !!r.is_correct,
  };
}

function sanitizeExercise(r: Exercise): Exercise {
  return {
    exercise_id: r.exercise_id,
    question: r.question ?? '',
    score: typeof r.score === 'number' ? r.score : 0,
    type: r.type ?? '单选',
    answer: r.answer ?? '',
    options: (r.options ?? []).map(sanitizeExerciseOption),
  };
}

function sanitizeSection(raw: Section): Section {
  return {
    section_id: raw.section_id,
    title: raw.title ?? '',
    order: typeof raw.order === 'number' ? raw.order : 0,
    estimated_time: typeof raw.estimated_time === 'number' ? raw.estimated_time : 0,
    video_url: raw.video_url ?? '',
    knowledge_content: raw.knowledge_content ?? '',
    leading_questions: (raw.leading_questions ?? []).map(sanitizeLeadingQuestion),
    exercises: (raw.exercises ?? []).map(sanitizeExercise),
  };
}

function sanitizeChapter(raw: Chapter): Chapter {
  return {
    chapter_id: raw.chapter_id,
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
  return {
    course_id: data.course_id ?? uuidv4(),
    title: data.title ?? '',
    description: data.description ?? '',
    ai_persona: sanitizeAiPersona(data.ai_persona, data.title, data.teacher_persona),
    category: normalizeCourseCategory(data.category),
    icon_url: data.icon_url ?? '',
    chapters: (data.chapters ?? []).map(sanitizeChapter),
  };
}

/**
 * 学习助手 delete/import 使用带连字符的标准 UUID。
 * 若 course_id 为 32 位 hex（无连字符），格式化为 8-4-4-4-12；已为 UUID 则规范化小写后原样使用。
 */
function courseIdForApi(raw: string): string {
  const s = raw.trim().toLowerCase();
  if (!s) return s;
  const hexOnly = s.replace(/-/g, '');
  if (hexOnly.length === 32 && /^[0-9a-f]+$/.test(hexOnly)) {
    return `${hexOnly.slice(0, 8)}-${hexOnly.slice(8, 12)}-${hexOnly.slice(12, 16)}-${hexOnly.slice(16, 20)}-${hexOnly.slice(20, 32)}`;
  }
  return s;
}

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
              className={`flex-1 p-2 cursor-pointer rounded mb-1 ${activePath === `chapters.${cIdx}`
                ? 'bg-indigo-500 text-white'
                : 'bg-indigo-100 hover:bg-indigo-200'
                }`}
            >
              📂 <strong>{chapter.title || `第${cIdx + 1}章`}</strong>
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
                    🎥 {section.title || `第${globalSectionIndex + 1}节`}
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
}

const PropertyEditor: React.FC<PropertyEditorProps> = ({ activePath, activeType, onDelete }) => {
  const { register, control, setValue } = useFormContext();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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
        {/* 删除按钮（只在章或节时显示） */}
        {(activeType === 'chapter' || activeType === 'section') && (
          <button
            onClick={handleDeleteClick}
            className="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
          >
            删除
          </button>
        )}
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
              <span className="text-xs text-gray-500 font-normal ml-2">将按 ai_persona 对象格式保存和导入学习助手</span>
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

          <hr className="my-6 border-gray-200" />

          {/* 引导问题管理 */}
          <LeadingQuestionsManager key={`questions-${activePath}`} activePath={activePath} />

          <hr className="my-6 border-gray-200" />

          {/* 练习题管理 */}
          <ExercisesManager key={`exercises-${activePath}`} activePath={activePath} />
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
  workspaces?: Array<{ name: string; path: string }>;
}

const CourseEditor: React.FC<CourseEditorProps> = ({ initialData, onSave: _onSave, workspaces = [] }) => {
  const defaultValues: CourseData = initialData
    ? sanitizeCourseData(initialData)
    : {
      course_id: uuidv4(),
      title: "",
      description: "",
      ai_persona: createDefaultAiPersona(""),
      category: DEFAULT_COURSE_CATEGORY,
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

  // 统一对话框状态
  const [isSubmittingCourse, setIsSubmittingCourse] = useState(false);

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

  /** 与另存为/导入学习助手共用：保证 category 写入快照（含 normalize 默认值） */
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
  const saveCourseToWorkspace = async () => {
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
        showDialog('保存成功', '课程已成功保存到工作区', 'success');
      } else {
        showDialog('保存失败', data.error || '未知错误', 'error');
      }
    } catch (error) {
      showDialog('保存失败', error instanceof Error ? error.message : '未知错误', 'error');
    }
  };

  /** 导入到学习助手；覆盖场景下可先 delete 再 import，新课程可跳过 delete */
  const performSubmitCourseToLibrary = async (options?: { skipDelete?: boolean }) => {
    const courseData = getSanitizedCoursePayload();
    const courseId = (courseData.course_id || '').trim();
    if (!courseId) {
      showDialog('提示', '请先填写课程 ID', 'warning');
      return;
    }

    const courseIdNormalized = courseIdForApi(courseId);

    setIsSubmittingCourse(true);
    try {
      if (!options?.skipDelete) {
        const delRes = await fetch('/api/courses/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ course_id: courseIdNormalized }),
        });

        const delRaw = await delRes.text();
        let delJson: Record<string, unknown> = {};
        try {
          delJson = delRaw ? (JSON.parse(delRaw) as Record<string, unknown>) : {};
        } catch {
          /* 非 JSON 响应 */
        }

        const delFailed =
          delRes.status !== 404 &&
          (!delRes.ok || delJson.success === false);
        if (delFailed) {
          const msg =
            (delJson.message as string) ||
            (delJson.error as string) ||
            delRaw ||
            `HTTP ${delRes.status}`;
          showDialog('删除课程失败', msg, 'error');
          return;
        }
      }

      const impRes = await fetch('/api/courses/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...courseData, course_id: courseIdNormalized }),
      });

      let impBody: Record<string, unknown> = {};
      try {
        impBody = (await impRes.json()) as Record<string, unknown>;
      } catch {
        /* ignore */
      }

      const impOk =
        impRes.ok &&
        (impBody.success === undefined || impBody.success === true);
      if (!impOk) {
        const msg =
          (impBody.message as string) ||
          (impBody.error as string) ||
          `HTTP ${impRes.status}`;
        showDialog('导入课程失败', msg, 'error');
        return;
      }

      showDialog(
        '导入成功',
        ((impBody.message as string) || '已同步到学习助手') as string,
        'success'
      );
    } catch (error) {
      showDialog(
        '导入失败',
        error instanceof Error ? error.message : '网络或服务器错误',
        'error'
      );
    } finally {
      setIsSubmittingCourse(false);
    }
  };

  /** 先 getById：无课程则直接导入；已有则简短确认后再删再导 */
  const requestSubmitCourseToLibrary = () => {
    void (async () => {
      const courseData = methods.getValues();
      const courseId = (courseData.course_id || '').trim();
      if (!courseId) {
        showDialog('提示', '请先填写课程 ID', 'warning');
        return;
      }

      const courseIdNormalized = courseIdForApi(courseId);

      try {
        const res = await fetch('/api/courses/getById', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ course_id: courseIdNormalized }),
        });

        let body: Record<string, unknown> = {};
        try {
          body = (await res.json()) as Record<string, unknown>;
        } catch {
          /* ignore */
        }

        if (!res.ok && res.status !== 404) {
          const msg =
            (body.message as string) ||
            (body.error as string) ||
            `查询课程失败（HTTP ${res.status}）`;
          showDialog('无法导入', msg, 'error');
          return;
        }

        const exists =
          res.status !== 404 &&
          res.ok &&
          body.success === true &&
          body.data != null &&
          typeof body.data === 'object';

        if (!exists) {
          void performSubmitCourseToLibrary({ skipDelete: true });
          return;
        }

        const data = body.data as { name?: string };
        const nameHint = data.name ? `「${data.name}」` : '';
        showDialog(
          '导入到学习助手',
          `学习助手已有该课程${nameHint}，导入将覆盖原有内容。是否继续？`,
          'confirm',
          () => void performSubmitCourseToLibrary({ skipDelete: false }),
          '覆盖并导入',
          '取消'
        );
      } catch (error) {
        showDialog(
          '无法导入',
          error instanceof Error ? error.message : '网络错误',
          'error'
        );
      }
    })();
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
          setAvailableSections([]); // 清空可用sections
          setSelectedWorkspace(''); // 清空工作区选择
          setOpenMode('file');
          showDialog('加载成功', 'JSON文件已成功加载', 'success');
        } catch (error) {
          showDialog('格式错误', error instanceof Error ? error.message : 'JSON文件格式错误', 'error');
        }
      };
      reader.readAsText(file);
    };
    input.click();
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
                  onClick={openJSONFile}
                  className="px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white rounded text-sm font-medium transition-colors border border-white/30"
                  title="从本地文件打开JSON"
                >
                  📂 选中JSON
                </button>
                <button
                  onClick={saveCourseToWorkspace}
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
                  onClick={exportCourseJSON}
                  className="px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white rounded text-sm font-medium transition-colors border border-white/30"
                  title="导出JSON文件"
                >
                  📥 另存为
                </button>
                <button
                  type="button"
                  onClick={requestSubmitCourseToLibrary}
                  disabled={isSubmittingCourse}
                  className={`px-3 py-1.5 text-white rounded text-sm font-medium transition-colors border border-white/30 ${isSubmittingCourse
                    ? 'bg-white/10 cursor-not-allowed opacity-60'
                    : 'bg-amber-500/90 hover:bg-amber-500'
                    }`}
                  title="将查询学习助手是否已有该课程；无则直接导入，有则确认后覆盖导入"
                >
                  {isSubmittingCourse ? '导入中…' : '导入学习助手'}
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
      </div>
    </FormProvider>
  );
};

export default CourseEditor;

