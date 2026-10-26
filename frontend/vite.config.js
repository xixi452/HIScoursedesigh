import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 显式绑定 IPv4 回环：默认的 localhost 在 Windows 上会解析成 [::1]，
    // 导致 http://127.0.0.1:5173 打不开
    host: '127.0.0.1',
    port: 5173,
    // 端口被占用时直接报错，而不是悄悄换到 5174 让人找不到服务
    strictPort: true,
  },
})
