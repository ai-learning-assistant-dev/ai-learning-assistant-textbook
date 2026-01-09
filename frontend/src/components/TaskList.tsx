import { Task, TaskStatus } from '../types';

interface TaskListProps {
  tasks: Record<string, Task>;
  onStopTask: (taskId: string) => Promise<void>;
}

export default function TaskList({ tasks, onStopTask }: TaskListProps) {
  const getStatusText = (status: TaskStatus): string => {
    const statusMap: Record<TaskStatus, string> = {
      pending: '等待中',
      downloading: '下载中',
      summarizing: '总结中',
      completed: '已完成',
      failed: '失败',
      stopping: '正在停止',
      stopped: '已停止',
    };
    return statusMap[status] || status;
  };

  const getStatusClass = (status: TaskStatus): string => {
    const statusClasses: Record<TaskStatus, string> = {
      pending: 'bg-orange-500',
      downloading: 'bg-blue-500',
      summarizing: 'bg-indigo-500',
      completed: 'bg-green-500',
      failed: 'bg-red-500',
      stopped: 'bg-gray-500',
      stopping: 'bg-yellow-500',
    };
    return statusClasses[status] || 'bg-gray-500';
  };

  const getBorderClass = (status: TaskStatus): string => {
    const borderClasses: Record<TaskStatus, string> = {
      pending: 'border-l-orange-500',
      downloading: 'border-l-blue-500',
      summarizing: 'border-l-indigo-500',
      completed: 'border-l-green-500',
      failed: 'border-l-red-500',
      stopped: 'border-l-gray-500',
      stopping: 'border-l-yellow-500',
    };
    return borderClasses[status] || 'border-l-gray-400';
  };

  const getFileName = (path: string | undefined): string => {
    if (!path) return '';
    return path.split(/[/\\]/).pop() || '';
  };

  const taskList = Object.values(tasks);

  if (taskList.length === 0) {
    return (
      <div className="mb-8">
        <div className="flex items-center mb-4">
          <div className="w-1 h-5 bg-blue-500 rounded mr-2.5"></div>
          <h2 className="text-lg font-semibold text-gray-800">任务列表</h2>
        </div>
        <div className="text-center py-10 text-gray-500">暂无任务</div>
      </div>
    );
  }

  const sortedTasks = [...taskList].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="mb-8">
      <div className="flex items-center mb-4">
        <div className="w-1 h-5 bg-blue-500 rounded mr-2.5"></div>
        <h2 className="text-lg font-semibold text-gray-800">任务列表</h2>
      </div>
      <div className="grid gap-4">
        {sortedTasks.map((task) => {
          const statusText = getStatusText(task.status);
          const statusClass = getStatusClass(task.status);
          const borderClass = getBorderClass(task.status);

          const showStopButton = task.status === 'downloading' || task.status === 'summarizing';

          return (
            <div
              key={task.id}
              className={`bg-gray-50 p-4 rounded-lg border-l-4 ${borderClass}`}
            >
              <div className="text-sm text-gray-800 mb-2 break-words">{task.url}</div>
              {task.video_title && (
                <div className="text-[13px] text-gray-600 mt-1">📹 {task.video_title}</div>
              )}
              <div className="mt-2 flex items-center">
                <span
                  className={`inline-block px-3 py-1 rounded-xl text-xs font-medium text-white ${statusClass}`}
                >
                  {statusText}
                </span>
                {showStopButton && (
                  <button
                    className="ml-2.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 transition-all"
                    onClick={async () => {
                      if (window.confirm('确定要停止这个任务吗？')) {
                        await onStopTask(task.id);
                      }
                    }}
                    title="停止任务"
                  >
                    ⏹ 停止
                  </button>
                )}
              </div>
              <div className="text-[13px] text-gray-600 mt-2">{task.message}</div>
              {task.status === 'completed' && task.files && (
                <div className="mt-2.5 pt-2.5 border-t border-gray-200">
                  <div className="text-[13px] font-semibold text-gray-800 mb-1.5">
                    📁 生成的文件：
                  </div>
                  <div className="text-xs text-gray-600 leading-7">
                    {task.files.video_dir && (
                      <div>
                        📂 输出目录:{' '}
                        <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">
                          {task.files.video_dir}
                        </code>
                      </div>
                    )}
                    {task.files.subtitle && (
                      <div>📝 字幕文件: {getFileName(task.files.subtitle)}</div>
                    )}
                    {task.files.cover && (
                      <div>🖼️ 封面图片: {getFileName(task.files.cover)}</div>
                    )}
                    {task.files.summary_json && (
                      <div>📄 要点总结: {getFileName(task.files.summary_json)}</div>
                    )}
                    {task.files.content_md && (
                      <div>📚 完整文档: {getFileName(task.files.content_md)}</div>
                    )}
                    {task.files.exercises && (
                      <div>📝 练习题: {getFileName(task.files.exercises)}</div>
                    )}
                    {task.files.questions && (
                      <div>❓预设问题: {getFileName(task.files.questions)}</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}


