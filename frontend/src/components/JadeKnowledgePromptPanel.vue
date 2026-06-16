<template>
  <section class="panel jade-knowledge-prompt-panel">
    <header class="panel-header">
      <div class="jade-knowledge-title">
        <div class="panel-title">直播间知识库</div>
        <div class="transcript-meta">{{ subjectLabel }} · 颜色/种水/款式/题材话术</div>
      </div>
      <span class="knowledge-count">{{ promptGroups.length }}</span>
    </header>

    <div class="panel-body jade-knowledge-body">
      <div class="jade-brief">
        <strong>{{ subjectLabel }}</strong>
        <span>{{ attributeLine }}</span>
      </div>

      <div class="prompt-grid">
        <article v-for="group in promptGroups" :key="group.title" class="prompt-card">
          <div class="prompt-card-head">
            <span>{{ group.title }}</span>
            <small>{{ group.tag }}</small>
          </div>
          <p>{{ group.content }}</p>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Product } from '../types'

const props = defineProps<{
  product: Product | null
  detectedName?: string
}>()

const subjectLabel = computed(() => (
  props.detectedName?.trim() ||
  props.product?.name?.trim() ||
  '待识别翡翠'
))

const color = computed(() => cleanValue(props.product?.color) || inferFromName(['阳绿', '帝王绿', '辣绿', '晴水', '蓝水', '紫罗兰', '白冰', '黄翡', '红翡', '墨翠', '飘花']) || '颜色待确认')
const water = computed(() => cleanValue(props.product?.water) || inferFromName(['玻璃种', '高冰', '冰种', '冰胶', '糯冰', '糯种', '豆种']) || '种水待确认')
const style = computed(() => cleanValue(props.product?.style) || cleanValue(props.product?.category) || inferFromName(['手镯', '珠串', '珠链', '蛋面', '戒指', '吊坠', '耳饰', '摆件']) || '款式待确认')
const theme = computed(() => cleanValue(props.product?.theme) || inferFromName(['观音', '佛公', '平安扣', '如意', '叶子', '山水', '貔貅', '葫芦', '福瓜', '福豆', '龙牌']) || '题材待确认')

const attributeLine = computed(() => [
  color.value,
  water.value,
  style.value,
  theme.value,
].filter(Boolean).join(' · '))

const promptGroups = computed(() => [
  {
    title: '颜色',
    tag: color.value,
    content: colorPrompt(color.value),
  },
  {
    title: '种水',
    tag: water.value,
    content: waterPrompt(water.value),
  },
  {
    title: '款式',
    tag: style.value,
    content: stylePrompt(style.value),
  },
  {
    title: '题材',
    tag: theme.value,
    content: themePrompt(theme.value),
  },
  {
    title: '历史',
    tag: '文化感',
    content: '翡翠在清代进入宫廷审美后，逐渐从玉料变成身份、祝福和收藏的表达。讲的时候可以把它放到东方玉文化里，说它不是只看亮不亮，而是看颜色、底子、工艺和寓意是否统一。',
  },
  {
    title: '小故事',
    tag: '停留话术',
    content: `可以说这件${subjectLabel.value}适合慢看：第一眼看颜色，第二眼看水头，第三眼看题材。懂行的人买翡翠，往往不是被一句价格打动，而是被越看越舒服的细节留住。`,
  },
  {
    title: '段子',
    tag: '轻口播',
    content: '直播间看翡翠别急着问最低价，先问自己喜不喜欢。喜欢才叫缘分，不喜欢再便宜也只是替抽屉进货。',
  },
  {
    title: '成交提示',
    tag: '收口',
    content: '收口可以围绕“颜色正、种水舒服、题材有寓意、上身不挑人”四点讲，最后提醒证据截图、尺寸、瑕疵和证书信息要同步确认。',
  },
])

function cleanValue(value: string | undefined | null): string {
  const cleaned = String(value || '').trim()
  if (!cleaned || cleaned.includes('待识别') || cleaned === '-') return ''
  return cleaned
}

function inferFromName(candidates: string[]): string {
  const source = subjectLabel.value
  return candidates.find((item) => source.includes(item)) || ''
}

function colorPrompt(value: string): string {
  if (value.includes('绿')) return '绿色系重点讲“正、阳、浓、匀”：颜色要正，亮度要舒服，不能灰闷。上手时提醒观众看自然光下的色感，避免只被灯光里的鲜艳带着走。'
  if (value.includes('蓝水') || value.includes('晴水')) return '蓝水、晴水适合讲清爽和气质，重点看底子干净、颜色不灰、光感柔和。它不是靠浓艳取胜，而是靠耐看和高级感。'
  if (value.includes('紫')) return '紫罗兰可以讲“见光不死”和温柔感，提醒看实物光线下的紫味是否稳定，适合走浪漫、稀缺和上身氛围的方向。'
  if (value.includes('白') || value.includes('无色')) return '白冰、无色重点讲通透度、棉感和起光。颜色不抢戏，反而更看种水和工艺，适合强调干净、百搭、日常佩戴。'
  if (value.includes('红')) return '红翡重点讲喜庆、暖色和稀缺感，颜色要看红味是否正、是否发暗发褐。直播里可以提醒观众看自然光下的红润度，以及红色部分和底子的过渡是否舒服。'
  return '颜色先讲真实观感：是否干净、是否均匀、是否跟种水协调。识别还不确定时，不要把颜色说死，可以用“偏”“带一点”“自然光再确认”。'
}

