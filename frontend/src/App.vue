<template>
  <main class="app-shell">
    <section class="hero-band">
      <div class="brand-row">
        <div class="brand-mark">JM</div>
        <div>
          <h1>视频转即梦提示词</h1>
          <p>手机上传视频，本地服务调用 MiniMax-M3，生成 Seedance 2.0 可用提示词。</p>
        </div>
      </div>
      <p v-if="health" class="runtime-line">
        {{ health.model }} · 最大 {{ health.max_upload_mb }}MB · 并发 {{ health.max_concurrent_jobs }}
      </p>
    </section>

    <section class="work-panel">
      <van-uploader
        v-model="fileList"
        class="video-uploader"
        accept="video/mp4,video/avi,video/quicktime,video/x-matroska"
        :max-count="1"
        :after-read="handleAfterRead"
        :before-delete="handleDelete"
      >
        <div class="upload-box">
          <div class="upload-icon">+</div>
          <strong>选择或拍摄视频</strong>
          <span>支持 MP4、MOV、AVI、MKV</span>
        </div>
      </van-uploader>

      <div v-if="selectedFile" class="file-meta">
        <span>{{ selectedFile.name }}</span>
        <strong>{{ formatBytes(selectedFile.size) }}</strong>
      </div>

      <video v-if="previewUrl" class="preview-video" :src="previewUrl" controls playsinline />

      <div class="form-grid">
        <label class="field-label">提示词目标</label>
        <van-radio-group v-model="promptMode" direction="horizontal" class="mode-group">
          <van-radio name="standard">通用</van-radio>
          <van-radio name="cinematic">电影感</van-radio>
          <van-radio name="product">商品</van-radio>
          <van-radio name="short_drama">短剧</van-radio>
        </van-radio-group>

        <label class="field-label">输出语言</label>
        <van-radio-group v-model="language" direction="horizontal" class="mode-group">
          <van-radio name="zh">中文优先</van-radio>
          <van-radio name="en">英文优先</van-radio>
        </van-radio-group>
      </div>

      <div class="action-grid">
        <van-button
          class="primary-action"
          type="primary"
          block
          round
          :loading="isSubmitting || isBusy"
          :disabled="!selectedFile || isSubmitting || isBusy"
          @click="submitVideo"
        >
          开始生成提示词
        </van-button>
        <van-button v-if="canCancel" plain type="danger" block round @click="cancelCurrentJob">取消任务</van-button>
        <van-button v-if="canRegenerate" plain type="primary" block round @click="submitVideo">重新生成</van-button>
      </div>

      <div v-if="isSubmitting && uploadProgress > 0" class="progress-card">
        <div class="status-line">
          <strong>上传中</strong>
          <span>{{ uploadProgress }}%</span>
        </div>
        <van-progress :percentage="uploadProgress" stroke-width="8" color="#20765b" />
      </div>

      <div v-if="job" class="progress-card">
        <div class="status-line">
          <strong>{{ statusText }}</strong>
          <span>{{ job.progress }}%</span>
        </div>
        <van-progress :percentage="job.progress" stroke-width="8" color="#20765b" />
        <p>{{ job.message }}</p>
      </div>

      <van-notice-bar
        v-if="job?.status === 'failed' || job?.status === 'canceled'"
        class="error-bar"
        wrapable
        :scrollable="false"
        color="#a33a24"
        background="#fff1eb"
        :text="job.error || job.message || '处理失败'"
      />
    </section>

    <section v-if="job?.result" class="result-panel">
      <ResultBlock title="即梦一键粘贴版" :content="editableSeedancePrompt" primary />
      <textarea v-model="editableSeedancePrompt" class="prompt-editor" rows="8" />
      <div class="result-actions">
        <van-button size="small" plain type="primary" @click="downloadResult">下载 TXT</van-button>
        <van-button size="small" plain @click="resetEditablePrompt">恢复模型结果</van-button>
      </div>

      <ResultBlock title="分镜增强版" :content="job.result.storyboard_prompt" />
      <ResultBlock title="负面提示词" :content="job.result.negative_prompt" />
      <ResultBlock title="英文版" :content="job.result.english_prompt" />

      <div class="detail-list">
        <DetailItem title="内容摘要" :content="job.result.summary" />
        <DetailItem title="主体" :content="job.result.subject" />
        <DetailItem title="场景" :content="job.result.scene" />
        <DetailItem title="动作" :content="job.result.action" />
        <DetailItem title="运镜" :content="job.result.camera" />
        <DetailItem title="光线" :content="job.result.lighting" />
        <DetailItem title="风格" :content="job.result.style" />
      </div>
    </section>

    <section v-if="history.length" class="history-panel">
      <header>
        <h2>最近任务</h2>
        <van-button size="small" plain @click="refreshHistory">刷新</van-button>
      </header>
      <button v-for="item in history" :key="item.id" class="history-item" type="button" @click="openHistoryJob(item.id)">
        <span>{{ item.filename }}</span>
        <strong>{{ statusLabel(item.status) }}</strong>
      </button>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { showFailToast, showSuccessToast, type UploaderFileListItem } from 'vant'
import ResultBlock from './components/ResultBlock.vue'
import DetailItem from './components/DetailItem.vue'
import {
  cancelJob,
  createJob,
  getHealth,
  getJob,
  listJobs,
  type HealthInfo,
  type JobRecord,
  type JobStatus,
  type PromptMode,
} from './api/jobs'

