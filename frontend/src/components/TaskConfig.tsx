import { useState, useEffect, FormEvent, ChangeEvent } from 'react';
import Alert from './Alert';
import { Model, AppConfig, AlertProps, CreateTaskRequest, Workspace } from '../types';

interface TaskConfigProps {
  models: Model[];
  workspaces: Workspace[];
  appConfig: AppConfig;
  onTaskSubmit: (taskData: CreateTaskRequest) => Promise<void>;
  alert: AlertProps | null;
  onConfigChange: (updates: Partial<AppConfig>) => Promise<void>;
}

interface TaskFormData {
  videoUrls: string;
  workspaceName: string;
  downloadAllParts: boolean;
  maxConcurrentTasks: number;
  genSummary: boolean;
  genFullContent: boolean;
  genExercises: boolean;
  genQuestions: boolean;
  modelName: string;
}

export default function TaskConfig({
  models,
  workspaces,
  appConfig,
  onTaskSubmit,
  alert,
  onConfigChange,
}: TaskConfigProps) {
  const [formData, setFormData] = useState<TaskFormData>({
    videoUrls: '',
    workspaceName: '',
    downloadAllParts: false,
    maxConcurrentTasks: 2,
    genSummary: true,
    genFullContent: true,
    genExercises: true,
    genQuestions: true,
    modelName: '',
  });

  useEffect(() => {
    if (appConfig) {
      setFormData((prev) => ({
        ...prev,
        downloadAllParts: appConfig.download_all_parts || false,
        maxConcurrentTasks: appConfig.max_concurrent_tasks || 2,
        modelName: appConfig.last_selected_model || '',
        workspaceName: appConfig.last_workspace_name || '',
      }));
    }
  }, [appConfig]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const urls = formData.videoUrls
      .split('\n')
      .map((u) => u.trim())
      .filter((u) => u);

    if (urls.length === 0) {
      return;
    }

    if (!formData.modelName) {
      return;
    }

    if (!formData.workspaceName) {
      return;
    }

    const generateOptions = {
      summary: formData.genSummary,
      full_content: formData.genFullContent,
      exercises: formData.genExercises,
      questions: formData.genQuestions,
    };

    await onTaskSubmit({
      urls,
      workspace_name: formData.workspaceName,
      model_name: formData.modelName,
      download_all_parts: formData.downloadAllParts,
      generate_options: generateOptions,
    });

    setFormData((prev) => ({ ...prev, videoUrls: '' }));
  };

  const handleDownloadAllPartsChange = async (checked: boolean) => {
    setFormData((prev) => ({ ...prev, downloadAllParts: checked }));
    await onConfigChange({ download_all_parts: checked });
  };

  const handleMaxConcurrentChange = async (value: string) => {
    const numValue = parseInt(value);
    if (numValue >= 1 && numValue <= 10) {
      setFormData((prev) => ({ ...prev, maxConcurrentTasks: numValue }));
      await onConfigChange({ max_concurrent_tasks: numValue });
    }
  };

  return (
    <div>
      <div className="flex items-center mb-4">
        <div className="w-1 h-5 bg-indigo-500 rounded mr-2.5"></div>
        <h2 className="text-lg font-semibold text-gray-800">创建下载任务</h2>
      </div>

      {alert && <Alert {...alert} />}

      <form onSubmit={handleSubmit}>
        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            视频URL（每行一个）
          </label>
          <textarea
            className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 resize-y min-h-[120px] font-inherit"
            placeholder="支持视频URL：&#10;https://www.bilibili.com/video/BV1xx411c7mu&#10;&#10;支持分P视频URL：&#10;https://www.bilibili.com/video/BV1xx411c7mu?p=2&#10;&#10;支持收藏夹URL：&#10;https://space.bilibili.com/UID/favlist?fid=收藏夹ID"
            value={formData.videoUrls}
            onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
              setFormData({ ...formData, videoUrls: e.target.value })
            }
            required
          />
          <div className="text-xs text-gray-600 mt-1">
            💡 提示：支持单个视频URL、多个视频URL和收藏夹URL混合输入，收藏夹会自动展开
          </div>
        </div>

        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            选择工作区 <span className="text-red-500">*</span>
          </label>
          <select
            className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            value={formData.workspaceName}
            onChange={(e: ChangeEvent<HTMLSelectElement>) =>
              setFormData({ ...formData, workspaceName: e.target.value })
            }
            required
          >
            <option value="">请选择工作区</option>
            {workspaces.map((workspace) => (
              <option key={workspace.name} value={workspace.name}>
                {workspace.name} ({workspace.path})
              </option>
            ))}
          </select>
          <div className="text-xs text-gray-600 mt-1">
            💡 提示：视频文件将保存到所选工作区的路径下。如果没有工作区，请先在上方"工作区配置"中添加
          </div>
        </div>

        <div className="mb-5">
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              className="cursor-pointer w-[18px] h-[18px]"
              checked={formData.downloadAllParts}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                handleDownloadAllPartsChange(e.target.checked)
              }
            />
            <span className="block text-sm font-medium text-gray-700">下载所有分P视频</span>
          </label>
          <div className="text-xs text-gray-600 mt-1 ml-7">
            💡 提示：关闭时（默认），只下载URL指定的那一个视频；开启时，下载该视频的所有分P
          </div>
        </div>

        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            最大并发任务数
          </label>
          <input
            type="number"
            className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            min="1"
            max="10"
            value={formData.maxConcurrentTasks}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              handleMaxConcurrentChange(e.target.value)
            }
            placeholder="同时处理的视频数量"
          />
          <div className="text-xs text-gray-600 mt-1">
            💡 提示：同时处理的视频数量。设置为1可避免API并发限制，设置为2-3可提高效率（需要API支持）
          </div>
        </div>

        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">生成内容选项</label>
          <div className="flex gap-4 flex-wrap p-2.5 bg-gray-50 rounded-lg border border-gray-200">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.genSummary}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setFormData({ ...formData, genSummary: e.target.checked })
                }
              />
              <span>要点总结</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.genFullContent}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setFormData({ ...formData, genFullContent: e.target.checked })
                }
              />
              <span>完整文档</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.genExercises}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setFormData({ ...formData, genExercises: e.target.checked })
                }
              />
              <span>练习题</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.genQuestions}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setFormData({ ...formData, genQuestions: e.target.checked })
                }
              />
              <span>预设问题</span>
            </label>
          </div>
        </div>

        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">选择模型</label>
          <select
            className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            value={formData.modelName}
            onChange={(e: ChangeEvent<HTMLSelectElement>) =>
              setFormData({ ...formData, modelName: e.target.value })
            }
            required
          >
            <option value="">请选择模型</option>
            {models.map((model) => (
              <option key={model.id} value={model.name}>
                {model.name}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          className="px-6 py-3 rounded-lg text-sm font-medium bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:shadow-lg hover:-translate-y-0.5 transition-all"
        >
          开始处理
        </button>
      </form>
    </div>
  );
}

