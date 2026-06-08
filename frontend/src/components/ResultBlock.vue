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
    await navigator.clipboard.writeText(props.content)
    showSuccessToast('已复制')
  } catch {
    showFailToast('复制失败')
  }
}
</script>

