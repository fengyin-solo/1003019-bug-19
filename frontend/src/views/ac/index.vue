<template>
  <section class="page" data-module="ac">
    <header class="page-head">
      <div>
        <h2>空调管理管理</h2>
        <p class="page-desc">维护空调，围绕空调编号、空调类型、制冷量、所属站点做登记、筛选与状态流转。</p>
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
              @click="openAction(action, row)"
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

    <div v-if="createVisible" class="dialog-mask">
      <form class="dialog" @submit.prevent="submitCreate">
        <h3 class="dialog-title">登记空调</h3>
        <label v-for="field in entryFields" :key="field" class="dialog-item">
          <span>{{ field }}<em v-if="requiredFields.includes(field)" class="required-mark">*</em></span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p class="dialog-tip">带 * 的为必填项，缺哪一项会被拦下并指明。</p>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="dialog-actions">
          <button class="btn primary" type="submit">确认登记</button>
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
        </div>
      </form>
    </div>

    <div v-if="actionRow" class="dialog-mask">
      <form class="dialog" @submit.prevent="submitAction">
        <h3 class="dialog-title">{{ pendingAction }} — {{ actionRow['空调编号'] }}</h3>
        <p class="dialog-tip">
          当前状态：{{ actionRow['空调状态'] ?? actionRow.status }}；只能按 正常 → 制冷不足 → 压缩机故障 → 已更换 顺序流转，测量值随登记内容一起落盘。
        </p>
        <label v-for="field in measureFields" :key="field" class="dialog-item">
          <span>{{ field }}</span>
          <input v-model="actionForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="dialog-actions">
          <button class="btn primary" type="submit">确认{{ pendingAction }}</button>
          <button class="btn ghost" type="button" @click="actionRow = null">取消</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type ActionReply = { ok: boolean; message: string }

const ENDPOINT = '/api/ac'
const columns = ["空调编号", "空调类型", "制冷量", "所属站点", "运行电流", "设定温度", "回风温度", "空调状态"]
const actions = ["登记不足", "登记故障", "安排更换"]
const statuses = ["正常", "制冷不足", "压缩机故障", "已更换"]
const stats = [{"label": "正常空调", "value": 0}, {"label": "制冷不足", "value": 0}, {"label": "故障空调", "value": 0}]
const entryFields = ["空调编号", "空调类型", "制冷量", "所属站点", "运行电流", "设定温度", "回风温度"]
const requiredFields = ["空调编号", "空调类型", "制冷量", "回风温度"]
const measureFields = ["制冷量", "运行电流", "设定温度", "回风温度"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})
const actionRow = ref<Row | null>(null)
const pendingAction = ref('')
const actionForm = ref<Record<string, string>>({})
const dialogError = ref('')

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  dialogError.value = ''
  noticeMessage.value = ''
  createVisible.value = true
}

function openAction(action: string, row: Row) {
  pendingAction.value = action
  actionRow.value = row
  const form: Record<string, string> = {}
  for (const field of measureFields) {
    const value = row[field]
    form[field] = value === null || value === undefined ? '' : String(value)
  }
  actionForm.value = form
  dialogError.value = ''
  noticeMessage.value = ''
}

async function postValues(path: string, values: Record<string, string>): Promise<ActionReply> {
  const response = await request(path, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  const payload = (await response.json().catch(() => null)) as (ActionReply & { detail?: string }) | null
  if (!response.ok) {
    throw new Error(payload?.detail ?? `接口返回 ${response.status}，操作未生效`)
  }
  if (!payload) {
    throw new Error('接口未返回可读结果，操作未生效')
  }
  return payload
}

async function submitCreate() {
  dialogError.value = ''
  try {
    const payload = await postValues(ENDPOINT, createForm.value)
    if (!payload.ok) {
      dialogError.value = payload.message
      return
    }
    createVisible.value = false
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '空调登记失败'
  }
}

async function submitAction() {
  const row = actionRow.value
  if (!row) {
    return
  }
  dialogError.value = ''
  try {
    const payload = await postValues(`${ENDPOINT}/${String(row.id)}/actions`, {
      action: pendingAction.value,
      ...actionForm.value,
    })
    if (!payload.ok) {
      dialogError.value = payload.message
      return
    }
    actionRow.value = null
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '空调管理操作失败'
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

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.dialog {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  width: 360px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dialog-title {
  margin: 0;
  font-size: 15px;
}
.dialog-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 2px;
}
.dialog-item input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.required-mark {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.dialog-tip {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.notice-text {
  color: #067647;
}
</style>
