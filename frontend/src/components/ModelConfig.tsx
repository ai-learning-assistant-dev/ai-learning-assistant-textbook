import { useState } from 'react';
import Alert from './Alert';
import ModelModal from './ModelModal';
import { Model, AlertProps } from '../types';

interface ModelConfigProps {
  models: Model[];
  onAddModel: (modelData: Omit<Model, 'id'>) => Promise<void>;
  onEditModel: (modelId: string, modelData: Omit<Model, 'id'>) => Promise<void>;
  onDeleteModel: (modelId: string) => Promise<void>;
  alert: AlertProps | null;
}

export default function ModelConfig({
  models,
  onAddModel,
  onEditModel,
  onDeleteModel,
  alert,
}: ModelConfigProps) {
  const [isListCollapsed, setIsListCollapsed] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<Model | null>(null);

  const handleAdd = () => {
    setEditingModel(null);
    setIsModalOpen(true);
  };

  const handleEdit = (modelId: string) => {
    const model = models.find((m) => m.id === modelId);
    setEditingModel(model || null);
    setIsModalOpen(true);
  };

  const handleDelete = async (modelId: string) => {
    if (window.confirm('确定要删除这个模型吗？')) {
      await onDeleteModel(modelId);
    }
  };

  const handleSave = async (formData: Omit<Model, 'id'>) => {
    if (editingModel) {
      await onEditModel(editingModel.id, formData);
    } else {
      await onAddModel(formData);
    }
    setIsModalOpen(false);
    setEditingModel(null);
  };

  const getApiDisplay = (apiBase: string): string => {
    return apiBase.replace(/^https?:\/\//, '').split('/')[0];
  };

  return (
    <div>
      <div className="flex items-center mb-4">
        <div className="w-1 h-5 bg-blue-500 rounded mr-2.5"></div>
        <h2 className="text-lg font-semibold text-gray-800">模型配置</h2>
      </div>

      {alert && <Alert {...alert} />}

      <div className="flex justify-between items-center mb-3">
        <span className="text-sm text-gray-600">
          {models.length === 0 ? '暂无模型' : `已配置 ${models.length} 个模型`}
        </span>
        <div className="flex gap-2.5">
          <button
            className="bg-transparent border-none text-blue-500 text-sm cursor-pointer px-2 py-1 hover:underline"
            onClick={() => setIsListCollapsed(!isListCollapsed)}
          >
            {isListCollapsed ? '展开列表' : '收起列表'}
          </button>
          <button
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:shadow-lg hover:-translate-y-0.5 transition-all"
            onClick={handleAdd}
          >
            + 添加
          </button>
        </div>
      </div>

      {!isListCollapsed && (
        <div className="max-h-[400px] overflow-y-auto pr-1">
          <div className="grid gap-2.5">
            {models.length === 0 ? (
              <div className="text-center py-10 text-gray-500">暂无模型配置，请先添加</div>
            ) : (
              models.map((model, index) => {
                const apiDisplay = getApiDisplay(model.api_base);
                return (
                  <div
                    key={model.id}
                    className="bg-gray-50 p-3 rounded-lg border-2 border-gray-200 hover:border-blue-500 hover:shadow-md transition-all"
                  >
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <span className="inline-block px-2 py-0.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-xl text-xs font-medium">
                          #{index + 1}
                        </span>
                        <span className="font-semibold text-[15px] text-gray-800">{model.name}</span>
                      </div>
                      <div className="flex gap-1.5">
                        <button
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-800 hover:bg-gray-200 transition-all"
                          onClick={() => handleEdit(model.id)}
                          title="编辑"
                        >
                          ✏️
                        </button>
                        <button
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 transition-all"
                          onClick={() => handleDelete(model.id)}
                          title="删除"
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1.5 flex items-center gap-2">
                      <span title={model.model_name}>{model.model_name}</span>
                      <span>•</span>
                      <span title={model.api_base}>{apiDisplay}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      <ModelModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingModel(null);
        }}
        onSave={handleSave}
        editingModel={editingModel}
      />
    </div>
  );
}

