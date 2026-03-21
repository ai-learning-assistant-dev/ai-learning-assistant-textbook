import { useState, useEffect, useCallback } from 'react';
import ModelConfig from './components/ModelConfig';
import WorkspaceConfig from './components/WorkspaceConfig';
import TaskConfig from './components/TaskConfig';
import TaskList from './components/TaskList';
import CourseEditor from './components/CourseEditor';
import CookieConfig from './components/CookieConfig'; 
import {
  Model,
  Task,
  AppConfig,
  AlertProps,
  CreateTaskRequest,
  ConfigResponse,
  CookiesConfigResponse,
  ModelsResponse,
  CreateTaskResponse,
  TasksResponse,
  ApiResponse,
  CourseData,
  Workspace,
  WorkspacesResponse,
} from './types';
import './App.css';

// 工作区配置功能已添加
function App() {
  const [activeTab, setActiveTab] = useState<'video' | 'course'>('video');
  const [models, setModels] = useState<Model[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [tasks, setTasks] = useState<Record<string, Task>>({});
  const [appConfig, setAppConfig] = useState<AppConfig>({});
  const [modelAlert, setModelAlert] = useState<AlertProps | null>(null);
  const [workspaceAlert, setWorkspaceAlert] = useState<AlertProps | null>(null);
  const [taskAlert, setTaskAlert] = useState<AlertProps | null>(null);
  const [pollInterval, setPollInterval] = useState<number | null>(null);
  const [courseData, setCourseData] = useState<CourseData | null>(null);
  const [isPollingActive, setIsPollingActive] = useState<boolean>(false);

  // 加载应用配置
  const loadAppConfig = useCallback(async () => {
    try {
      const response = await fetch('/api/config');

      if (!response.ok) {
        console.warn('加载配置失败:', response.status, response.statusText);
        return;
      }

      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        console.warn('配置API返回的不是JSON格式，后端服务可能未启动');
        return;
      }

      const data: ConfigResponse = await response.json();

      if (data.success && data.config) {
        setAppConfig(data.config);
      }
    } catch (error) {
      console.error('加载配置失败:', error);
    }
  }, []);

  // 保存应用配置
  const saveAppConfig = useCallback(async (updates: Partial<AppConfig>) => {
    try {
      const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });

      const data: ConfigResponse = await response.json();
      if (data.success && data.config) {
        setAppConfig(data.config);
      }
    } catch (error) {
      console.error('保存配置失败:', error);
    }
  }, []);

  // 检查Cookie配置
  const checkCookiesConfig = useCallback(async () => {
    try {
      const response = await fetch('/api/config/cookies');

      if (!response.ok) {
        return; // 静默失败，不影响主流程
      }

      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        return; // 静默失败
      }

      const data: CookiesConfigResponse = await response.json();

      if (!data.configured) {
        setTaskAlert({
          message: '提示：请先配置cookies.txt文件中的SESSDATA，否则无法下载AI字幕',
          type: 'warning',
        });
      }
    } catch (error) {
      console.error('检查Cookie配置失败:', error);
    }
  }, []);

  // 加载模型列表
  const loadModels = useCallback(async () => {
    try {
      const response = await fetch('/api/models');

      // 检查响应状态
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
      }

      // 检查内容类型
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        throw new Error(
          `服务器返回的不是JSON格式。可能是后端服务未启动或API路径配置错误。响应内容: ${text.substring(0, 100)}`
        );
      }

      const data: ModelsResponse = await response.json();

      if (data.success && data.models) {
        setModels(data.models);
      } else {
        setModelAlert({ message: '加载模型失败: ' + (data.error || '未知错误'), type: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setModelAlert({
        message: '加载模型失败: ' + errorMessage + '。请确保后端服务已启动并正确配置API路径。',
        type: 'error',
      });
    }
  }, []);

  // 加载工作区列表
  const loadWorkspaces = useCallback(async () => {
    try {
      const response = await fetch('/api/workspace');

      if (!response.ok) {
        console.warn('加载工作区失败:', response.status, response.statusText);
        return;
      }

      const data: WorkspacesResponse = await response.json();

      if (data.success && data.workspaces) {
        setWorkspaces(data.workspaces);
      }
    } catch (error) {
      console.error('加载工作区失败:', error);
    }
  }, []);

  // 添加模型
  const handleAddModel = useCallback(
    async (modelData: Omit<Model, 'id'>) => {
      try {
        const response = await fetch('/api/models', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(modelData),
        });

        const data: ApiResponse = await response.json();

        if (data.success) {
          setModelAlert({ message: '添加成功', type: 'success' });
          await loadModels();
          setTimeout(() => setModelAlert(null), 3000);
        } else {
          alert('操作失败: ' + (data.error || '未知错误'));
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '未知错误';
        alert('操作失败: ' + errorMessage);
      }
    },
    [loadModels]
  );

  // 编辑模型
  const handleEditModel = useCallback(
    async (modelId: string, modelData: Omit<Model, 'id'>) => {
      try {
        const response = await fetch(`/api/models/${modelId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(modelData),
        });

        const data: ApiResponse = await response.json();

        if (data.success) {
          setModelAlert({ message: '更新成功', type: 'success' });
          await loadModels();
          setTimeout(() => setModelAlert(null), 3000);
        } else {
          alert('操作失败: ' + (data.error || '未知错误'));
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '未知错误';
        alert('操作失败: ' + errorMessage);
      }
    },
    [loadModels]
  );

  // 删除模型
  const handleDeleteModel = useCallback(
    async (modelId: string) => {
      try {
        const response = await fetch(`/api/models/${modelId}`, {
          method: 'DELETE',
        });

        const data: ApiResponse = await response.json();

        if (data.success) {
          setModelAlert({ message: '删除成功', type: 'success' });
          await loadModels();
          setTimeout(() => setModelAlert(null), 3000);
        } else {
          setModelAlert({ message: '删除失败: ' + (data.error || '未知错误'), type: 'error' });
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '未知错误';
        setModelAlert({ message: '删除失败: ' + errorMessage, type: 'error' });
      }
    },
    [loadModels]
  );

  // 加载任务列表
  const loadTasks = useCallback(async () => {
    try {
      const response = await fetch('/api/tasks');
      const data: TasksResponse = await response.json();

      if (data.success && data.tasks) {
        const tasksMap: Record<string, Task> = {};
        data.tasks.forEach((task) => {
          tasksMap[task.id] = task;
        });
        setTasks(tasksMap);

        // 检查是否还有活跃任务（非完成、失败或已停止状态的任务）
        const activeTasks = data.tasks.filter(
          (t) => !['completed', 'failed', 'stopped'].includes(t.status)
        );

        // 如果没有活跃任务，停止轮询
        if (activeTasks.length === 0 && isPollingActive) {
          console.log("停止轮询：没有活跃任务");
          stopPolling(); // 使用新的停止轮询函数
        }
      }
    } catch (error) {
      console.error('加载任务失败:', error);
      // 如果请求失败，停止轮询以避免错误循环
      if (isPollingActive) {
        console.log("因错误停止轮询");
        stopPolling(); // 使用新的停止轮询函数
      }
    }
  }, [isPollingActive]); // 更新依赖项

  // 新增停止轮询函数
  const stopPolling = useCallback(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
      setPollInterval(null);
    }
    setIsPollingActive(false);
  }, [pollInterval]);

  // 开始轮询任务状态
  const startPolling = useCallback(() => {
    // 如果已经在轮询，则不重复开始
    if (isPollingActive) {
      return;
    }

    loadTasks(); // 立即加载一次
    const interval = window.setInterval(loadTasks, 2000); // 使用window.setInterval明确指定使用浏览器API
    setPollInterval(interval);
    setIsPollingActive(true);
  }, [loadTasks, isPollingActive]);

  // 处理任务提交
  const handleTaskSubmit = useCallback(
    async (taskData: CreateTaskRequest) => {
      const urls = taskData.urls;
      if (urls.length === 0) {
        setTaskAlert({ message: '请输入至少一个视频URL', type: 'error' });
        return;
      }

      if (!taskData.model_name) {
        setTaskAlert({ message: '请选择模型', type: 'error' });
        return;
      }

      try {
        const response = await fetch('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData),
        });

        const data: CreateTaskResponse = await response.json();

        if (data.success) {
          const message = data.total_videos
            ? `已创建 ${data.task_ids.length} 个任务，共 ${data.total_videos} 个视频`
            : `已创建 ${data.task_ids.length} 个任务`;
          setTaskAlert({ message, type: 'success' });
          setTimeout(() => setTaskAlert(null), 3000);

          // 保存选择的模型和工作区
          await saveAppConfig({
            last_selected_model: taskData.model_name,
            last_workspace_name: taskData.workspace_name
          });

          // 开始轮询任务状态
          startPolling();
        } else {
          setTaskAlert({ message: '创建任务失败: ' + (data.error || '未知错误'), type: 'error' });
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '未知错误';
        setTaskAlert({ message: '创建任务失败: ' + errorMessage, type: 'error' });
      }
    },
    [saveAppConfig, startPolling]
  );

  // 停止任务
  const handleStopTask = useCallback(
    async (taskId: string) => {
      try {
        const response = await fetch(`/api/tasks/${taskId}/stop`, {
          method: 'POST',
        });

        const data: ApiResponse = await response.json();

        if (data.success) {
          loadTasks();
        } else {
          setTaskAlert({ message: '停止任务失败: ' + (data.error || '未知错误'), type: 'error' });
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '未知错误';
        setTaskAlert({ message: '停止任务失败: ' + errorMessage, type: 'error' });
      }
    },
    [loadTasks]
  );

  // 初始化
  useEffect(() => {
    loadAppConfig();
    loadModels();
    loadWorkspaces();
    checkCookiesConfig();
  }, [loadAppConfig, loadModels, loadWorkspaces, checkCookiesConfig]);

  // 清理轮询
  useEffect(() => {
    return () => {
      if (pollInterval) {
        console.log("清理轮询定时器");
        clearInterval(pollInterval);
      }
    };
  }, [pollInterval]);

  // 处理课程数据保存
  const handleCourseSave = useCallback((data: CourseData) => {
    setCourseData(data);
    const jsonStr = JSON.stringify(data, null, 2);
    console.log("课程数据已保存:", jsonStr);

    // 创建下载链接
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `course-${data.course_id || Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    alert('课程数据已保存并下载！');
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* 标签页导航 */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-5">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('video')}
              className={`px-6 py-3 font-medium transition-colors ${activeTab === 'video'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
                }`}
            >
              📹 视频下载
            </button>
            <button
              onClick={() => setActiveTab('course')}
              className={`px-6 py-3 font-medium transition-colors ${activeTab === 'course'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
                }`}
            >
              📚 课程编辑
            </button>
          </div>
        </div>
      </div>

      {activeTab === 'video' && (
        <div className="min-h-screen p-6">
          <div className="max-w-[1600px] mx-auto">
            {/* 页面标题 */}
            <div className="mb-6 bg-white rounded-xl shadow-lg overflow-hidden">
              <div className="bg-gradient-to-r from-blue-500 to-indigo-600 text-white p-6">
                <h1 className="text-2xl font-bold mb-2">📹 Bilibili视频字幕下载与总结</h1>
                <p className="opacity-90 text-sm">
                  批量下载B站视频字幕，AI自动生成内容总结 · 支持收藏夹批量处理
                </p>
              </div>
            </div>

            {/* 双栏布局 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 左侧配置区域 */}
              <div className="lg:col-span-1 space-y-6">
                <div className="bg-white rounded-xl shadow-lg p-6">
                  <ModelConfig
                    models={models}
                    onAddModel={handleAddModel}
                    onEditModel={handleEditModel}
                    onDeleteModel={handleDeleteModel}
                    alert={modelAlert}
                  />
                </div>

                <div className="bg-white rounded-xl shadow-lg p-6">
                  <WorkspaceConfig
                    alert={workspaceAlert}
                    appConfig={appConfig}
                    onWorkspacesChange={loadWorkspaces}
                  />
                </div>

                {/* 新增Cookie配置卡片 */}
                <div className="bg-white rounded-xl shadow-lg p-6">
                  <CookieConfig
                    alert={taskAlert} // 可以复用taskAlert或创建独立的alert状态
                  />
                </div>
              </div>

              {/* 右侧任务区域 */}
              <div className="lg:col-span-2 space-y-6">
                <div className="bg-white rounded-xl shadow-lg p-6">
                  <TaskConfig
                    models={models}
                    workspaces={workspaces}
                    appConfig={appConfig}
                    onTaskSubmit={handleTaskSubmit}
                    alert={taskAlert}
                    onConfigChange={saveAppConfig}
                  />
                </div>

                <div className="bg-white rounded-xl shadow-lg p-6">
                  <TaskList tasks={tasks} onStopTask={handleStopTask} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'course' && (
        <div className="h-[calc(100vh-60px)]">
          <CourseEditor initialData={courseData || undefined} onSave={handleCourseSave} workspaces={workspaces} />
        </div>
      )}
    </div>
  );
}

export default App;

