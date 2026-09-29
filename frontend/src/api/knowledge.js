import axios from 'axios'
import { BASE_URL, USE_MOCK } from './config'

const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))

export async function uploadKnowledge(file) {
  if (USE_MOCK) {
    await wait(700)
    return { filename: file.name, status: 'success', message: '文件已进入模拟知识库处理队列' }
  }

  const formData = new FormData()
  formData.append('file', file)

  const { data } = await axios.post(
    `${BASE_URL}/api/knowledge/upload`,
    formData,
    { timeout: 120_000 },
  )
  return data
}
