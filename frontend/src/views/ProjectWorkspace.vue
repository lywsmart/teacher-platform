<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download, errorMessage } from '../api'

type FileItem = { id: number; name: string; status: string; note: string; available: boolean }
type Selection = {
  category_id: number | null; use_for: string; clause: string; condition: string; score_group: string
  basis: string; self_score?: number; missing: string; evidence_ids: number[]; audited_score?: number; audit_note?: string
}
type Row = {
  id: number; title: string; category: string; level?: string; rank?: number; deleted: boolean; directory: string
  data: Selection; issues: string[]; evidence: FileItem[]; available_evidence: FileItem[]
}
type ConditionGroup = { name: string; mode: string; clauses: { name: string; status: string }[] }
type Settings = { review_type?: string; rule_year?: number; groups: ConditionGroup[] }
type Workspace = {
  settings: Settings; directories: { id: number; name: string }[]
  rows: Row[]; issues: string[]; materials: FileItem[]; groups: (ConditionGroup & { outcome: string })[]
}
type Export = { id: number; filename: string; mode: string; issue_count: number; created_at: string }
type Candidate = { id: number; title: string; year: number }
const props = defineProps<{ project: { id: number; name: string; year: number; target_title: string } }>()
const root = `/title-applications/${props.project.id}`
const base = `${root}/workspace`
const state = ref<Workspace>()
const history = ref<Export[]>([])
const settings = ref<Settings>({ groups: [] })
const busy = ref(false)
const tab = ref('items')
const candidates = ref<Candidate[]>([])
const candidate = ref<number>()
const keyword = ref('')
const editing = ref<Row>()
const form = ref<Selection>()
const materialTypes = ref<string[]>([])
const materialType = ref('')
const reviewTypes = ['教学为主型', '教学科研并重型', '社会服务型', '思政课教师', '专职辅导员']

async function run(task: () => Promise<void>) {
  busy.value = true
  try { await task() }
  catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}
async function reload() {
  const { data } = await api.get(base)
  state.value = data
  settings.value = { ...data.settings, groups: structuredClone(data.settings.groups || []) }
}
async function loadHistory() { history.value = (await api.get(`${base}/exports`)).data }
async function find() {
  const { data } = await api.get('/achievements', { params: { keyword: keyword.value, page_size: 50 } })
  candidates.value = data.items
}
onMounted(() => run(async () => {
  const [, , , materials] = await Promise.all([reload(), find(), loadHistory(), api.get(`${root}/materials`)])
  materialTypes.value = materials.data.categories
}))
function saveSettings() {
  return run(async () => {
    await api.put(`${base}/settings`, settings.value)
    await reload()
  })
}
function addGroup() {
  settings.value.groups.push({ name: '', mode: 'all', clauses: [{ name: '', status: '待核实' }] })
}
function add() {
  if (!candidate.value) return
  const id = candidate.value
  return run(async () => {
    await api.put(`${base}/items/${id}`, {})
    candidate.value = undefined
    await reload()
    const row = state.value?.rows.find(item => item.id === id)
    if (row) edit(row)
  })
}
function edit(row: Row) {
  editing.value = row
  form.value = { ...row.data, evidence_ids: row.evidence.map(file => file.id) }
}
function save() {
  if (!editing.value || !form.value) return
  return run(async () => {
    await api.put(`${base}/items/${editing.value!.id}`, form.value)
    editing.value = undefined
    await reload()
  })
}
async function remove(row: Row) {
  try { await ElMessageBox.confirm('该成果将移出本次申报，成果库记录和佐证会保留。', '移出清单') }
  catch { return }
  await run(async () => { await api.delete(`${base}/items/${row.id}`); await reload() })
}
function upload(event: Event, row?: Row) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  return run(async () => {
    const data = new FormData()
    data.append('file', file)
    try {
      if (row && form.value) {
        data.append('file_category', '申报佐证')
        const uploaded = await api.post(`/achievements/${row.id}/files`, data)
        form.value.evidence_ids.push(uploaded.data.id)
        await reload()
        editing.value = state.value?.rows.find(item => item.id === row.id)
        ElMessage.success('佐证已上传。请保存本次引用。')
      } else {
        data.append('category', materialType.value)
        await api.post(`${root}/materials`, data)
        await reload()
      }
    } finally { input.value = '' }
  })
}
async function exportPackage(mode: 'draft' | 'package') {
  const issues = (state.value?.issues.length || 0) + (state.value?.rows.reduce((total, row) => total + row.issues.length, 0) || 0)
  if (mode === 'package' && issues) {
    try { await ElMessageBox.confirm(`仍有 ${issues} 项待处理，继续生成将保留这些提示。`, '确认生成材料包') }
    catch { return }
  }
  await run(async () => {
    const { data } = await api.post(`${base}/exports`, { mode, acknowledge_issues: mode === 'package' && issues > 0 })
    await loadHistory()
    await download(`${base}/exports/${data.id}`, data.filename)
  })
}
</script>

