<template>
  <main class="page">
    <app-top-nav title="观察报告" subtitle="把公开视频号翡翠直播沉淀成训练样本" />

    <section class="dashboard" style="height: auto">
      <div class="status-bar">
        <div>
          <div class="panel-title">公开视频号翡翠直播观察报告</div>
          <div class="transcript-meta">基于投屏采集、转写、虚拟回复和风险样本生成</div>
        </div>
        <n-button type="primary" :disabled="!store.currentSession" @click="handleGenerate">
          生成观察报告
        </n-button>
      </div>

      <section class="panel">
        <header class="panel-header">
          <div class="panel-title">观察内容</div>
          <n-tag v-if="store.report" type="success">已生成</n-tag>
        </header>
        <div class="panel-body">
          <div v-if="!store.report" class="empty-state">
            观察结束后点击“生成观察报告”，这里会展示话术样本、风险改写和新人训练素材。
          </div>
          <template v-else>
            <n-alert type="success" :show-icon="false">{{ store.report.summary }}</n-alert>
            <div class="main-grid" style="grid-template-columns: repeat(2, minmax(280px, 1fr)); margin-top: 14px">
              <report-section title="可学习话术" :items="store.report.useful_scripts" />
              <report-section title="讲解缺口" :items="store.report.missed_points" />
              <report-section title="风险改写" :items="store.report.risk_warnings" />
              <report-section title="训练样本任务" :items="store.report.next_suggestions" />
            </div>
          </template>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { defineComponent, h } from 'vue'
import { NAlert, NButton, NTag, useMessage } from 'naive-ui'
import AppTopNav from '../components/AppTopNav.vue'
import { useJlaoStore } from '../stores/jlao'

const store = useJlaoStore()
const message = useMessage()

async function handleGenerate() {
  await store.generateReplay()
  message.success('观察报告已生成')
}

const ReportSection = defineComponent({
  props: {
    title: { type: String, required: true },
    items: { type: Array<string>, required: true },
  },
  setup(props) {
    return () =>
      h('section', { class: 'panel', style: 'min-height: 220px' }, [
        h('header', { class: 'panel-header' }, h('div', { class: 'panel-title' }, props.title)),
        h(
          'div',
          { class: 'panel-body' },
          props.items.length
            ? h(
                'div',
                { class: 'transcript-list' },
                props.items.map((item) => h('div', { class: 'transcript-item' }, item)),
              )
            : h('div', { class: 'empty-state' }, '暂无记录'),
        ),
      ])
  },
})
</script>
