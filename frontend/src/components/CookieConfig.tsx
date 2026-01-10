import { useState, useEffect } from 'react';
import Alert from './Alert';
import { AlertProps, CookiesConfigResponse } from '../types';

interface CookieConfigProps {
  alert: AlertProps | null;
}

export default function CookieConfig({ alert }: CookieConfigProps) {
  const [sessdata, setSessdata] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isConfigured, setIsConfigured] = useState(false);
  const [hasValue, setHasValue] = useState(false); // 是否有已保存的值
  const [showInput, setShowInput] = useState(false); // 是否显示输入框
  const [cookieAlert, setCookieAlert] = useState<AlertProps | null>(null);

  // 加载现有的Cookie配置
  useEffect(() => {
    loadCookieConfig();
  }, []);

  const loadCookieConfig = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/config/cookies');
      
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
      }
      
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        throw new Error('服务器返回的不是JSON格式');
      }
      
      const data: CookiesConfigResponse = await response.json();
      
      if (data.success) {
        setIsConfigured(data.configured);
        setHasValue(!!data.has_value); // 设置是否有已保存值的状态
        if (data.has_value) {
          // 不直接显示实际的SESSDATA值，而是显示占位符或提示信息
          setSessdata('••••••••••••••••••••••••••••••••'); // 显示星号占位符
        }
      } else {
        setCookieAlert({ message: '加载Cookie配置失败: ' + (data.error || '未知错误'), type: 'error' });
      }
    } catch (error) {
      console.error('加载Cookie配置失败:', error);
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setCookieAlert({ message: '加载Cookie配置失败: ' + errorMessage, type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    // 如果当前显示的是占位符，需要用户输入新值
    if (sessdata === '••••••••••••••••••••••••••••••••') {
      setCookieAlert({ message: '请先点击"修改配置"输入新的SESSDATA值', type: 'warning' });
      return;
    }

    if (!sessdata.trim()) {
      setCookieAlert({ message: '请输入SESSDATA值', type: 'error' });
      return;
    }

    if (sessdata === '••••••••••••••••••••••••••••••••') {
      setCookieAlert({ message: '请输入有效的SESSDATA值，而不是占位符', type: 'error' });
      return;
    }

    try {
      // 发送请求更新配置文件
      const response = await fetch('/api/config/cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessdata: sessdata.trim() }),
      });

      const data = await response.json();

      if (data.success) {
        setCookieAlert({ message: 'Cookie配置保存成功', type: 'success' });
        setIsConfigured(true);
        setHasValue(true);
        // 保存成功后，显示占位符而非明文
        setSessdata('••••••••••••••••••••••••••••••••');
        setShowInput(false); // 保存后隐藏输入框
        setTimeout(() => setCookieAlert(null), 3000);
      } else {
        setCookieAlert({ message: '保存失败: ' + (data.error || '未知错误'), type: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setCookieAlert({ message: '保存失败: ' + errorMessage, type: 'error' });
    }
  };

  const handleTest = async () => {
    let testData = sessdata;
    
    // 如果显示的是占位符，需要获取实际的值进行测试
    if (sessdata === '••••••••••••••••••••••••••••••••') {
      // 对于测试，我们不能直接发送占位符，需要向后端发送测试请求而不暴露具体值
      // 这里我们发送一个特殊请求，后端会从配置文件读取实际值进行测试
      testData = 'PLACEHOLDER_VALUE_FOR_TEST'; // 特殊标记，后端识别此标记从配置文件读取值
    }

    try {
      const response = await fetch('/api/test_cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessdata: testData }),
      });

      const data = await response.json();

      if (data.success) {
        setCookieAlert({ message: 'Cookie测试成功: ' + data.message, type: 'success' });
      } else {
        setCookieAlert({ message: 'Cookie测试失败: ' + (data.error || '验证不通过'), type: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      setCookieAlert({ message: '测试连接失败: ' + errorMessage, type: 'error' });
    }
  };

  const handleModifyClick = () => {
    setShowInput(true);
    setSessdata(''); // 清空占位符，让用户输入新值
  };

  const handleCancel = () => {
    // 取消编辑时，恢复到显示占位符状态
    setShowInput(false);
    if (hasValue) {
      setSessdata('••••••••••••••••••••••••••••••••');
    } else {
      setSessdata('');
    }
  };

  return (
    <div>
      <div className="flex items-center mb-4">
        <div className="w-1 h-5 bg-green-500 rounded mr-2.5"></div>
        <h2 className="text-lg font-semibold text-gray-800">Cookie配置</h2>
      </div>
      <div className="mb-3">
        <h3 className="text-xs text-gray-600 mt-1">
          🍪 配置Bilibili登录Cookie，用于下载AI生成的字幕
        </h3>
      </div>

      {(alert || cookieAlert) && <Alert {...(cookieAlert || alert!)} />}

      <div className="space-y-4">
        {showInput ? (
          // 编辑模式：显示输入框
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                SESSDATA <span className="text-red-500">*</span>
              </label>
              <textarea
                value={sessdata}
                onChange={(e) => setSessdata(e.target.value)}
                placeholder="在此处粘贴您的SESSDATA值"
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              <div className="text-xs text-gray-600 mt-1">
                💡 获取方法：登录bilibili.com → F12开发者工具 → Application → Cookie → SESSDATA
              </div>
            </div>

            <div className="flex gap-2.5 pt-2">
              <button
                className="px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-green-500 to-teal-600 text-white hover:shadow-lg transition-all disabled:opacity-50"
                onClick={handleSave}
                disabled={isLoading}
              >
                {isLoading ? '保存中...' : '保存配置'}
              </button>
              <button
                className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-500 text-white hover:bg-gray-600 transition-all disabled:opacity-50"
                onClick={handleCancel}
                disabled={isLoading}
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          // 显示模式：显示状态和操作按钮
          <div className="space-y-4">
            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
              <div className="flex justify-between items-start">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center mb-2">
                    <span className="text-sm font-medium text-gray-700 mr-2">当前状态:</span>
                    {isConfigured ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        已配置
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                        未配置
                      </span>
                    )}
                  </div>
                  
                  <div className="text-sm text-gray-600 break-all">
                    {hasValue 
                      ? 'SESSDATA: ••••••••••••••••••••••••••••••••' 
                      : '尚未配置SESSDATA'}
                  </div>
                </div>
                
                <div className="flex flex-col gap-2 ml-4">
                  <button
                    className="px-3 py-1 rounded-lg text-xs font-medium bg-blue-500 text-white hover:bg-blue-600 transition-all"
                    onClick={handleTest}
                    disabled={isLoading || !hasValue}
                  >
                    测试
                  </button>
                  <button
                    className="px-3 py-1 rounded-lg text-xs font-medium bg-gradient-to-r from-green-500 to-teal-600 text-white hover:shadow-lg transition-all"
                    onClick={handleModifyClick}
                  >
                    {hasValue ? '修改' : '设置'}
                  </button>
                </div>
              </div>
            </div>

            <div className="text-xs text-gray-600">
              💡 获取方法：登录bilibili.com → F12开发者工具 → Application → Cookie → SESSDATA
            </div>
          </div>
        )}

        {isConfigured && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
              </svg>
              <span className="text-green-700 font-medium">Cookie已配置</span>
            </div>
            <p className="text-green-600 text-sm mt-1">
              您的Bilibili Cookie 已正确配置，可以下载AI字幕
            </p>
          </div>
        )}
      </div>
    </div>
  );
}