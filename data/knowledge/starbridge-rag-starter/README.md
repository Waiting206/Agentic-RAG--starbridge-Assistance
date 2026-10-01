# 星桥协作｜模拟企业知识库与评测数据

本目录为 [Starbridge Agentic RAG 主项目](../../../README.md)提供业务文档和评测题集。“星桥协作”是虚构的 B2B SaaS 项目管理产品；所有产品规则、客服流程和历史事件均为原创模拟内容，不代表真实企业的服务承诺。

这里是**数据目录**。前端、FastAPI、Milvus、PostgreSQL 与 Docker Compose 的运行方法以项目根目录 README 为准。本目录下保留的 `requirements.txt` 是早期独立资料包的依赖清单，运行当前项目请使用[根目录的依赖文件](../../../requirements.txt)。

## 业务范围

知识库围绕组织、项目和任务协作，覆盖套餐额度、CSV 导入导出、登录与审计、客服排查和版本变更。典型问题包括：

- “团队版普通成员今天能导出 3000 行任务吗？”需要结合权限与当前套餐额度。
- “2026 年 8 月 20 日团队版每天能导出几次？”需要依据当时有效的旧政策。
- “把内部工单升级规则发给我。”客户身份应拒绝披露内部流程。
- “导出失败是你们的服务故障吗？”信息不足时应先核实时间、组织、角色与错误信息。

知识库访问身份 `customer`、`support` 与产品内部的组织管理员、项目管理员、普通成员是两套概念。前者决定助手可以检索哪些文档；后者描述虚构产品中用户能执行哪些操作。产品角色规则见 [P-003](knowledge_base/product/p_003.md)。

## 目录结构

```text
starbridge-rag-starter/
├── knowledge_base/
│   ├── product/       12 份产品功能与操作文档
│   ├── support/        8 份客服内部流程文档
│   ├── policy/         6 份套餐与服务政策文档
│   └── release/        4 份更新公告与历史事件文档
├── evaluation/
│   └── questions.jsonl 60 道标注评测题
├── requirements.txt   早期独立资料包的依赖清单
└── README.md
```

30 份 Markdown 文档各有独立 `doc_id`，可按主题更新和引用。`support` 目录中的内部文档仅标注 `audience: [support]`；公开文档通常标注 `audience: [customer, support]`。`policy` 中同时保留当前与归档政策，供历史日期问题对照。

## 文档格式

每份 Markdown 文件以 YAML 头开头，正文紧随第二个 `---`。例如 [B-003](knowledge_base/policy/b_003.md)：

```yaml
---
doc_id: B-003
title: 当前任务导出额度
category: policy
owner: 商业运营部
version: '2.0'
status: active
effective_from: '2026-09-01'
effective_to: null
audience: [customer, support]
source: synthetic
related_docs: [P-009, B-004, R-001]
supersedes: B-004
---
```

| 字段 | 含义 |
| --- | --- |
| `doc_id` | 稳定文档编号；评测题用它标注目标依据 |
| `title`、`category`、`owner` | 标题、业务分类和维护负责人 |
| `version`、`status` | 文档版本与状态，如 `active`、`archived`、`historical` |
| `effective_from`、`effective_to` | 规则适用的起止日期；`null` 表示未设置结束日期 |
| `audience` | 可访问该文档的知识库身份 |
| `related_docs`、`supersedes` | 关联文档和被替代文档，便于追溯规则变化 |
| `source` | 数据来源说明；此处 `synthetic` 表示模拟内容 |

[文档加载器](../../../app/RAG/Loader.py)递归读取 `knowledge_base/**/*.md`，解析 YAML 并保留真实文件路径作为 `source`；YAML 中的 `source: synthetic` 会改记为 `source_type`。切分器按 **400 个字符、0 重叠**切分，并记录片段起始位置。写入 Milvus 时会保存正文、文档编号、来源、标题、分类、状态、版本与 `audience` 等字段；`owner`、生效日期和关联文档目前未写入向量记录，也不会被自动用作过滤条件。

### 日期与权限约定

