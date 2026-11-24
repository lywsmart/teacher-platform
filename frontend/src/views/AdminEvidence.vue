<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, download, errorMessage } from '../api'

type Evidence = {
  id: number; kind: string; filename: string; category: string; parent: string
  username: string; teacher: string; status: string; note: string
}
const kind = ref('achievement')
const owner = ref('')
const rows = ref<Evidence[]>([])
const next = ref<number | null>(null)
const loading = ref(false)
const selected = ref<Evidence>()
const form = reactive({ status: '待审核', note: '' })
const saving = ref(false)
const url = (item: Evidence) => `/admin/evidence/${item.kind}/${item.id}`

async function load(before = 0) {
  loading.value = true
  try {
    const { data } = await api.get('/admin/evidence', { params: { kind: kind.value, owner: owner.value, before } })
    rows.value = before ? [...rows.value, ...data.items] : data.items
    next.value = data.next
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { loading.value = false }
}
function open(item: Evidence) {
  selected.value = item
  Object.assign(form, { status: item.status, note: item.note })
}
async function save() {
  const item = selected.value
  if (!item) return
  saving.value = true
  try {
    Object.assign(item, (await api.put(url(item), form)).data)
    selected.value = undefined
    ElMessage.success('审核意见已保存')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { saving.value = false }
}
async function view(item: Evidence) {
  try { await download(`${url(item)}/download`, item.filename) }
  catch (error) { ElMessage.error(errorMessage(error)) }
}
onMounted(() => load())
</script>

<template>
  <section class="panel">
    <div class="toolbar">
      <el-select v-model="kind" aria-label="材料来源" style="width:170px" :disabled="loading" @change="load()">
        <el-option label="成果附件" value="achievement" />
        <el-option label="申报项目材料" value="application" />
      </el-select>
      <el-input v-model.trim="owner" placeholder="教师用户名" style="width:180px" @keyup.enter="load()" />
      <el-button :loading="loading" @click="load()">查询</el-button>
    </div>
    <el-table v-loading="loading" :data="rows">
      <el-table-column prop="teacher" label="教师" width="120" />
      <el-table-column prop="parent" label="所属成果／申报" min-width="155" />
      <el-table-column prop="filename" label="文件名" min-width="185" />
      <el-table-column prop="category" label="材料类别" width="130" />
      <el-table-column prop="status" label="审核状态" width="110" />
      <el-table-column prop="note" label="审核意见" min-width="140" />
      <el-table-column label="操作" width="125">
        <template #default="{ row }">
          <el-button link type="primary" @click="view(row)">下载</el-button>
          <el-button link type="primary" @click="open(row)">审核</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-button v-if="next" :loading="loading" @click="load(next)">加载更多</el-button>
  </section>
  <el-dialog :model-value="!!selected" :title="selected?.filename || '审核佐证'" width="min(92vw, 520px)" @close="selected = undefined">
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item label="审核状态">
        <el-select v-model="form.status"><el-option v-for="state in ['待审核', '通过', '需补充']" :key="state" :value="state" /></el-select>
      </el-form-item>
      <el-form-item label="审核意见"><el-input v-model="form.note" type="textarea" maxlength="500" show-word-limit /></el-form-item>
      <el-button type="primary" native-type="submit" :loading="saving">保存审核</el-button>
    </el-form>
  </el-dialog>
</template>
