import { useState, useEffect, FormEvent } from 'react';
import { Model } from '../types';

interface ModelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (formData: Omit<Model, 'id'>) => Promise<void>;
  editingModel: Model | null;
}

interface ModelFormData {
  name: string;
  model_name: string;
  api_base: string;
  api_key: string;
}

export default function ModelModal({ isOpen, onClose, onSave, editingModel }: ModelModalProps) {
  const [formData, setFormData] = useState<ModelFormData>({
    name: '',
    model_name: '',
    api_base: '',
    api_key: '',
  });

  useEffect(() => {
    if (editingModel) {
      setFormData({
        name: editingModel.name || '',
        model_name: editingModel.model_name || '',
        api_base: editingModel.api_base || '',
        api_key: editingModel.api_key || '',
      });
    } else {
      setFormData({
        name: '',
        model_name: '',
        api_base: '',
        api_key: '',
      });
    }
  }, [editingModel, isOpen]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    await onSave(formData);
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 z-[1000] flex items-center justify-center"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white p-8 rounded-xl max-w-[500px] w-[90%] max-h-[80vh] overflow-y-auto">
        <h2 className="text-xl font-semibold mb-5">
          {editingModel ? '编辑模型' : '添加模型'}
        </h2>

        <form onSubmit={handleSubmit}>
          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              模型名称
              <span className="text-gray-500 font-normal text-xs ml-1">
                （自定义，方便识别）
              </span>
            </label>
            <input
              type="text"
              className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="例如: DeepSeek-V3 或 通义千问"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              模型标识
              <span className="text-gray-500 font-normal text-xs ml-1">
                （服务商提供的model参数）
              </span>
            </label>
            <input
              type="text"
              className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="例如: deepseek-ai/DeepSeek-V3"
              value={formData.model_name}
              onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
              required
            />
          </div>

          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              API地址
              <span className="text-gray-500 font-normal text-xs ml-1">
                （完整的base URL）
              </span>
            </label>
            <input
              type="text"
              className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="例如: https://api.siliconflow.cn/v1"
              value={formData.api_base}
              onChange={(e) => setFormData({ ...formData, api_base: e.target.value })}
              required
            />
          </div>

          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              API密钥
            </label>
            <input
              type="password"
              className="w-full p-3 border-2 border-gray-200 rounded-lg text-sm transition-all focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder={editingModel ? '不修改请保持原值' : 'sk-xxxxx'}
              value={formData.api_key}
              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
              required
            />
            <div className="text-xs text-gray-500 mt-1">
              请妥善保管，不要泄露给他人
            </div>
          </div>

          <div className="flex gap-2.5 justify-end mt-5">
            <button
              type="button"
              className="px-6 py-3 rounded-lg text-sm font-medium bg-gray-100 text-gray-800 hover:bg-gray-200 transition-all"
              onClick={onClose}
            >
              取消
            </button>
            <button
              type="submit"
              className="px-6 py-3 rounded-lg text-sm font-medium bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:shadow-lg hover:-translate-y-0.5 transition-all"
            >
              保存
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

