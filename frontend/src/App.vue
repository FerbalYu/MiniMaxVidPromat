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

      <van-button
        class="primary-action"
        type="primary"
        block
        round
        :loading="isBusy"
        :disabled="!selectedFile || isBusy"
        @click="submitVideo"
      >
        开始生成提示词
      </van-button>

      <div v-if="job" class="progress-card">
        <div class="status-line">
          <strong>{{ statusText }}</strong>
          <span>{{ job.progress }}%</span>
        </div>
        <van-progress :percentage="job.progress" stroke-width="8" color="#20765b" />
        <p>{{ job.message }}</p>
      </div>

      <van-notice-bar
        v-if="job?.status === 'failed'"
        class="error-bar"
        wrapable
        :scrollable="false"
        color="#a33a24"
        background="#fff1eb"
        :text="job.error || '处理失败'"
      />
    </section>

    <section v-if="job?.result" class="result-panel">
      <ResultBlock title="即梦一键粘贴版" :content="job.result.seedance_prompt" primary />
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
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { showFailToast, showSuccessToast, type UploaderFileListItem } from 'vant'
import ResultBlock from './components/ResultBlock.vue'
import DetailItem from './components/DetailItem.vue'
import { createJob, getJob, type JobRecord, type PromptMode } from './api/jobs'

const fileList = ref<UploaderFileListItem[]>([])
const selectedFile = ref<File | null>(null)
const previewUrl = ref('')
const promptMode = ref<PromptMode>('standard')
const language = ref('zh')
const job = ref<JobRecord | null>(null)
const pollingTimer = ref<number | null>(null)
const activeJobId = ref('')

const isBusy = computed(() => job.value?.status === 'queued' || job.value?.status === 'processing')
const statusText = computed(() => {
  const status = job.value?.status
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'processing') return '处理中'
  return '排队中'
})

function handleAfterRead(item: UploaderFileListItem | UploaderFileListItem[]) {
  const current = Array.isArray(item) ? item[0] : item
  const file = current.file
  if (!file) return
  stopPolling()
  activeJobId.value = ''
  selectedFile.value = file
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file)
  job.value = null
}

function handleDelete() {
  stopPolling()
  activeJobId.value = ''
  selectedFile.value = null
  job.value = null
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  return true
}

async function submitVideo() {
  if (!selectedFile.value) return
  try {
    stopPolling()
    const created = await createJob(selectedFile.value, promptMode.value, language.value)
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
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : '提交失败')
  }
}

function pollJob(jobId: string) {
  stopPolling()
  const tick = async () => {
    try {
      const currentJob = await getJob(jobId)
      if (activeJobId.value !== jobId) return
      job.value = currentJob
      if (job.value.status === 'completed') {
        stopPolling()
        activeJobId.value = ''
        showSuccessToast('提示词生成完成')
        return
      }
      if (job.value.status === 'failed') {
        stopPolling()
        activeJobId.value = ''
        showFailToast('处理失败')
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

function stopPolling() {
  if (pollingTimer.value) {
    window.clearTimeout(pollingTimer.value)
    pollingTimer.value = null
  }
}

onBeforeUnmount(() => {
  stopPolling()
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>