function waterPrompt(value: string): string {
  if (value.includes('玻璃') || value.includes('高冰')) return '高种水重点讲通透、起光和胶感。镜头里可以让观众看边缘透光和内部结构，越干净越能体现高级感。'
  if (value.includes('冰')) return '冰种、糯冰适合讲“透而不空、润而不闷”。重点看水头是否足、棉是否影响美观，以及上手有没有清爽感。'
  if (value.includes('糯')) return '糯种重点讲细腻、温润和性价比。它不一定追求极透，但要看底子是否细、颜色是否舒服、工艺是否把料子优点做出来。'
  if (value.includes('豆')) return '豆种重点讲实在、耐戴和性价比，结构感会比冰种明显一些。讲解时别硬夸通透，可以把重点放在颜色、雕工、寓意和日常佩戴的亲和力上。'
  return '种水还不确定时，先讲光感、细腻度和通透度，不要直接下绝对结论。可以引导观众看“底子干不干净、水头够不够、结构粗不粗”。'
}

function stylePrompt(value: string): string {
  if (value.includes('手镯')) return '手镯讲整体感，重点看圈口、条形、颜色分布和纹裂。它是最吃料也最看完整度的品类，可以强调上手气场和保值关注点。'
  if (value.includes('珠')) return '珠串讲统一度：珠径、颜色、种水、孔道和圆度要协调。适合提醒观众看整串是否顺眼，别只盯一颗特别亮的珠子。'
  if (value.includes('蛋') || value.includes('戒')) return '蛋面讲饱满度和起光，面型要鼓，颜色要聚。小件更考验颜色集中度，适合讲精致和日常搭配。'
  if (value.includes('吊坠')) return '吊坠讲料子和雕工的配合：种水托底，题材加分。镜头里可以多给侧面厚度和雕刻细节。'
  return '款式讲佩戴场景：日常、送礼、收藏、搭配。先说适合谁，再说为什么适合，观众更容易代入。'
}

function themePrompt(value: string): string {
  if (value.includes('观音')) return '观音题材常讲平安、慈悲和护佑，适合送长辈或自己贴身佩戴。讲解时注意语气稳一点，不要讲得太跳。'
  if (value.includes('佛')) return '佛公题材讲笑口常开、福气和包容，适合轻松一点的口播。可以提醒看肚子是否饱满、脸部雕工是否舒服。'
  if (value.includes('如意')) return '如意讲事事顺、万事如意，送礼场景强。重点看线条是否流畅，造型是否饱满。'
  if (value.includes('叶')) return '叶子寓意金枝玉叶、一夜成名，适合年轻女性或送祝福。讲解时可以强调灵动、轻巧、上身显气质。'
  if (value.includes('山水')) return '山水牌讲胸有丘壑、仁者乐山智者乐水，适合讲文化感和收藏感。看雕刻层次、留白和意境。'
  if (value.includes('貔貅')) return '貔貅常讲招财守财，适合做生意、开店、求好彩头的人。重点看嘴、身形和整体饱满度。'
  return '题材还不明确时，可以先讲“好寓意”和“佩戴场景”，等截图/OCR 或人工标注确认后再补具体故事。'
}
</script>

<style scoped>
.jade-knowledge-prompt-panel {
  height: 100%;
  min-height: 0;
}

.jade-knowledge-prompt-panel .panel-header {
  min-height: 54px;
  align-items: center;
}

.jade-knowledge-title {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.jade-knowledge-title .panel-title,
.jade-knowledge-title .transcript-meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.jade-knowledge-title .panel-title {
  line-height: 1.2;
}

.jade-knowledge-title .transcript-meta {
  margin-top: 0;
  line-height: 1.25;
}

.knowledge-count {
  min-width: 28px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  color: #07100d;
  background: #22d3a6;
  font-size: 12px;
  font-weight: 800;
}

.jade-knowledge-body {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 8px;
}

.jade-brief {
  min-width: 0;
  display: grid;
  gap: 4px;
  padding: 8px 10px;
  border: 1px solid rgba(34, 211, 166, 0.26);
  border-radius: 6px;
  background: rgba(34, 211, 166, 0.08);
}

.jade-brief strong,
.jade-brief span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.jade-brief strong {
  color: #eafff8;
  font-size: 13px;
}

.jade-brief span {
  color: #8ff2ca;
  font-size: 12px;
}

.prompt-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.prompt-card {
  min-width: 0;
  min-height: 0;
  padding: 9px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
}

.prompt-card-head {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.prompt-card-head span {
  min-width: 0;
  overflow: hidden;
  color: #f4fffc;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-card-head small {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  color: #88f0bd;
  font-size: 11px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-card p {
  margin: 6px 0 0;
  color: #c7d6df;
  font-size: 12px;
  line-height: 1.48;
}

@media (max-width: 1180px) {
  .prompt-grid {
    grid-template-columns: 1fr;
  }
}
</style>
