<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { deleteThread, streamChatMessage } from '../api/chat'
import ChatInput from '../components/ChatInput.vue'
import ChatMessage from '../components/ChatMessage.vue'
import Sidebar from '../components/Sidebar.vue'
import SourcePanel from '../components/SourcePanel.vue'
import UploadPanel from '../components/UploadPanel.vue'

const STORAGE_KEY = 'astra-rag-sessions-v1'
const sessions = ref([])
const activeThreadId = ref('')
const isLoading = ref(false)
const deletingThreadId = ref('')
const deleteError = ref('')
const messageList = ref(null)

const activeSession = computed(() => sessions.value.find((item) => item.threadId === activeThreadId.value))
const activeSources = computed(() => {
  const messages = activeSession.value?.messages || []
  const latestAssistant = [...messages].reverse().find((message) => message.role === 'assistant')
  return latestAssistant?.sources || []
})

function createThreadId() {
  const id = globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(16).slice(2)}`
  return `session_${id}`
}

function currentTime() {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date())
}

function createSession() {
  const threadId = createThreadId()
  return {
    threadId,
    title: '新的知识咨询',
    createdAt: Date.now(),
    messages: [{
      id: `${threadId}_welcome`,
      role: 'assistant',
      content: '你好，我是 Astra 企业知识助手。你可以向我询问产品功能、企业政策或客户支持流程。',
      time: currentTime(),
      sources: [],
    }],
  }
}

function newSession() {
  if (isLoading.value) return
  const session = createSession()
  sessions.value.unshift(session)
  activeThreadId.value = session.threadId
}

function selectSession(threadId) {
  if (!isLoading.value) activeThreadId.value = threadId
}

async function removeSession(threadId) {
  if (isLoading.value || deletingThreadId.value) return

  deletingThreadId.value = threadId
  deleteError.value = ''

  try {
    await deleteThread(threadId)

    const deletingActiveSession = activeThreadId.value === threadId
    sessions.value = sessions.value.filter((session) => session.threadId !== threadId)

    if (deletingActiveSession) {
      if (sessions.value.length) {
        activeThreadId.value = sessions.value[0].threadId
      } else {
        newSession()
      }
    }
  } catch (error) {
    console.error('删除会话失败', error)
    deleteError.value = error instanceof Error ? error.message : '删除会话失败，请稍后重试。'
  } finally {
    deletingThreadId.value = ''
  }
}

async function sendMessage(content) {
  const session = activeSession.value
  if (!session || isLoading.value) return
  session.messages.push({
    id: `${session.threadId}_${Date.now()}_user`, role: 'user', content, time: currentTime(), sources: [],
  })
  if (session.title === '新的知识咨询') session.title = content.length > 18 ? `${content.slice(0, 18)}…` : content

  const loadingMessage = {
    id: `${session.threadId}_${Date.now()}_loading`, role: 'assistant', content: '', time: currentTime(), sources: [], loading: true,
  }
  session.messages.push(loadingMessage)
  isLoading.value = true

  const responseMessage = () => session.messages.find((message) => message.id === loadingMessage.id)

  try {
    await streamChatMessage(content, session.threadId, {
      onDelta(delta) {
        const target = responseMessage()
        if (!target) return
        target.content += delta
        target.loading = false
      },
      onSources(sources) {
        const target = responseMessage()
        if (target) target.sources = sources
      },
      onDone() {
        const target = responseMessage()
        if (target) target.loading = false
      },
    })

    const target = responseMessage()
    if (target && !target.content) target.content = '服务未返回回答内容。'
  } catch (error) {
    console.error('流式聊天请求失败', error)
    const target = responseMessage()
    if (target) {
      target.content = target.content || '当前无法完成回答，请稍后重试。'
      target.loading = false
    }
  } finally {
    isLoading.value = false
  }
}

async function scrollToLatest() {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}

function loadStoredSessions() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (stored?.sessions?.length && stored.activeThreadId) {
      sessions.value = stored.sessions
      activeThreadId.value = stored.activeThreadId
      return
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
  newSession()
}

watch([sessions, activeThreadId, isLoading], () => {
  if (!isLoading.value) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessions: sessions.value, activeThreadId: activeThreadId.value }))
  }
}, { deep: true })
watch(() => activeSession.value?.messages, scrollToLatest, { deep: true })
watch(activeThreadId, scrollToLatest)
onMounted(() => { loadStoredSessions(); scrollToLatest() })
</script>

<template>
  <main class="app-shell">
    <div v-if="deleteError" class="app-toast error" role="alert">{{ deleteError }}</div>
    <Sidebar
      :sessions="sessions"
      :active-thread-id="activeThreadId"
      :deleting-thread-id="deletingThreadId"
      :actions-disabled="isLoading"
      @new-session="newSession"
      @select-session="selectSession"
      @delete-session="removeSession"
    />
    <section class="chat-workspace">
      <header class="chat-header">
        <div><span class="eyebrow">ENTERPRISE KNOWLEDGE ASSISTANT</span><h1>{{ activeSession?.title || '新的知识咨询' }}</h1></div>
        <div class="header-status"><span class="status-dot"></span><div><strong>RAG READY</strong><small>FastAPI · SSE</small></div></div>
      </header>
      <div ref="messageList" class="message-list">
        <div class="conversation-intro"><span>SECURE KNOWLEDGE SESSION</span><i></i><small>{{ activeSession?.threadId }}</small></div>
        <ChatMessage v-for="message in activeSession?.messages || []" :key="message.id" :message="message" />
      </div>
      <ChatInput :disabled="isLoading" @send="sendMessage" />
    </section>
    <aside class="context-panel"><SourcePanel :sources="activeSources" /><UploadPanel /></aside>
  </main>
</template>
