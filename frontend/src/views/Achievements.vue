<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, download, errorMessage } from '../api'

type Options = { categories: { name: string; children: string[] }[]; levels: string[]; upload?: { extensions: string[]; max_mb: number } }
type Evidence = { id: number; original_name: string; file_size: number; file_category: string }
type PendingFile = { id: string; file: File; category: string; error?: string; uploaded?: boolean }
const categories = ['证书', '立项或结项文件', '论文或著作', '教学材料', '获奖佐证', '证明或公示', '其他']

const list = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const editing = ref<number | null>(null)
const recordSaved = ref(false)
const dialogMode = ref<'new' | 'edit' | 'evidence'>('new')
const manageOnly = computed(() => dialogMode.value === 'evidence')
const busy = ref(false)
const evidenceLoading = ref(false)
const evidenceError = ref(false)
const evidence = ref<Evidence[]>([])
const pending = ref<PendingFile[]>([])
const evidenceSection = ref<string[]>([])
const options = ref<Options>({ categories: [], levels: [] })
const query = reactive({ page: 1, page_size: 20, keyword: '', year: undefined as number | undefined, achievement_type: '', level: '' })
const blank = () => ({
  achievement_type: '教学成果', category: '课程建设', title: '', year: new Date().getFullYear(),
  achievement_date: null, level: '', rank: null, role: '', organization: '',
  certificate_no: '', score: 0, description: '', remark: '',
})
const form = reactive<any>(blank())
const upload = computed(() => options.value.upload)
const dialogTitle = computed(() => ({ new: '新增成果', edit: '编辑成果', evidence: '管理佐证' })[dialogMode.value])

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/achievements', { params: query })
    list.value = data.items
    total.value = data.total
  } catch { ElMessage.error('成果列表加载失败') }
  finally { loading.value = false }
}

async function loadEvidence(id: number) {
  evidenceLoading.value = true
  evidenceError.value = false
  try {
    const { data } = await api.get('/files', { params: { achievement_id: id } })
    if (editing.value === id) evidence.value = data
  } catch {
    if (editing.value === id) evidenceError.value = true
  } finally {
    evidenceLoading.value = false
  }
}

function open(row?: any, onlyEvidence = false) {
  Object.assign(form, blank(), row)
  editing.value = row?.id ?? null
  recordSaved.value = false
  dialogMode.value = onlyEvidence ? 'evidence' : row ? 'edit' : 'new'
  evidence.value = []
  evidenceError.value = false
  pending.value = []
  evidenceSection.value = onlyEvidence ? ['evidence'] : []
  dialog.value = true
  if (row) void loadEvidence(row.id)
}

function add() { open() }
function edit(row: any) { open(row) }
function manage(row: any) { open(row, true) }

function selectFiles(event: Event) {
  const input = event.target as HTMLInputElement
  if (!upload.value) return
  const rejected: string[] = []
  for (const file of Array.from(input.files || [])) {
    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!file.size || file.size > upload.value.max_mb * 1024 * 1024 || !upload.value.extensions.includes(extension)) {
      rejected.push(file.name)
      continue
    }
    const random = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')
    const id = [random.slice(0, 8), random.slice(8, 12), random.slice(12, 16), random.slice(16, 20), random.slice(20)].join('-')
    pending.value.push({ id, file, category: '其他' })
  }
  if (rejected.length) ElMessage.warning({ message: `文件为空、格式不支持或超过大小限制：${rejected.join('、')}`, showClose: true })
  input.value = ''
}

