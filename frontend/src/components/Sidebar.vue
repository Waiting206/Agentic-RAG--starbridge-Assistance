<script setup>
defineProps({
  sessions: { type: Array, required: true },
  activeThreadId: { type: String, required: true },
  deletingThreadId: { type: String, default: '' },
  actionsDisabled: { type: Boolean, default: false },
})
const emit = defineEmits(['new-session', 'select-session', 'delete-session'])
const shortId = (id) => id.replace('session_', '').slice(0, 8)

function requestDelete(session) {
  const confirmed = window.confirm(`确定删除“${session.title}”吗？删除后无法恢复该会话记忆。`)
  if (confirmed) emit('delete-session', session.threadId)
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
      <div><strong>ASTRA KNOWLEDGE</strong><small>Agentic RAG Console</small></div>
    </div>

    <button class="new-chat-button" type="button" :disabled="actionsDisabled" @click="$emit('new-session')">
      <span class="plus-icon">+</span>新建会话<span class="button-hint">⌘ K</span>
    </button>

    <div class="session-section">
      <div class="section-label"><span>最近会话</span><span>{{ sessions.length }}</span></div>
      <nav class="session-list" aria-label="历史会话">
        <div v-for="session in sessions" :key="session.threadId" class="session-row">
          <button
            type="button"
            class="session-item"
            :class="{ active: session.threadId === activeThreadId }"
            :disabled="actionsDisabled"
            @click="$emit('select-session', session.threadId)"
          >
            <span class="session-indicator"></span>
            <span class="session-content">
              <strong>{{ session.title }}</strong>
              <small>{{ shortId(session.threadId) }} · {{ session.messages.length }} 条消息</small>
            </span>
          </button>
          <button
            type="button"
            class="session-delete"
            :class="{ deleting: deletingThreadId === session.threadId }"
            :disabled="actionsDisabled || Boolean(deletingThreadId)"
            :aria-label="`删除会话：${session.title}`"
            :title="deletingThreadId === session.threadId ? '正在删除' : '删除会话'"
            @click.stop="requestDelete(session)"
          >
            <span v-if="deletingThreadId === session.threadId" class="delete-spinner" aria-hidden="true"></span>
            <svg v-else viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 7h14M9 7V4.5h6V7m-8 0 1 13h8l1-13M10 10.5v6M14 10.5v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </nav>
    </div>

    <div class="sidebar-footer">
      <div class="version-tag">DEV · v0.1</div>
    </div>
  </aside>
</template>
