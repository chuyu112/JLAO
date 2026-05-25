<template>
  <section class="panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">实时转写</div>
        <div class="transcript-meta">直播声音实时转写</div>
      </div>
      <n-tag size="small">{{ transcripts.length }} 条</n-tag>
    </header>
    <div class="panel-body">
      <div v-if="partialTranscript" class="transcript-partial">
        正在识别：{{ partialTranscript }}
      </div>
      <div v-if="transcripts.length === 0" class="empty-state">
        接入直播音频后，这里会出现主播实时讲解内容。
      </div>
      <div v-else class="transcript-list">
        <article v-for="item in orderedTranscripts" :key="item.id" class="transcript-item">
          <div class="transcript-text">{{ item.text }}</div>
          <div class="transcript-meta">
            #{{ item.index }} ｜ {{ formatTime(item.created_at) }}
            <template v-if="item.keywords.length"> ｜ 关键词：{{ item.keywords.join('、') }}</template>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'
import type { TranscriptSegment } from '../types'

const props = defineProps<{
  transcripts: TranscriptSegment[]
  partialTranscript: string
}>()

const orderedTranscripts = computed(() => [...props.transcripts].slice(-30).reverse())

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

