# Starbridge RAG Frontend

Starbridge Agentic RAG 的 Vue 3 前端，提供多会话聊天、SSE 流式回答、检索来源展示、会话删除和知识文件上传。

完整项目说明见上级目录的 [README](../README.md)。

## 本地开发

```bash
npm ci
npm run dev
```

创建 `.env.local`：

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

默认访问 http://localhost:5173。

## 生产构建

```bash
npm run build
```

Docker 部署采用多阶段构建：Node.js 负责生成 `dist/`，Nginx 负责提供静态页面，并将 `/api/` 请求转发给 FastAPI。

Mock 代码仍保留用于无后端界面演示，通过 `VITE_USE_MOCK=true` 才会启用；默认 Docker 部署连接真实后端。
