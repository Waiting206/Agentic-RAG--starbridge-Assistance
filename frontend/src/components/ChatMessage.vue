<script setup>
defineProps({ message: { type: Object, required: true } })
</script>

<template>
  <article class="message-row" :class="`message-${message.role}`">
    <div class="message-avatar" aria-hidden="true">
      <svg v-if="message.role === 'assistant'" viewBox="0 0 24 24" fill="none">
        <path d="M12 3.5 14.2 9l5.3 2.2-5.3 2.2L12 19l-2.2-5.6-5.3-2.2L9.8 9 12 3.5Z" stroke="currentColor" stroke-width="1.5"/>
      </svg>
      <svg v-else viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="8" r="3.5" stroke="currentColor" stroke-width="1.5"/>
        <path d="M5.5 20c.7-4 3-6 6.5-6s5.8 2 6.5 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="message-content">
      <div class="message-meta">
        <strong>{{ message.role === 'assistant' ? 'ASTRA AGENT' : 'YOU' }}</strong><span>{{ message.time }}</span>
      </div>
      <div v-if="message.loading" class="typing-indicator" aria-label="AI 正在思考">
        <span></span><span></span><span></span><em>正在检索企业知识库</em>
      </div>
      <p v-else class="message-text">{{ message.content }}</p>
      <div v-if="message.sources?.length" class="message-source-count">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M7 4.5h8l3 3V20H7V4.5Z" stroke="currentColor" stroke-width="1.5"/>
          <path d="M15 4.5V8h3M10 12h5M10 15.5h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        {{ message.sources.length }} 个知识来源
      </div>
    </div>
  </article>
</template>
