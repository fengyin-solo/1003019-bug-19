<template>
  <section class="page" data-module="ac">
    <header class="page-head">
      <div>
        <h2>空调管理</h2>
        <p class="page-desc">
          维护空调，围绕空调编号、空调类型、制冷量、所属站点做登记、筛选与状态流转。
          状态只能按 {{ statuses.join(' → ') }} 依次登记，跳档会被打回并说明卡在哪一档。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记空调</button>
        <button class="btn" type="button" @click="exportRows">导出空调管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无空调管理数据，可先登记空调</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条空调管理记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3>登记空调</h3>
        <p class="modal-desc">带 * 为必填；回风温度是判断正常运行的依据，缺了会被打回并点名。</p>
        <form @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.name" class="form-item">
            <span>{{ field.name }}<em v-if="field.required">*</em></span>
            <input v-model="createForm[field.name]" :placeholder="`请输入${field.name}`" />
          </label>
          <p v-if="createError" class="modal-error">{{ createError }}</p>
          <div class="modal-actions">
            <button class="btn primary" type="submit">提交登记</button>
            <button class="btn ghost" type="button" @click="closeCreate">取消</button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/ac'
const columns = ["空调编号", "空调类型", "制冷量", "所属站点", "运行电流", "设定温度", "回风温度", "空调状态"]
const actions = ["登记不足", "登记故障", "安排更换"]
const statuses = ["正常", "制冷不足", "压缩机故障", "已更换"]
const stats = [{"label": "正常空调", "value": 0}, {"label": "制冷不足", "value": 0}, {"label": "故障空调", "value": 0}]
const createFields = [
  { name: "空调编号", required: true },
  { name: "空调类型", required: true },
  { name: "制冷量", required: true },
  { name: "所属站点", required: false },
  { name: "运行电流", required: false },
  { name: "设定温度", required: false },
  { name: "回风温度", required: true },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})
const createError = ref('')

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  showCreate.value = true
}

function closeCreate() {
  showCreate.value = false
}

async function submitCreate() {
  createError.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ?? '空调登记请求未送达，请稍后重试')
    }
    if (!payload?.ok) {
      createError.value = payload?.message ?? '空调登记被打回，但未说明原因'
      return
    }
    showCreate.value = false
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '空调登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ?? '空调管理动作未生效，请稍后重试')
    }
    if (!payload?.ok) {
      errorMessage.value = payload?.message ?? '空调管理动作被打回，但未说明原因'
      return
    }
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '空调管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('空调列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '空调管理列表读取失败'
  }
}

onMounted(reload)
</script>
