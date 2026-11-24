<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorMessage } from '../api'
type Project = { id: number; name: string; teacher: string; username: string; college?: string; year: number }
type Row = { id: number; title: string; deleted: boolean; data: {
  score_group: string; basis: string; self_score?: number; audited_score?: number; audit_note?: string
} }
const username = ref('')
const projects = ref<Project[]>([])
const selected = ref<number>()
const rows = ref<Row[]>([])
const editing = ref<Row>()
const score = ref<number>()
const note = ref('')
const busy = ref(false)
const url = () => `/title-applications/${selected.value}/workspace`

async function run(task: () => Promise<void>) {
  busy.value = true
  try { await task() }
  catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}
function search() {
  return run(async () => {
    projects.value = (await api.get('/title-applications/workspace/admin/projects', { params: { username: username.value } })).data
    selected.value = undefined
    rows.value = []
  })
}
async function reload() { rows.value = selected.value ? (await api.get(`${url()}/audit`)).data.rows : [] }
function edit(item: Row) {
  editing.value = item
  score.value = item.data.audited_score
  note.value = item.data.audit_note || ''
}
function save() {
  return run(async () => {
    await api.put(`${url()}/items/${editing.value?.id}/score`, { score: score.value ?? null, note: note.value })
    editing.value = undefined
    await reload()
  })
}
</script>

<template>
  <section class="panel" v-loading="busy">
    <div class="toolbar">
      <el-input v-model.trim="username" placeholder="教师用户名（可留空）" style="width:220px" @keyup.enter="search" />
      <el-button @click="search">查找项目</el-button>
      <el-select v-model="selected" placeholder="选择申报项目" style="width:350px" @change="run(reload)">
        <el-option v-for="project in projects" :key="project.id" :value="project.id"
          :label="`${project.teacher} (${project.username}) · ${project.college || '院系未填'} · ${project.name}`" />
      </el-select>
    </div>
    <el-table :data="rows" empty-text="请选择教师的申报项目">
      <el-table-column prop="title" label="成果" min-width="140" />
      <el-table-column prop="data.score_group" label="计分栏目" min-width="120" />
      <el-table-column prop="data.basis" label="计分依据" min-width="130" />
      <el-table-column prop="data.self_score" label="自评分" width="90" />
      <el-table-column prop="data.audited_score" label="审核分" width="90" />
      <el-table-column label="操作" width="100"><template #default="{ row }"><el-button v-if="!row.deleted" link type="primary" @click="edit(row)">核定分数</el-button></template></el-table-column>
    </el-table>
  </section>
  <el-dialog :model-value="!!editing" :title="editing?.title || '核定分数'" @close="editing = undefined" width="min(95vw, 470px)">
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item label="审核分（留空清除）"><el-input-number v-model="score" :min="0" :max="100" :precision="2" /></el-form-item>
      <el-form-item label="审核意见"><el-input v-model="note" type="textarea" maxlength="500" /></el-form-item>
      <el-button type="primary" native-type="submit" :loading="busy">保存审核分</el-button>
    </el-form>
  </el-dialog>
</template>
