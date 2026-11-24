<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download, errorMessage } from '../api'

type Template = { id: string; name: string; fields: Record<string, string> }
type AwardForm = {
  template: string; title: string; achievement_date: string; organization: string; level: string
  prize: string; certificate_no: string; scope: string; role: string; rank?: number
  extras: Record<string, string>
}
type Award = AwardForm & { id: number }
type Evidence = { id: number; name: string; status: string; note: string }
const templates = ref<Template[]>([])
const rows = ref<Award[]>([])
const next = ref<number | null>(null)
const filter = ref('')
const editing = ref<number>()
const editOpen = ref(false)
const active = ref<Award>()
const evidenceOpen = ref(false)
const busy = ref(false)
const attachments = ref<Evidence[]>([])
function empty(template = ''): AwardForm {
  return { template, title: '', achievement_date: '', organization: '', level: '', prize: '',
    certificate_no: '', scope: '个人', role: '', rank: undefined, extras: {} }
}
const form = ref<AwardForm>(empty())
const template = computed(() => templates.value.find(item => item.id === form.value.template))
const templateName = (id: string) => templates.value.find(item => item.id === id)?.name || id

async function run(task: () => Promise<void>) {
  busy.value = true
  try { await task() }
  catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}
async function load(before = 0) {
  const { data } = await api.get('/awards', { params: { before, template: filter.value || undefined } })
  rows.value = before ? [...rows.value, ...data.items] : data.items
  next.value = data.next
}
onMounted(() => run(async () => {
  templates.value = (await api.get('/awards/templates')).data
  await load()
}))
function openEditor(item?: Award) {
  editing.value = item?.id
  form.value = item ? { ...empty(), ...item, extras: { ...item.extras } } : empty(filter.value || templates.value[0]?.id)
  editOpen.value = true
}
async function save() {
  await run(async () => {
    if (editing.value) await api.put(`/awards/${editing.value}`, form.value)
    else await api.post('/awards', form.value)
    editOpen.value = false
    await load()
    ElMessage.success('获奖记录已保存')
  })
}
async function remove(item: Award) {
  try { await ElMessageBox.confirm('删除后，该记录将从成果汇总及申报明细中移除。', '删除获奖记录', { type: 'warning' }) }
  catch { return }
  await run(async () => {
    await api.delete(`/achievements/${item.id}`)
    await load()
  })
}
async function loadEvidence(id: number) {
  attachments.value = (await api.get(`/awards/${id}/evidence`)).data
}
async function showEvidence(item: Award) {
  active.value = item
  attachments.value = []
  evidenceOpen.value = true
  await run(() => loadEvidence(item.id))
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const id = active.value?.id
  if (!file || !id) return
  await run(async () => {
    const data = new FormData()
    data.append('file', file)
    data.append('file_category', '获奖佐证')
    await api.post(`/achievements/${id}/files`, data)
    await loadEvidence(id)
    ElMessage.success('佐证已上传')
  })
  input.value = ''
}
</script>

<template>
  <section class="panel">
    <div class="toolbar">
      <el-select v-model="filter" style="width:230px" aria-label="获奖分类" :disabled="busy" @change="run(() => load())">
        <el-option label="全部获奖类别" value="" />
        <el-option v-for="item in templates" :key="item.id" :value="item.id" :label="item.name" />
      </el-select>
      <el-button type="primary" :disabled="busy || !templates.length" @click="openEditor()">录入获奖</el-button>
      <el-button :disabled="busy" @click="run(() => download('/awards/export', '获奖成果汇总.xlsx'))">导出汇总</el-button>
    </div>
    <p><router-link class="action-button" to="/titles">前往职称申报选入成果</router-link></p>
    <el-table v-loading="busy && !editOpen && !evidenceOpen" :data="rows" empty-text="暂无获奖记录">
      <el-table-column prop="title" label="获奖名称" min-width="150" />
      <el-table-column label="类别" min-width="145"><template #default="{ row }">{{ templateName(row.template) }}</template></el-table-column>
      <el-table-column prop="achievement_date" label="获奖日期" width="115" />
      <el-table-column label="级别" width="95"><template #default="{ row }">{{ row.level || '待核实' }}</template></el-table-column>
      <el-table-column prop="prize" label="奖等" width="90" />
      <el-table-column label="操作" min-width="170">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="busy" @click="openEditor(row)">编辑</el-button>
          <el-button link type="primary" :disabled="busy" @click="showEvidence(row)">佐证</el-button>
          <el-button link type="danger" :disabled="busy" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-button v-if="next" :disabled="busy" @click="run(() => load(next || 0))">加载更多</el-button>
  </section>
  <el-dialog v-model="editOpen" :title="editing ? '编辑获奖记录' : '录入获奖记录'" width="min(95vw, 650px)">
    <el-form label-position="top" @submit.prevent="save">
      <div class="grid-2">
        <el-form-item label="获奖模板">
          <el-select v-model="form.template" @change="form.extras = {}">
            <el-option v-for="item in templates" :key="item.id" :value="item.id" :label="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="获奖名称"><el-input v-model.trim="form.title" maxlength="255" /></el-form-item>
        <el-form-item label="获奖日期"><el-date-picker v-model="form.achievement_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="授奖单位"><el-input v-model.trim="form.organization" maxlength="255" /></el-form-item>
        <el-form-item label="认定级别"><el-input v-model.trim="form.level" placeholder="留空表示待核实" maxlength="64" /></el-form-item>
        <el-form-item label="奖项等次（按证书填写）"><el-input v-model.trim="form.prize" maxlength="64" placeholder="荣誉无等次可留空" /></el-form-item>
        <el-form-item label="证书编号"><el-input v-model.trim="form.certificate_no" maxlength="128" /></el-form-item>
        <el-form-item label="个人或团队"><el-radio-group v-model="form.scope"><el-radio value="个人">个人</el-radio><el-radio value="团队">团队</el-radio></el-radio-group></el-form-item>
        <el-form-item :label="form.template === 'student_contest' ? '本人指导角色' : '本人角色'"><el-input v-model.trim="form.role" maxlength="64" /></el-form-item>
        <el-form-item :label="form.template === 'student_contest' ? '本人指导排名' : '本人排名'"><el-input-number v-model="form.rank" :min="1" :max="9999" :precision="0" placeholder="待核实" /></el-form-item>
        <el-form-item v-for="(label, key) in template?.fields" :key="key" :label="label"><el-input v-model.trim="form.extras[key]" maxlength="255" /></el-form-item>
      </div>
      <el-button type="primary" native-type="submit" :loading="busy" :disabled="!form.title || !form.achievement_date || !form.organization">保存</el-button>
    </el-form>
  </el-dialog>
  <el-dialog v-model="evidenceOpen" :title="active?.title + ' · 获奖佐证'" width="min(95vw, 680px)">
    <input aria-label="上传获奖佐证" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.zip" :disabled="busy" @change="upload" />
    <el-table :data="attachments">
      <el-table-column prop="name" label="文件名" min-width="150" />
      <el-table-column prop="status" label="审核状态" width="100" />
      <el-table-column prop="note" label="审核意见" min-width="120" />
      <el-table-column label="操作" width="90"><template #default="{ row }"><el-button link type="primary" :disabled="busy" @click="run(() => download(`/files/${row.id}/download`, row.name))">下载</el-button></template></el-table-column>
    </el-table>
  </el-dialog>
</template>
