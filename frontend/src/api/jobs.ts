import axios from 'axios'
import type { AxiosProgressEvent } from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const message = formatApiError(error.response?.data?.detail) || error.message || '请求失败'
      return Promise.reject(new Error(message))
    }
    return Promise.reject(error)
  },
)

function formatApiError(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'msg' in item) return String(item.msg)
        return ''
      })
      .filter(Boolean)
      .join('；')
  }
  if (detail && typeof detail === 'object' && 'msg' in detail) {
    return String(detail.msg)
  }
  return ''
}

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'canceled'
export type PromptMode = 'standard' | 'cinematic' | 'product' | 'short_drama'

export interface HealthInfo {
  ok: boolean
  model: string
  files_api_enabled: boolean
  max_upload_mb: number
  max_concurrent_jobs: number
  job_retention_hours: number
}

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

export async function getHealth() {
  const { data } = await apiClient.get<HealthInfo>('/api/health')
  return data
}

export async function createJob(
  file: File,
  promptMode: PromptMode,
  language: string,
  onUploadProgress?: (percent: number) => void,
) {
  const formData = new FormData()
  formData.append('video', file)
  formData.append('prompt_mode', promptMode)
  formData.append('language', language)
  const { data } = await apiClient.post<{ job_id: string; status: JobStatus }>('/api/jobs', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (!event.total || !onUploadProgress) return
      onUploadProgress(Math.round((event.loaded / event.total) * 100))
    },
  })
  return data
}

export async function getJob(jobId: string) {
  const { data } = await apiClient.get<JobRecord>(`/api/jobs/${jobId}`)
  return data
}

export async function listJobs() {
  const { data } = await apiClient.get<JobRecord[]>('/api/jobs')
  return data
}

export async function cancelJob(jobId: string) {
  const { data } = await apiClient.post<{ job_id: string; status: JobStatus; message: string }>(`/api/jobs/${jobId}/cancel`)
  return data
}

export async function retryJob(jobId: string) {
  const { data } = await apiClient.post<{ job_id: string; status: JobStatus }>(`/api/jobs/${jobId}/retry`)
  return data
}
