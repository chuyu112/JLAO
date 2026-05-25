<template>
  <section class="panel agent-utterance-panel">
    <div class="panel-header">
      <div>
        <h2>虚拟场控回复流</h2>
        <p>{{ agents.length }} 个角色 · 仅模拟，不发送</p>
      </div>
      <span class="count-pill">{{ utterances.length }}</span>
    </div>

    <div class="agent-list">
      <article v-for="utterance in utterances.slice(0, 8)" :key="utterance.id" class="utterance-item">
        <div class="utterance-meta">
          <span>{{ utterance.agent_role }}</span>
          <small>{{ utterance.agent_name }}</small>
          <b :class="modeClass(utterance.send_mode)">{{ modeLabel(utterance.send_mode) }}</b>
        </div>
        <p>{{ utterance.content }}</p>
        <footer>{{ utterance.trigger_reason }}</footer>
      </article>
      <div v-if="!utterances.length" class="empty-state compact">等待公开视频号直播转写触发虚拟回复。</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AgentProfile, AgentUtterance } from '../types'

defineProps<{
  agents: AgentProfile[]
  utterances: AgentUtterance[]
}>()

function modeLabel(mode: string) {
  if (mode === 'blocked') return '拦截'
  if (mode === 'needs_review') return '审核'
  return '模拟'
}

function modeClass(mode: string) {
  return {
    blocked: mode === 'blocked',
    review: mode === 'needs_review',
    auto: mode === 'auto_simulated',
  }
}
</script>

<style scoped>
.agent-utterance-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.panel-header h2 {
  margin: 0;
  font-size: 15px;
}
.panel-header p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #8fa3b6;
}
.count-pill {
  min-width: 26px;
  height: 22px;
  border-radius: 11px;
  background: rgba(34, 211, 166, 0.16);
  color: #6ff0cf;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.agent-list {
  display: grid;
  gap: 8px;
}
.utterance-item {
  padding: 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.utterance-meta {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
}
.utterance-meta span {
  font-weight: 700;
  font-size: 13px;
}
.utterance-meta small {
  color: #8fa3b6;
  font-size: 11px;
}
.utterance-meta b {
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.utterance-meta b.auto {
  color: #6ff0cf;
  background: rgba(34, 211, 166, 0.14);
}
.utterance-meta b.review {
  color: #ffd166;
  background: rgba(255, 209, 102, 0.13);
}
.utterance-meta b.blocked {
  color: #ff9aa2;
  background: rgba(255, 94, 120, 0.15);
}
.utterance-item p {
  margin: 7px 0 0;
  color: #d7e2ec;
  font-size: 12px;
  line-height: 1.5;
}
.utterance-item footer {
  margin-top: 6px;
  color: #8fa3b6;
  font-size: 11px;
}
</style>
