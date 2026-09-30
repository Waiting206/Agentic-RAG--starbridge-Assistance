# Starbridge Agentic RAG

面向模拟 B2B SaaS 企业“星桥协作”的知识库助手。项目使用自建的产品、政策、版本公告和客服流程文档，完成知识入库、向量检索、Agent 问答、来源追溯、多轮会话和文件上传。

项目数据均为原创模拟内容，不包含真实企业或客户数据。

## 功能

- 加载 30 份带 YAML 元数据的 Markdown 企业知识文档
- 使用 RecursiveCharacterTextSplitter 切分文档
- 使用内容、页码和起始位置生成稳定 Chunk ID
- 使用 Embedding 模型和 Milvus 完成语义检索
- 由 LangGraph Agent 判断何时调用知识库工具
- 使用 SSE 向前端流式输出回答
- 在回答完成后展示文档来源和知识片段
- 根据文档 `audience` 元数据隔离客户资料与客服内部资料
- 客服角色使用服务端密钥授权，客户与客服会话分别保存
- 使用 PostgreSQL Checkpointer 保存多轮会话状态
- 支持新建、切换和删除会话
- 支持上传 PDF、TXT、Markdown 文件并增量写入 Milvus
- 使用 SHA-256 识别重复上传文件
- 使用 Vue 3 实现知识库聊天界面
- 使用 Docker Compose 部署前端、后端、PostgreSQL 和 Milvus
- 新环境首次启动时自动初始化内置知识库

## 系统架构

```mermaid
flowchart LR
    U[浏览器] --> N[Nginx]
    N --> V[Vue 3 静态页面]
    N -->|/api| F[FastAPI]
    F --> A[LangGraph Agent]
    A --> T[知识库检索工具]
    T --> E[Embedding]
    E --> M[(Milvus)]
    A --> P[(PostgreSQL Checkpointer)]
    F --> S[PDF / TXT / Markdown 上传]
    S --> C[解析与切分]
    C --> E
```

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、Vue Router、Axios |
| Web 服务 | Nginx |
| 后端 | FastAPI、Pydantic、SSE |
| Agent | LangChain、LangGraph |
| 大模型 | DeepSeek |
| Embedding | 智谱 Embedding API |
| 向量数据库 | Milvus |
| 会话持久化 | PostgreSQL、LangGraph Checkpointer |
| 部署 | Docker、Docker Compose |

## 项目结构

```text
.
├── app/
│   ├── api/
│   │   ├── chat.py               # 普通问答与 SSE 流式问答
│   │   ├── knowledge.py          # 知识文件上传接口
│   │   └── threads.py            # 会话删除接口
│   ├── agent/
│   │   ├── init_agent.py         # Agent 与 PostgreSQL Checkpointer
│   │   └── tools.py              # 知识库检索工具
│   ├── RAG/
│   │   ├── Loader.py             # 内置 Markdown 批量加载
│   │   ├── upload_loader.py      # 上传文件解析
│   │   ├── spiltter.py           # 文本切分
│   │   ├── retriever.py          # Milvus 检索
│   │   └── vector_store.py       # Embedding、稳定 ID 与向量写入
│   ├── bootstrap.py              # 空知识库首次初始化
│   ├── config.py
│   └── main.py
├── data/
│   ├── knowledge/                # 内置知识库与 60 道评测题
│   └── uploads/                  # 本地开发上传目录
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── nginx.conf
├── Dockerfile                    # FastAPI 镜像
├── compose.yaml
├── requirements.txt
└── .env.example
```

## Docker 一键部署

### 1. 准备配置

```bash
cp .env.example .env
```

至少填写：

```env
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=对应服务地址
ZHIPUAI_API_KEY=你的密钥
SUPPORT_ACCESS_TOKEN=随机长字符串
```

不要将真实 `.env` 提交到代码仓库。

### 2. 构建并启动

```bash
docker compose up -d --build
```

Compose 会依次：

1. 启动 PostgreSQL 和 Milvus。
2. 检查 Milvus 是否为空。
3. 首次部署时将内置知识文档写入 Milvus。
4. 启动 FastAPI。
5. 启动 Vue/Nginx 前端。

### 3. 访问

| 地址 | 用途 |
| --- | --- |
| http://localhost:5173 | 知识助手前端 |
| http://localhost:8000/docs | FastAPI 接口文档 |
| http://localhost:8000/health | 后端健康检查 |

### 4. 管理命令

```bash
# 查看状态
docker compose ps

# 查看日志
docker compose logs -f

# 停止并删除容器，保留数据
docker compose down

# 同时删除数据库和上传文件 Volume
docker compose down -v
```

PostgreSQL、Milvus 和上传文件均使用 Docker Volume 持久化。

