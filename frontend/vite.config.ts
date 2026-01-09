import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:5000', // 后端服务地址，根据实际情况修改
                changeOrigin: true,
                secure: false,
            },
        },
    },
});

