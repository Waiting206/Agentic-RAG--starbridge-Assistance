<script setup>
import { nextTick, ref } from 'vue'

const props = defineProps({ disabled: { type: Boolean, default: false } })
const emit = defineEmits(['send'])
const content = ref('')
const textarea = ref(null)

function resizeTextarea() {
  const element = textarea.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 160)}px`
}

function submit() {
  const message = content.value.trim()
  if (!message || props.disabled) return
  emit('send', message)
  content.value = ''
  nextTick(resizeTextarea)
}

function handleKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="composer-shell">
    <div class="composer" :class="{ disabled }">
      <textarea
        ref="textarea"
        v-model="content"
        rows="1"
        placeholder="询问产品、政策或支持流程…"
        aria-label="聊天消息"
        :disabled="disabled"
        @input="resizeTextarea"
        @keydown="handleKeydown"
      ></textarea>
      <button type="button" class="send-button" :disabled="disabled || !content.trim()" aria-label="发送消息" @click="submit">
        <svg viewBox="0 0 24 24" fill="none"><path d="m5 12 14-7-4.5 14-3-5.5L5 12Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="m11.5 13.5 3-3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
      </button>
    </div>
    <div class="composer-help"><span>Enter 发送 · Shift + Enter 换行</span><span>回答由模拟知识库生成</span></div>
  </div>
</template>