const fileList = ref<UploaderFileListItem[]>([])
const selectedFile = ref<File | null>(null)
const previewUrl = ref('')
const promptMode = ref<PromptMode>('standard')
const language = ref('zh')
const job = ref<JobRecord | null>(null)
const history = ref<JobRecord[]>([])
const health = ref<HealthInfo | null>(null)
const pollingTimer = ref<number | null>(null)
const activeJobId = ref('')
const uploadProgress = ref(0)
const isSubmitting = ref(false)
const editableSeedancePrompt = ref('')

const isBusy = computed(() => job.value?.status === 'queued' || job.value?.status === 'processing')
const canCancel = computed(() => Boolean(job.value && (job.value.status === 'queued' || job.value.status === 'processing')))
const canRegenerate = computed(() => Boolean(selectedFile.value && job.value && ['failed', 'canceled', 'completed'].includes(job.value.status)))
const statusText = computed(() => statusLabel(job.value?.status || 'queued'))

watch(
  () => job.value?.result?.seedance_prompt,
  (value) => {
    editableSeedancePrompt.value = value || ''
  },
)

onMounted(async () => {
  await Promise.all([loadHealth(), refreshHistory()])
})

function handleAfterRead(item: UploaderFileListItem | UploaderFileListItem[]) {
  const current = Array.isArray(item) ? item[0] : item
  const file = current.file
  if (!file) return
  stopPolling()
  activeJobId.value = ''
  selectedFile.value = file
  uploadProgress.value = 0
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file)
  job.value = null
}

function handleDelete() {
  stopPolling()
  activeJobId.value = ''
  selectedFile.value = null
  job.value = null
  uploadProgress.value = 0
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  return true
}

async function submitVideo() {
  if (!selectedFile.value) return
  const maxUploadBytes = (health.value?.max_upload_mb || 0) * 1024 * 1024
  if (maxUploadBytes > 0 && selectedFile.value.size > maxUploadBytes) {
    showFailToast(`视频不能超过 ${health.value?.max_upload_mb}MB`)
    return
  }
  try {
    stopPolling()
    isSubmitting.value = true
    uploadProgress.value = 0
    const created = await createJob(selectedFile.value, promptMode.value, language.value, (percent) => {
      uploadProgress.value = percent
    })
    activeJobId.value = created.job_id
    job.value = {
      id: created.job_id,
      status: created.status,
      filename: selectedFile.value.name,
      size_bytes: selectedFile.value.size,
      prompt_mode: promptMode.value,
      language: language.value,
      progress: 0,
      message: '已提交，等待处理',
      result: null,
      error: null,
      created_at: Date.now() / 1000,
      updated_at: Date.now() / 1000,
      meta: {},
    }
    pollJob(created.job_id)
    await refreshHistory()
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : '提交失败')
  } finally {
    isSubmitting.value = false
  }
}

async function cancelCurrentJob() {
  if (!job.value) return
  try {
    await cancelJob(job.value.id)
    stopPolling()
    activeJobId.value = ''
    job.value = await getJob(job.value.id)
    await refreshHistory()
    showSuccessToast('任务已取消')
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : '取消失败')
  }
}

function pollJob(jobId: string) {
  stopPolling()
  const tick = async () => {
    try {
      const currentJob = await getJob(jobId)
      if (activeJobId.value !== jobId) return
      job.value = currentJob
      if (['completed', 'failed', 'canceled'].includes(job.value.status)) {
        stopPolling()
        activeJobId.value = ''
        await refreshHistory()
        if (job.value.status === 'completed') showSuccessToast('提示词生成完成')
        if (job.value.status === 'failed') showFailToast('处理失败')
        return
      }
      pollingTimer.value = window.setTimeout(tick, 1800)
    } catch (error) {
      stopPolling()
      activeJobId.value = ''
      showFailToast(error instanceof Error ? error.message : '查询任务失败')
    }
  }
  void tick()
}

async function openHistoryJob(jobId: string) {
  try {
    stopPolling()
    activeJobId.value = ''
    job.value = await getJob(jobId)
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : '读取任务失败')
  }
}

async function refreshHistory() {
  try {
    history.value = await listJobs()
  } catch {
    history.value = []
  }
}

async function loadHealth() {
  try {
    health.value = await getHealth()
  } catch {
    health.value = null
  }
}

function downloadResult() {
  if (!job.value?.result) return
  const content = [
    `即梦一键粘贴版\n${editableSeedancePrompt.value}`,
    `分镜增强版\n${job.value.result.storyboard_prompt}`,
    `负面提示词\n${job.value.result.negative_prompt}`,
    `英文版\n${job.value.result.english_prompt}`,
  ].join('\n\n')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${job.value.filename || 'prompt'}.txt`
  link.click()
  URL.revokeObjectURL(url)
}

function resetEditablePrompt() {
  editableSeedancePrompt.value = job.value?.result?.seedance_prompt || ''
}

function stopPolling() {
  if (pollingTimer.value) {
    window.clearTimeout(pollingTimer.value)
    pollingTimer.value = null
  }
}

function statusLabel(status: JobStatus) {
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'processing') return '处理中'
  if (status === 'canceled') return '已取消'
  return '排队中'
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

onBeforeUnmount(() => {
  stopPolling()
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>