## 本地开发

本地开发可以继续连接已经运行的 PostgreSQL 和 Milvus。

### 后端

```bash
conda create -n RAG-Agent python=3.12 -y
conda activate RAG-Agent
pip install -r requirements.txt
uvicorn app.main:app --reload
```

本地 `.env` 中使用：

```env
DB_URL=postgresql://postgres:123456@localhost:5432/rag_db
MILVUS_URI=http://localhost:19530
```

首次需要手动写入内置知识库时：

```bash
python -c "from app.main import ingest; ingest()"
```

### 前端

```bash
cd frontend
npm ci
```

创建 `frontend/.env.local`：

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

启动：

```bash
npm run dev
```

## API

### 普通回答

```http
POST /api/chat
Content-Type: application/json
```

```json
{
  "message": "企业版支持 SSO 吗？",
  "thread_id": "session_demo",
  "role": "customer"
}
```

`role`默认为`customer`。客户只能检索`audience`包含`customer`的文档。
客服请求使用`role: "support"`时，还必须提供请求头：

```http
X-Support-Token: 与 .env 中 SUPPORT_ACCESS_TOKEN 相同的值
```

客服密钥只保存在后端和内部评测环境中，不应写入Vue前端。相同的`thread_id`会按角色映射到不同的PostgreSQL会话，客户无法读取客服会话历史。

### 流式回答

```http
POST /api/chat/stream
```

SSE 事件包括：

- `message`：回答文字片段
- `sources`：检索来源
- `done`：回答结束
- `error`：生成失败

### 上传知识文件

```http
POST /api/knowledge/upload
Content-Type: multipart/form-data
```

支持 PDF、TXT、MD、Markdown，单文件最大 10 MB。

上传流程：

```text
文件校验
  → SHA-256 重复检查
  → 保存原文件
  → 解析为 Document
  → 文本切分
  → Embedding
  → Upsert Milvus
```

### 删除会话

```http
DELETE /api/threads/{thread_id}
```

## 知识库

内置知识库模拟一款企业项目管理产品，包含：

| 分类 | 数量 | 内容 |
| --- | ---: | --- |
| product | 12 | 产品功能、权限和操作 |
| support | 8 | 客服排查与处理流程 |
| policy | 6 | 套餐、额度和服务规则 |
| release | 4 | 更新公告和历史事件 |

Markdown 文档通过 YAML 保存 `doc_id`、标题、版本、状态、生效时间、访问身份和关联文档等信息。

## 评测数据

`data/knowledge/starbridge-rag-starter/evaluation/questions.jsonl` 包含 60 道标注题，覆盖：

- 事实问答
- 操作流程
- 跨文档问题
- 历史版本
- 访问控制
- 证据不足

评测程序位于 `evaluation/evaluate.py`。它会调用真实的 SSE 问答接口，记录完整回答、来源、首字延迟和总响应时间，并计算 Hit@5、Macro Recall@5、MRR 和完整来源召回率。

先用 5 道题检查链路：

```bash
python evaluation/evaluate.py --limit 5
```

运行全部 60 道题：

```bash
python evaluation/evaluate.py
```

也可以只运行一种题型：

```bash
python evaluation/evaluate.py --category fact
```

报告会写入 `evaluation/results/`，同时生成 JSON 和 CSV。CSV 中保留了 `expected_behavior` 和 `expected_points`，方便逐题检查答案。评测产生的临时会话默认会自动删除。

检索指标只统计带 `gold_doc_ids` 的题目。评测程序会按题目中的`role`调用客户或客服知识范围；客服题从本地`.env`读取`SUPPORT_ACCESS_TOKEN`。权限、历史时间和证据不足类问题仍需要人工判断回答行为，程序不会伪造这些题目的自动通过率。在得到真实运行结果前，不应在简历中填写虚构准确率。

## 当前限制

- 尚未实现账号登录和基于用户身份的完整RBAC；当前客服访问使用服务端共享密钥
- `audience`已经用于检索过滤；版本状态和生效日期尚未作为结构化过滤条件
- 当前检索以向量 Top K 为主，尚未增加重排序
- 尚未提供完整的自动化接口测试
- Redis 已列入依赖，但当前业务流程尚未使用

## 项目定位

这是一个面向学习、作品集和实习展示的全栈 Agentic RAG 项目，重点展示：

- 企业知识库的数据建模
- RAG 文档入库和来源追溯
- Agent 工具调用
- PostgreSQL 多轮会话持久化
- FastAPI 与 Vue 的前后端协作
- Docker Compose 可复现部署

它已经具备完整演示链路和基础访问边界，但仍需要真实账号认证、完整RBAC、版本过滤和更完整的测试体系才能达到生产系统要求。