<template>
  <section class="panel" v-loading="busy && !editing">
    <div class="project-heading">
      <h3>{{ project.name }} · {{ project.year }} 年 · {{ project.target_title }}</h3>
      <slot name="actions" />
    </div>
    <template v-if="state">
    <div class="toolbar">
      <el-select v-model="settings.review_type" placeholder="选择评审类型" style="width:190px">
        <el-option v-for="type in reviewTypes" :key="type" :value="type" />
      </el-select>
      <el-input-number v-model="settings.rule_year" :min="2000" :max="2100" placeholder="规则年度" />
      <el-button :disabled="!settings.review_type || !settings.rule_year || busy" @click="saveSettings">保存评审设置</el-button>
    </div>
    <el-tabs v-model="tab">
      <el-tab-pane label="成果与条件核对" name="items">
        <div class="toolbar">
          <el-input v-model.trim="keyword" placeholder="按名称搜索成果库" style="width:210px" @keyup.enter="run(find)" />
          <el-button @click="run(find)">搜索</el-button>
          <el-select v-model="candidate" placeholder="选择已有成果" style="width:260px">
            <el-option v-for="item in candidates.filter(item => !state?.rows.some(row => row.id === item.id))"
              :key="item.id" :value="item.id" :label="`${item.year} · ${item.title}`" />
          </el-select>
          <el-button type="primary" :disabled="!candidate" @click="add">加入清单</el-button>
        </div>
        <el-table :data="state.rows" empty-text="请从成果库选入成果">
          <el-table-column prop="title" label="成果" min-width="160" />
          <el-table-column prop="directory" label="材料目录" min-width="110" />
          <el-table-column prop="data.use_for" label="申报用途" min-width="120" />
          <el-table-column prop="data.condition" label="条件状态" width="100" />
          <el-table-column label="待处理" min-width="205">
            <template #default="{ row }"><div v-for="issue in row.issues" :key="issue">{{ issue }}</div><span v-if="!row.issues.length">无</span></template>
          </el-table-column>
          <el-table-column label="操作" width="135">
            <template #default="{ row }">
              <el-button v-if="!row.deleted" link type="primary" @click="edit(row)">核对与补件</el-button>
              <el-button link type="danger" @click="remove(row)">移出</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="资格条件清单" name="conditions">
        <p class="muted">请按申报年度的附件 2 填入适用条件。各条款由人工核对，系统只汇总组合结果。</p>
        <div v-for="(group, index) in settings.groups" :key="index" class="export-preview">
          <div class="toolbar">
            <el-input v-model.trim="group.name" placeholder="条件组名称" maxlength="128" style="width:235px" />
            <el-select v-model="group.mode" aria-label="条件组合关系" style="width:150px">
              <el-option label="同时满足" value="all" /><el-option label="满足其中一项" value="any" />
            </el-select>
            <span v-if="state.groups[index]?.name === group.name">已保存结果：{{ state.groups[index]?.outcome }}</span>
            <el-button link type="danger" @click="settings.groups.splice(index, 1)">移除条件组</el-button>
          </div>
          <div v-for="(clause, position) in group.clauses" :key="position" class="toolbar">
            <el-input v-model.trim="clause.name" placeholder="填写适用条款" maxlength="500" style="width:310px" />
            <el-select v-model="clause.status" aria-label="核对状态" style="width:120px">
              <el-option v-for="value in ['待核实', '已满足', '未满足', '不适用']" :key="value" :value="value" />
            </el-select>
            <el-button link type="danger" :disabled="group.clauses.length < 2" @click="group.clauses.splice(position, 1)">移除条款</el-button>
          </div>
          <el-button :disabled="group.clauses.length >= 40" @click="group.clauses.push({ name: '', status: '待核实' })">添加条款</el-button>
        </div>
        <div class="toolbar">
          <el-button :disabled="settings.groups.length >= 30" @click="addGroup">添加条件组</el-button>
          <el-button type="primary" :disabled="!settings.review_type || !settings.rule_year || busy || settings.groups.some(group => !group.name || group.clauses.some(clause => !clause.name))" @click="saveSettings">保存条件清单</el-button>
        </div>
      </el-tab-pane>
      <el-tab-pane label="申报材料" name="materials">
        <div class="toolbar">
          <el-select v-model="materialType" placeholder="选择本次项目材料类别" style="width:235px">
            <el-option v-for="type in materialTypes" :key="type" :value="type" />
          </el-select>
          <input type="file" aria-label="上传申报材料" :disabled="!materialType || busy" @change="upload($event)" />
        </div>
        <el-table :data="state.materials">
          <el-table-column prop="name" label="文件名" min-width="170" />
          <el-table-column prop="status" label="审核状态" width="120" />
          <el-table-column prop="note" label="审核意见" min-width="140" />
          <el-table-column label="操作" width="90">
            <template #default="{ row }"><el-button link type="primary" :disabled="!row.available" @click="run(() => download(`${root}/materials/${row.id}`, row.name))">下载</el-button></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="导出预览与历史" name="exports">
        <div v-for="issue in state.issues" :key="issue">{{ issue }}</div>
        <h4>将包含的成果和佐证</h4>
        <div v-for="row in state.rows" :key="row.id" class="export-preview">
          <strong>{{ row.title }}</strong>
          <div>{{ row.evidence.filter(file => file.available).map(file => file.name).join('、') || '暂无可打包佐证' }}</div>
          <div v-if="row.issues.length" class="muted">{{ row.issues.join('；') }}</div>
        </div>
        <p>项目材料：{{ state.materials.filter(file => file.available).map(file => file.name).join('、') || '无' }}</p>
        <p>随包生成附件 2 条件对照、附件 18 计分明细和导出检查表。</p>
        <div class="toolbar">
          <el-button @click="run(() => download(`${base}/reports`, '申报对照与计分.xlsx'))">下载 Excel</el-button>
          <el-button @click="exportPackage('draft')">导出草稿</el-button>
          <el-button type="primary" @click="exportPackage('package')">生成申报材料包</el-button>
          <router-link class="action-button" :to="{ path: '/ai', query: { project: project.id } }">撰写本项目业绩总结</router-link>
        </div>
        <el-table :data="history" empty-text="暂无历史导出">
          <el-table-column prop="id" label="记录编号" width="100" />
          <el-table-column prop="filename" label="历史材料包" min-width="170" />
          <el-table-column prop="created_at" label="生成时间" min-width="150" />
          <el-table-column prop="issue_count" label="待处理数" width="100" />
          <el-table-column label="操作" width="100"><template #default="{ row }"><el-button link type="primary" @click="run(() => download(`${base}/exports/${row.id}`, row.filename))">下载</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
    </template>
    <el-empty v-else-if="!busy" description="暂时无法加载申报工作台" />
  </section>
  <el-dialog :model-value="!!editing" :title="editing?.title || '核对成果'" width="min(95vw, 720px)" @close="editing = undefined">
    <el-form v-if="editing && form" label-position="top" @submit.prevent="save">
      <div class="grid-2">
        <el-form-item label="材料目录">
          <el-select v-model="form.category_id" clearable placeholder="待归类" :value-on-clear="null">
            <el-option v-for="directory in state?.directories" :key="directory.id" :value="directory.id" :label="directory.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="申报用途"><el-select v-model="form.use_for"><el-option v-for="value in ['待确认', '教学（工作）业绩', '科研业绩', '仅计分']" :key="value" :value="value" /></el-select></el-form-item>
        <el-form-item label="附件 2 条款"><el-input v-model="form.clause" maxlength="500" /></el-form-item>
        <el-form-item label="资格条件核对"><el-select v-model="form.condition"><el-option v-for="value in ['待核实', '已满足', '未满足', '不适用']" :key="value" :value="value" /></el-select></el-form-item>
        <el-form-item label="附件 18 计分栏目"><el-input v-model="form.score_group" maxlength="64" /></el-form-item>
        <el-form-item label="教师自评分"><el-input-number v-model="form.self_score" :min="0" :max="100" :precision="2" /></el-form-item>
      </div>
      <p v-if="form.audited_score != null">审核分 {{ form.audited_score }}　{{ form.audit_note }}</p>
      <el-form-item label="计分依据"><el-input v-model="form.basis" maxlength="500" /></el-form-item>
      <el-form-item label="待补佐证"><el-input v-model="form.missing" maxlength="500" /></el-form-item>
      <el-form-item label="本次引用的成果佐证">
        <el-checkbox-group v-model="form.evidence_ids">
          <div v-for="file in editing.available_evidence" :key="file.id">
            <el-checkbox :value="file.id">{{ file.name }} · {{ file.status }}</el-checkbox>
            <el-button v-if="file.available" link type="primary" @click="run(() => download(`/files/${file.id}/download`, file.name))">下载</el-button>
            <span v-if="file.note" class="muted">{{ file.note }}</span>
          </div>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="上传补充佐证"><input type="file" aria-label="上传补充佐证" :disabled="busy" @change="upload($event, editing)" /></el-form-item>
      <el-button type="primary" native-type="submit" :loading="busy">保存本次引用</el-button>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.project-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.project-heading h3 { margin: 0; overflow-wrap: anywhere; }
.export-preview { padding: 8px 0; border-bottom: 1px solid var(--line); }
</style>
