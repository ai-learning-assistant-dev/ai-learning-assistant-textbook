import { useState, useEffect, useCallback } from 'react';
import Alert from './Alert';
import { AlertProps, AppConfig } from '../types';

interface Workspace {
  name: string;
  path: string;
  created_at: string;
}

interface WorkspaceConfigProps {
  alert: AlertProps | null;
  appConfig: AppConfig;
  onWorkspacesChange: () => void;
}

export default function WorkspaceConfig({ alert, appConfig, onWorkspacesChange }: WorkspaceConfigProps) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isListCollapsed, setIsListCollapsed] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [workspaceAlert, setWorkspaceAlert] = useState<AlertProps | null>(null);
  const [formData, setFormData] = useState({ name: '', path: '' });

  // 当工作区名称改变时，自动生成默认路径
  const handleNameChange = (name: string) => {
    const baseDir = appConfig.output_directory || './subtitles';
    setFormData({
      name,
      path: name ? `${baseDir}/${name}` : ''
    });
  };

  // 加载工作区列表
  const loadWorkspaces = useCallback(async () => {
    try {
      const response = await fetch('/api/workspace');
      const data = await response.json();

      if (data.success && data.workspaces) {
        setWorkspaces(data.workspaces);
      } else {
        setWorkspaceAlert({ message: '加载工作区失败: ' + (data.error || '未知错误'), type: 'error' });
      }
    } catch (error) {
      console.error('加载工作区失败:', error);
      setWorkspaceAlert({
        message: '加载工作区失败: ' + (error instanceof Error ? error.message : '未知错误'),
        type: 'error'
      });
    }
  }, []);

  // 初始化加载
  useEffect(() => {
    loadWorkspaces();
  }, [loadWorkspaces]);

  // 添加工作区
  const handleAdd = async () => {
    const { name, path } = formData;

    if (!name.trim()) {
      setWorkspaceAlert({ message: '请输入工作区名称', type: 'error' });
      return;
    }

    if (!path.trim()) {
      setWorkspaceAlert({ message: '请输入工作区路径', type: 'error' });
      return;
    }

    try {
      const response = await fetch('/api/workspace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), path: path.trim() }),
      });

      const data = await response.json();

      if (data.success) {
        setWorkspaceAlert({ message: '添加成功', type: 'success' });
        setFormData({ name: '', path: '' });
        setIsAdding(false);
        await loadWorkspaces();
        onWorkspacesChange();
        setTimeout(() => setWorkspaceAlert(null), 3000);
      } else {
        setWorkspaceAlert({ message: data.error || '添加失败', type: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setWorkspaceAlert({ message: '添加失败: ' + errorMessage, type: 'error' });
    }
  };

  // 删除工作区
  const handleDelete = async (workspaceName: string) => {
    if (!window.confirm(`确定要删除工作区 "${workspaceName}" 吗？`)) {
      return;
    }

    try {
      const response = await fetch(`/api/workspace/${encodeURIComponent(workspaceName)}`, {
        method: 'DELETE',
      });

      const data = await response.json();

      if (data.success) {
        setWorkspaceAlert({ message: '删除成功', type: 'success' });
        await loadWorkspaces();
        onWorkspacesChange();
        setTimeout(() => setWorkspaceAlert(null), 3000);
      } else {
        setWorkspaceAlert({ message: '删除失败: ' + (data.error || '未知错误'), type: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setWorkspaceAlert({ message: '删除失败: ' + errorMessage, type: 'error' });
    }
  };

  // 取消添加
  const handleCancel = () => {
    setIsAdding(false);
    setFormData({ name: '', path: '' });
    setWorkspaceAlert(null);
  };

  return (
    <div>
      <div className="flex items-center mb-4">
        <div className="w-1 h-5 bg-green-500 rounded mr-2.5"></div>
        <h2 className="text-lg font-semibold text-gray-800">工作区配置</h2>
      </div>
      <div className="mb-3">
        <h3 className="text-xs text-gray-600 mt-1">🤔工作区代表单一课程的工作文件夹，包括该课程的中间素材和最终结果。</h3>
      </div>

      {(alert || workspaceAlert) && <Alert {...(workspaceAlert || alert!)} />}

      <div className="flex justify-between items-center mb-3">
        <span className="text-sm text-gray-600">
          {workspaces.length === 0 ? '暂无工作区' : `已配置 ${workspaces.length} 个工作区`}
        </span>
        <div className="flex gap-2.5">
          <button
            className="bg-transparent border-none text-blue-500 text-sm cursor-pointer px-2 py-1 hover:underline"
            onClick={() => setIsListCollapsed(!isListCollapsed)}
          >
            {isListCollapsed ? '展开列表' : '收起列表'}
          </button>
          {!isAdding && (
            <button
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-green-500 to-teal-600 text-white hover:shadow-lg hover:-translate-y-0.5 transition-all"
              onClick={() => {
                setFormData({ name: '', path: '' });
                setIsAdding(true);
              }}
            >
              + 添加
            </button>
          )}
        </div>
      </div>

      {!isListCollapsed && (
        <div className="max-h-[400px] overflow-y-auto pr-1">
          {isAdding && (
            <div className="bg-blue-50 p-4 rounded-lg border-2 border-blue-300 mb-3">
              <div className="grid gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    工作区名称（建议填写课程名称） <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleNameChange(e.target.value)}
                    placeholder="例如：计算机网络通识"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    工作区路径 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.path}
                    onChange={(e) => setFormData({ ...formData, path: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <div className="text-xs text-gray-600 mt-1">
                    💡 提示：会根据课程名自动补全相对路径，也可以使用绝对路径，建议使用默认值即可
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-200 text-gray-800 hover:bg-gray-300 transition-all"
                    onClick={handleCancel}
                  >
                    取消
                  </button>
                  <button
                    className="px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-green-500 to-teal-600 text-white hover:shadow-lg transition-all"
                    onClick={handleAdd}
                  >
                    保存
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="grid gap-2.5">
            {workspaces.length === 0 && !isAdding ? (
              <div className="text-center py-10 text-gray-500">暂无工作区配置，请先添加</div>
            ) : (
              workspaces.map((workspace, index) => (
                <div
                  key={workspace.name}
                  className="bg-gray-50 p-3 rounded-lg border-2 border-gray-200 hover:border-green-500 hover:shadow-md transition-all"
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <span className="inline-block px-2 py-0.5 bg-gradient-to-r from-green-500 to-teal-600 text-white rounded-xl text-xs font-medium">
                        #{index + 1}
                      </span>
                      <span className="font-semibold text-[15px] text-gray-800">{workspace.name}</span>
                    </div>
                    <button
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 transition-all"
                      onClick={() => handleDelete(workspace.name)}
                      title="删除"
                    >
                      🗑️
                    </button>
                  </div>
                  <div className="text-xs text-gray-500 mt-1.5">
                    <div title={workspace.path}>📁 {workspace.path}</div>
                    <div className="mt-0.5">
                      🕒 {new Date(workspace.created_at).toLocaleString('zh-CN')}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
