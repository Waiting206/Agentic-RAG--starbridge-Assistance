// 开发环境由 .env.local 指向本机 FastAPI；容器环境留空并通过 Nginx 同源代理。
export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