async function save() {
  if (busy.value || evidenceLoading.value) return
  if (!manageOnly.value && !recordSaved.value && (!form.title.trim() || !form.achievement_type || !form.category || !form.year)) {
    ElMessage.warning('请填写成果名称、类型、二级分类和年度')
    return
  }
  busy.value = true
  try {
    let id = editing.value
    if (!manageOnly.value && !recordSaved.value) {
      const values = { ...form, title: form.title.trim() }
      const { data } = id === null
        ? await api.post('/achievements', values)
        : await api.put(`/achievements/${id}`, values)
      id = data.id as number
      editing.value = id
      recordSaved.value = true
      void load()
    }
    if (id === null) return
    const files = pending.value.filter(item => !item.uploaded)
    for (const item of files) {
      item.error = undefined
      try {
        const data = new FormData()
        data.append('file', item.file)
        data.append('file_category', item.category)
        data.append('upload_id', item.id)
        await api.post(`/achievements/${id}/files`, data, { timeout: 300000 })
        item.uploaded = true
      } catch (error) { item.error = errorMessage(error) }
    }
    if (files.length) await loadEvidence(id)
    if (pending.value.some(item => item.error)) {
      evidenceSection.value = ['evidence']
      if (recordSaved.value) ElMessage.warning('成果已保存，部分佐证上传失败，可重试')
      return
    }
    if (manageOnly.value) {
      pending.value = []
      ElMessage.success('佐证材料已上传')
      return
    }
    ElMessage.success(files.length ? '成果和佐证材料已保存' : '成果已保存')
    dialog.value = false
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}

async function close(done?: () => void) {
  if (busy.value || evidenceLoading.value) return
  if (pending.value.some(item => !item.uploaded)) {
    try {
      await ElMessageBox.confirm('尚未上传的文件将从本次列表移除。', '关闭窗口', { type: 'warning' })
    } catch { return }
  }
  if (done) done()
  else dialog.value = false
}

async function downloadEvidence(file: Evidence) {
  try { await download(`/files/${file.id}/download`, file.original_name) }
  catch (error) { ElMessage.error(errorMessage(error)) }
}

async function remove(row: any) {
  try { await ElMessageBox.confirm(`确认删除“${row.title}”？`, '删除成果', { type: 'warning' }) }
  catch { return }
  try {
    await api.delete(`/achievements/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (error) { ElMessage.error(errorMessage(error)) }
}

async function copy(row: any) {
  try {
    await api.post(`/achievements/${row.id}/copy`)
    ElMessage.success('已创建副本')
    await load()
  } catch (error) { ElMessage.error(errorMessage(error)) }
}

onMounted(async () => {
  void load()
  try { options.value = (await api.get('/settings/options')).data }
  catch (error) { ElMessage.error(errorMessage(error)) }
})
</script>
<template><div class="panel"><div class="toolbar"><el-input v-model="query.keyword" clearable placeholder="搜索成果名称、单位或描述" style="width:260px" @keyup.enter="load"/><el-input-number v-model="query.year" :controls="false" placeholder="年度" style="width:110px"/><el-select v-model="query.achievement_type" clearable placeholder="成果类型" style="width:150px"><el-option v-for="x in options.categories" :key="x.name" :label="x.name" :value="x.name"/></el-select><el-select v-model="query.level" clearable placeholder="级别" style="width:130px"><el-option v-for="x in options.levels" :key="x" :value="x"/></el-select><el-button @click="query.page=1;load()">查询</el-button><div class="spacer"></div><el-button @click="download('/achievements/export/excel','成果清单.xlsx')">导出 Excel</el-button><el-button type="primary" @click="add">+ 新增成果</el-button></div><el-table v-loading="loading" :data="list" stripe><el-table-column prop="title" label="成果名称" min-width="280"><template #default="s"><b>{{s.row.title}}</b><div class="muted">{{s.row.category}}</div></template></el-table-column><el-table-column prop="achievement_type" label="类型" width="120"><template #default="s"><el-tag effect="plain">{{s.row.achievement_type}}</el-tag></template></el-table-column><el-table-column prop="year" label="年度" width="85"/><el-table-column prop="level" label="级别" width="105"/><el-table-column prop="rank" label="排名" width="75"><template #default="s">{{s.row.rank?'第 '+s.row.rank:'—'}}</template></el-table-column><el-table-column prop="score" label="积分" width="75"/><el-table-column label="操作" width="255" fixed="right"><template #default="s"><el-button link type="primary" @click="edit(s.row)">编辑</el-button><el-button link type="primary" @click="manage(s.row)">管理佐证</el-button><el-button link @click="copy(s.row)">复制</el-button><el-button link type="danger" @click="remove(s.row)">删除</el-button></template></el-table-column></el-table><div style="display:flex;justify-content:flex-end;margin-top:18px"><el-pagination v-model:current-page="query.page" :total="total" :page-size="query.page_size" layout="total, prev, pager, next" @change="load"/></div></div>
  <el-dialog v-model="dialog" :title="dialogTitle" width="min(840px, 94vw)"
    :before-close="close" :close-on-click-modal="false" :close-on-press-escape="!busy">
    <p v-if="manageOnly" class="evidence-title">{{ form.title }}</p><el-form v-if="!manageOnly" :model="form" label-width="95" :disabled="busy || recordSaved"><div class="grid-2"><el-form-item label="成果类型" required><el-select v-model="form.achievement_type" @change="form.category=options.categories.find((x:any)=>x.name===form.achievement_type)?.children[0]||''"><el-option v-for="x in options.categories" :key="x.name" :value="x.name"/></el-select></el-form-item><el-form-item label="二级分类" required><el-select v-model="form.category"><el-option v-for="x in options.categories.find((x:any)=>x.name===form.achievement_type)?.children||[]" :key="x" :value="x"/></el-select></el-form-item></div><el-form-item label="成果名称" required><el-input v-model="form.title"/></el-form-item><div class="grid-2"><el-form-item label="年度" required><el-input-number v-model="form.year" :min="1950" :max="2200"/></el-form-item><el-form-item label="成果日期"><el-date-picker v-model="form.achievement_date" value-format="YYYY-MM-DD"/></el-form-item><el-form-item label="成果级别"><el-select v-model="form.level" clearable><el-option v-for="x in options.levels" :key="x" :value="x"/></el-select></el-form-item><el-form-item label="本人排名"><el-input-number v-model="form.rank" :min="1"/></el-form-item><el-form-item label="角色"><el-input v-model="form.role"/></el-form-item><el-form-item label="积分"><el-input-number v-model="form.score" :precision="1"/></el-form-item></div><el-form-item label="组织单位"><el-input v-model="form.organization"/></el-form-item><el-form-item label="证书编号"><el-input v-model="form.certificate_no"/></el-form-item><el-form-item label="成果描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item><el-form-item label="备注"><el-input v-model="form.remark"/></el-form-item></el-form>
    <el-collapse v-model="evidenceSection">
      <el-collapse-item name="evidence" title="电子佐证材料（选填）">
        <div class="evidence" v-loading="evidenceLoading">
          <div v-if="evidenceError" class="evidence-row">
            <span>佐证列表加载失败</span>
            <el-button link type="primary" v-if="editing !== null" @click="loadEvidence(editing)">重新加载</el-button>
          </div>
          <div v-for="file in evidence" :key="file.id" class="evidence-row">
            <span class="evidence-name">{{ file.original_name }}</span>
            <el-tag effect="plain">{{ file.file_category }}</el-tag>
            <span class="muted">{{ (file.file_size / 1024).toFixed(1) }} KB</span>
            <el-button link type="primary" @click="downloadEvidence(file)">下载</el-button>
          </div>
          <label v-if="upload" class="file-picker">
            <span class="muted">支持 {{ upload.extensions.map(ext => ext.slice(1).toUpperCase()).join('、') }}，单个文件最多 {{ upload.max_mb }} MB。</span>
            <input type="file" multiple :accept="upload.extensions.join(',')" :disabled="busy" @change="selectFiles">
          </label>
          <el-alert v-else title="上传规则暂不可用，请刷新页面重试。" type="info" :closable="false" />
          <div v-for="(item, index) in pending" :key="item.id" class="evidence-row pending-evidence">
            <span class="evidence-name">{{ item.file.name }}</span>
            <el-select v-model="item.category" aria-label="佐证类别" :disabled="busy || item.uploaded || Boolean(item.error)">
              <el-option v-for="category in categories" :key="category" :value="category" />
            </el-select>
            <el-tag v-if="item.uploaded" type="success">已上传</el-tag>
            <el-button v-else link :disabled="busy" @click="pending.splice(index, 1)">移除</el-button>
            <span v-if="item.error" class="evidence-error" role="status">{{ item.error }}</span>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
    <template #footer>
      <el-button :disabled="busy || evidenceLoading" @click="close()">{{ recordSaved || manageOnly ? '关闭' : '取消' }}</el-button>
      <el-button type="primary" :loading="busy" :disabled="evidenceLoading || ((manageOnly || recordSaved) && !pending.some(item => !item.uploaded))" @click="save">
        {{ pending.some(item => item.error) ? '重试失败文件' : manageOnly || recordSaved ? '上传佐证' : '保存成果' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.evidence { display: grid; gap: 8px; }
.evidence-title { margin-top: 0; font-weight: 600; }
.evidence-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 8px 12px; background: #f4f8ff; border-radius: 8px; }
.evidence-name { flex: 1 1 180px; min-width: 0; overflow-wrap: anywhere; }
.pending-evidence .el-select { width: 146px; }
.evidence-error { flex: 0 0 100%; color: #b52c32; }
.file-picker { display: grid; gap: 8px; padding: 8px 0; }
.file-picker input { max-width: 100%; }
.file-picker input::file-selector-button { padding: 6px 10px; border: 1px solid #b6cdee; border-radius: 6px; color: #134789; background: #edf5ff; cursor: pointer; }
</style>
