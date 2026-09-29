import { BASE_URL, USE_MOCK } from './config'

const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))

const mockAnswers = [
  {
    match: ['退款', '退费'],
    answer: '根据当前知识库，退款申请需要在规定时间内提交。提交后由支持团队核验订单状态与服务使用情况，并在审核通过后按原支付路径处理。',
    sources: [
      { source: 'refund_policy.pdf', chunk_id: 'chunk_001', text: '退款申请应在规定期限内提交，并提供订单信息。审核通过后，款项将按原支付路径退回。' },
      { source: 'support_process.md', chunk_id: 'chunk_014', text: '支持团队收到退款请求后，需要核验订单状态、账号信息以及对应服务的使用情况。' },
    ],
  },
  {
    match: ['企业版', 'sso', '单点登录'],
    answer: '企业版支持 SSO 单点登录与审计日志能力，适合需要统一身份管理和安全审计的组织使用。',
    sources: [
      { source: 'product_enterprise.md', chunk_id: 'chunk_023', text: '企业版包含团队版全部功能，并支持 SSO、成员统一管理以及最近 90 天审计日志。' },
    ],
  },
  {
    match: ['上传', '附件'],
    answer: '知识库支持 PDF、TXT 和 Markdown 文档。当前页面使用 Mock 上传，后续接入 FastAPI 后会将文件提交到 /knowledge/upload。',
    sources: [
      { source: 'knowledge_guide.md', chunk_id: 'chunk_032', text: '知识库允许录入结构化文本资料，并在索引完成后提供语义检索和来源追溯。' },
    ],
  },
]

export async function mockChat(message, threadId) {
  await wait(650 + Math.floor(Math.random() * 300))
  const normalized = message.toLowerCase()
  const matched = mockAnswers.find((item) => item.match.some((key) => normalized.includes(key.toLowerCase())))

  if (matched) return { answer: matched.answer, sources: matched.sources, thread_id: threadId }

  return {
    answer: '我已基于当前模拟知识库完成检索。真实后端接入后，这里会综合 Milvus 检索结果，由 Agent 生成带来源依据的回答。',
    sources: [{
      source: 'enterprise_knowledge_base.md',
      chunk_id: 'chunk_mock_001',
      text: `与“${message.slice(0, 28)}${message.length > 28 ? '…' : ''}”相关的模拟知识片段。`,
    }],
    thread_id: threadId,
  }
}

export async function streamChatMessage(message, threadId, { onDelta, onSources, onDone } = {}) {
  if (USE_MOCK) {
    const result = await mockChat(message, threadId)
    onDelta?.(result.answer)
    onSources?.(result.sources || [])
    onDone?.(result)
    return result
  }

  const response = await fetch(`${BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `聊天请求失败：${response.status}`)
  }
  if (!response.body) throw new Error('当前浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let answer = ''
  let sources = []
  let completed = false

  const handleEvent = (block) => {
    if (!block.trim()) return

    let event = 'message'
    const dataLines = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    }
    if (!dataLines.length) return

    const payload = JSON.parse(dataLines.join('\n'))
    if (event === 'message' && typeof payload.delta === 'string') {
      answer += payload.delta
      onDelta?.(payload.delta)
    } else if (event === 'sources') {
      sources = Array.isArray(payload.sources) ? payload.sources : []
      onSources?.(sources)
    } else if (event === 'done') {
      completed = true
      onDone?.(payload)
    } else if (event === 'error') {
      throw new Error(payload.detail || '流式回答生成失败')
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      handleEvent(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')
    }

    if (done) break
  }

  if (buffer.trim()) handleEvent(buffer)
  if (!completed) throw new Error('流式连接提前结束')

  return { answer, thread_id: threadId, sources }
}

export async function deleteThread(threadId) {
  if (USE_MOCK) return

  const response = await fetch(
    `${BASE_URL}/api/threads/${encodeURIComponent(threadId)}`,
    { method: 'DELETE' },
  )

  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(error?.detail || `删除会话失败：${response.status}`)
  }
}
