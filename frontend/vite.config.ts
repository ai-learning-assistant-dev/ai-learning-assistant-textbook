import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: '../templates',
        emptyOutDir: true,
    },
    server: {
        proxy: {
            // 课程库 API（与 curl 示例一致，默认 3000；需与主 Flask 端口区分时请改此处）
            '/api/courses': {
                target: 'http://localhost:3000',
                changeOrigin: true,
                secure: false,
            },
            '/api': {
                target: 'http://localhost:5000', // 后端服务地址，根据实际情况修改
                changeOrigin: true,
                secure: false,
            },
        },
    },
});

