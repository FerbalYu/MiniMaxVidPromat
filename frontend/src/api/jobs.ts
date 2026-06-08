import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail
      if (typeof detail === 'string') {
        return Promise.reject(new Error(detail))
      }
      return Promise.reject(new Error(error.message || '请求失败'))
    }
    return Promise.reject(error)
  },
)

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type PromptMode = 'standard' | 'cinematic' | 'product' | 'short_drama'

export interface PromptResult {
  summary: string
  subject: string
  scene: string
  action: string
  camera: string
  lighting: string
  style: string
  seedance_prompt: string
  storyboard_prompt: string
  negative_prompt: string
  english_prompt: string
  raw_text: string
}

export interface JobRecord {
  id: string
  status: JobStatus
  filename: string
  size_bytes: number
  prompt_mode: PromptMode
  language: string
  progress: number
  message: string
  result: PromptResult | null
  error: string | null
  created_at: number
  updated_at: number
  meta: Record<string, unknown>
}

export async function createJob(file: File, promptMode: PromptMode, language: string) {
  const formData = new FormData()
  formData.append('video', file)
  formData.append('prompt_mode', promptMode)
  formData.append('language', language)
  const { data } = await apiClient.post<{ job_id: string; status: JobStatus }>('/api/jobs', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getJob(jobId: string) {
  const { data } = await apiClient.get<JobRecord>(`/api/jobs/${jobId}`)
  return data
}
