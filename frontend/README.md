# Bilibili视频字幕下载与总结 - 前端项目

## 项目说明

这是一个使用 React + Vite + Tailwind CSS 构建的前端项目，用于管理 Bilibili 视频字幕下载和AI总结任务。

## 开发环境设置

### 1. 安装依赖

```bash
npm install
```

### 2. 配置后端API地址

项目默认将 `/api` 请求代理到 `http://localhost:5000`。

如果你的后端服务运行在不同的端口，请修改 `vite.config.js` 中的代理配置：

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:你的后端端口', // 例如: 8000, 3000 等
      changeOrigin: true,
      secure: false,
    }
  }
}
```

### 3. 启动开发服务器

```bash
npm run dev
```

### 4. 确保后端服务已启动

在启动前端之前，请确保后端API服务已经运行。如果后端未启动，前端会显示错误提示。

## 常见问题

### 错误：`Unexpected token '<', "<!DOCTYPE "... is not valid JSON`

这个错误通常表示：
1. **后端服务未启动** - 请确保后端API服务正在运行
2. **API路径配置错误** - 检查 `vite.config.js` 中的代理配置是否正确
3. **后端端口不匹配** - 确认后端服务运行的端口与代理配置中的端口一致

### 如何检查后端服务是否运行？

在浏览器中直接访问 `http://localhost:你的后端端口/api/models`，如果返回JSON数据，说明后端正常运行。

## 构建生产版本

```bash
npm run build
```

## 预览生产构建

```bash
npm run preview
```