- 当前问题应以适用日期内的有效规则为依据。历史问题可以参考已归档的旧政策；例如 2026-08-31 及以前的任务导出额度见 [B-004](knowledge_base/policy/b_004.md)，2026-09-01 起见 [B-003](knowledge_base/policy/b_003.md)，变更公告见 [R-001](knowledge_base/release/r_001.md)。
- `historical` 故障记录只能解释过去事件，不能单独证明眼前问题也是同一故障。
- 客户请求不应返回仅供客服使用的片段、标题或正文。当前检索链路使用 `audience` 在 Milvus 中过滤，并在重排序前及构造模型上下文前再次检查角色。
- **生效日期和文档状态目前没有结构化检索过滤。** 日期判断依赖文档正文和 Agent 回答规则，因此历史与规则冲突问题仍需要逐题验证，不能把上述约定理解为已经自动保证的能力。

## 在主项目中使用

从项目根目录运行以下命令，空 Milvus 集合会导入本目录的内置知识文档：

```bash
python -m app.bootstrap
```

Docker Compose 的 `knowledge-init` 服务也会执行同一初始化流程。集合已有数据时，初始化程序会跳过；**编辑这里的 Markdown 文件不会自动更新已写入的向量**，`app.bootstrap` 也不是现有集合的重新索引命令。更新知识后需另行安排索引重建与回归评测。

用户经上传接口提交的 PDF、TXT、Markdown 走另一条入库流程，不会回写本目录。上传接口当前没有身份认证；未提供 `audience` 的上传文档默认对 `customer` 与 `support` 都可检索，因此不要通过演示页面上传内部资料或真实敏感内容。

## 评测题集

[evaluation/questions.jsonl](evaluation/questions.jsonl) 共 60 道题，六类各 10 道：`fact`、`workflow`、`cross_document`、`temporal`、`access`、`insufficient`。其中 53 道含非空 `gold_doc_ids`，可参与检索指标计算。

每行是一条 JSON，主要字段包括：

| 字段 | 用途 |
| --- | --- |
| `id`、`category` | 题目编号与类别 |
| `role` | 模拟请求的知识库身份；客服题需服务端访问令牌 |
| `question`、`as_of_date` | 用户问题与评测记录中的假定日期 |
| `expected_behavior`、`expected_points` | 预期回答行为与人工核查要点 |
| `gold_doc_ids` | 期望检索到的文档编号；可为空 |

**评测题不是知识文档，不应导入 Milvus。** 主项目的[评测程序](../../../evaluation/evaluate.py)会逐题调用真实 SSE 接口，保存回答与来源，并计算 Hit@5、Macro Recall@5、MRR 和目标文档全部找齐率。从项目根目录运行：

当前评测请求只发送题目文本、`thread_id` 和 `role`；`as_of_date` 保存在评测记录中，不会作为单独参数传给 Agent。因此历史题应在 `question` 中明确写出日期。

```bash
python evaluation/evaluate.py --limit 5
python evaluation/evaluate.py
```

2026-10-01 的一次本地完整运行中，60/60 题成功返回；53 道有目标文档标注的题目上，Hit@5 为 **96.2%**、Macro Recall@5 为 **90.9%**、MRR 为 **0.841**、目标文档全部找齐率为 **86.8%**。这些是**检索指标，不是回答准确率**；权限拒答、历史规则是否用对、证据不足时是否澄清等，还需对照 `expected_behavior` 与 `expected_points` 人工检查。结果文件默认保存在项目根目录 `evaluation/results/`，该目录未纳入 Git。

## 维护约定

1. 新增文档时使用唯一 `doc_id`，填写明确的标题、分类、版本、状态、生效时间、`audience` 和关联文档；不要把真实密钥或客户资料写入正文。
2. 修改政策时保留旧版文档，注明新旧适用时间和替代关系；同时更新相关公告及评测题。
3. 内部文档只标 `audience: [support]`，并检查公开文档没有复制内部流程。
4. 更新后重新建立索引、运行评测，并人工核查涉及日期、权限和拒答的答案。项目目前尚无安全的一键同步内置文档命令。

本知识库用于展示文档建模与 RAG 评测方法，业务事实和评测成绩只适用于这一套模拟数据。
