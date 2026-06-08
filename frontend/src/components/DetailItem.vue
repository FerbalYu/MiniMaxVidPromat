<template>
  <div class="detail-item">
    <span>{{ title }}</span>
    <p>{{ content || '未识别' }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  content: string
}>()
</script>

