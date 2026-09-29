<script setup>
import { ref } from 'vue'
import { uploadKnowledge } from '../api/knowledge'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const selectedFile = ref(null)
const status = ref('idle')
const statusMessage = ref('')
const input = ref(null)
const acceptedExtensions = ['pdf', 'txt', 'md', 'markdown']

function chooseFile() {
  input.value?.click()
}

function uploadErrorMessage(error) {
  if (error?.code === 'ECONNABORTED') return '处理超时，请稍后重试'
  if (error?.code === 'ERR_NETWORK') return '无法连接后端服务，请检查服务是否已经启动'
  return error?.response?.data?.detail || error?.message || '上传失败，请稍后重试'
}

async function handleFile(event) {
  const file = event.target.files?.[0]
  if (!file) return

  const extension = file.name.split('.').pop()?.toLowerCase()
  selectedFile.value = file

  if (!acceptedExtensions.includes(extension)) {
    status.value = 'error'
    statusMessage.value = '仅支持 PDF、TXT 和 Markdown 文件'
    event.target.value = ''
    return
  }

  if (file.size > MAX_FILE_SIZE) {
    status.value = 'error'
    statusMessage.value = '文件不能超过 10 MB'
    event.target.value = ''
    return
  }

  status.value = 'uploading'
  statusMessage.value = '正在解析并写入知识库…'

  try {
    const result = await uploadKnowledge(file)
    status.value = 'success'
    statusMessage.value = result.message
  } catch (error) {
    status.value = 'error'
    statusMessage.value = uploadErrorMessage(error)
  } finally {
    event.target.value = ''
  }
}
</script>

<template>
  <section class="upload-section">
    <header class="panel-heading compact"><div><span class="eyebrow">KNOWLEDGE INGESTION</span><h2>添加知识</h2></div></header>
    <input ref="input" type="file" accept=".pdf,.txt,.md,.markdown" hidden @change="handleFile" />
    <div v-if="selectedFile" class="upload-result" :class="status" role="status" aria-live="polite">
      <div class="file-icon">{{ selectedFile.name.split('.').pop()?.toUpperCase() }}</div>
      <div><strong>{{ selectedFile.name }}</strong><small>{{ statusMessage }}</small></div>
      <span class="result-mark">{{ status === 'success' ? '✓' : status === 'error' ? '!' : '···' }}</span>
    </div>
    <button class="upload-dropzone" type="button" :disabled="status === 'uploading'" @click="chooseFile">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 16V5m0 0L8 9m4-4 4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 14v4.5h14V14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      <span>{{ status === 'uploading' ? '处理中…' : '选择知识文件' }}</span><small>PDF · TXT · MARKDOWN · 最大 10 MB</small>
    </button>
  </section>
</template>
