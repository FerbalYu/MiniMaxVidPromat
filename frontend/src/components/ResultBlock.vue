<template>
  <article :class="['result-block', { primary }]">
    <header>
      <h2>{{ title }}</h2>
      <van-button size="small" plain type="primary" @click="copyText">复制</van-button>
    </header>
    <p>{{ content || '暂无内容' }}</p>
  </article>
</template>

<script setup lang="ts">
import { showFailToast, showSuccessToast } from 'vant'

const props = defineProps<{
  title: string
  content: string
  primary?: boolean
}>()

async function copyText() {
  if (!props.content) return
  try {
    await writeClipboard(props.content)
    showSuccessToast('已复制')
  } catch {
    showFailToast('复制失败')
  }
}

async function writeClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Fall through to execCommand for non-secure LAN origins.
    }
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)
  if (!copied) {
    throw new Error('copy failed')
  }
}
</script>
