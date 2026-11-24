<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MoreFilled } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '../api'
import ProjectWorkspace from './ProjectWorkspace.vue'

type Project = { id: number; name: string; year: number; target_title: string; status: string }
type DeletedProject = Omit<Project, 'status'> & { deleted_at: string }
type DeletionImpact = { materials: number; exports: number }
const projects = ref<Project[]>([])
const selected = ref<Project>()
const dialog = ref(false)
const busy = ref(false)
const loading = ref(true)
const recentOpen = ref(false)
const recentLoading = ref(false)
const recentError = ref(false)
const recent = ref<DeletedProject[]>([])
const pendingDeletion = ref<Project>()
const impact = ref<DeletionImpact>()
const confirmOpen = ref(false)
const operationBusy = ref(false)
const restoring = ref<number>()
const route = useRoute()
const router = useRouter()
const form = reactive({ name: '', year: new Date().getFullYear(), target_title: '副教授', status: '准备中' })
const deletionDate = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })

watch(() => route.query.new, value => {
  if (value !== '1') return
  dialog.value = true
  void router.replace({ query: { ...route.query, new: undefined } })
}, { immediate: true })

onMounted(async () => {
  try {
    projects.value = (await api.get('/title-applications')).data
    selected.value = projects.value.find(project => String(project.id) === route.query.project) || projects.value[0]
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { loading.value = false }
})

async function create() {
  if (busy.value || !form.name.trim() || !form.year) return
  busy.value = true
  try {
    const { data } = await api.post('/title-applications', form)
    projects.value.unshift(data)
    selected.value = data
    dialog.value = false
    form.name = ''
    ElMessage.success('申报项目已创建')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}

async function confirmDeletion() {
  if (!selected.value || operationBusy.value) return
  const project = selected.value
  operationBusy.value = true
  try {
    const { data } = await api.get(`/title-applications/${project.id}/deletion-impact`)
    pendingDeletion.value = project
    impact.value = data
    confirmOpen.value = true
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { operationBusy.value = false }
}

async function removeProject() {
  if (!pendingDeletion.value || operationBusy.value) return
  const id = pendingDeletion.value.id
  operationBusy.value = true
  try {
    await api.delete(`/title-applications/${id}`)
    projects.value = projects.value.filter(project => project.id !== id)
    if (selected.value?.id === id) selected.value = projects.value[0]
    confirmOpen.value = false
    ElMessage.success('项目已移入「最近删除」')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { operationBusy.value = false }
}

async function showRecent() {
  recentOpen.value = true
  recentLoading.value = true
  recentError.value = false
  try { recent.value = (await api.get('/title-applications', { params: { deleted: true } })).data }
  catch (error) {
    recentError.value = true
    ElMessage.error(errorMessage(error))
  } finally { recentLoading.value = false }
}

async function restore(project: DeletedProject) {
  if (restoring.value !== undefined) return
  restoring.value = project.id
  try {
    const { data } = await api.post(`/title-applications/${project.id}/restore`)
    projects.value = [data, ...projects.value.filter(item => item.id !== project.id)]
    selected.value = data
    recent.value = recent.value.filter(item => item.id !== project.id)
    recentOpen.value = false
    ElMessage.success('项目已恢复')
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { restoring.value = undefined }
}
</script>

<template>
  <div class="toolbar">
    <el-select :model-value="selected?.id" aria-label="申报项目" placeholder="选择申报项目"
      class="project-select" :loading="loading" :disabled="operationBusy"
      @change="(id: number) => selected = projects.find(project => project.id === id)">
      <el-option v-for="project in projects" :key="project.id" :value="project.id"
        :label="`${project.name} · ${project.year} 年 · ${project.target_title}`" />
    </el-select>
    <el-button type="primary" @click="dialog = true">新建申报项目</el-button>
    <el-button plain @click="showRecent">最近删除</el-button>
  </div>
  <ProjectWorkspace v-if="selected" :key="selected.id" :project="selected">
    <template #actions>
      <el-dropdown trigger="click" @command="confirmDeletion">
        <el-button :icon="MoreFilled" :loading="operationBusy">更多操作</el-button>
        <template #dropdown>
          <el-dropdown-menu><el-dropdown-item command="delete"><span class="danger-action">删除项目</span></el-dropdown-item></el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>
  </ProjectWorkspace>
  <el-empty v-else-if="!loading" description="创建申报项目后，可从成果库选入成果并准备佐证。" />
  <el-dialog v-model="dialog" title="新建申报项目" width="min(92vw, 520px)">
    <el-form label-position="top" @submit.prevent="create">
      <el-form-item label="项目名称"><el-input v-model.trim="form.name" maxlength="128" /></el-form-item>
      <el-form-item label="申报年度"><el-input-number v-model="form.year" :min="2000" :max="2100" /></el-form-item>
      <el-form-item label="目标职称">
        <el-select v-model="form.target_title">
          <el-option v-for="title in ['教授', '副教授', '讲师', '助教']" :key="title" :value="title" />
        </el-select>
      </el-form-item>
      <el-button type="primary" native-type="submit" :disabled="!form.name || !form.year" :loading="busy">创建</el-button>
    </el-form>
  </el-dialog>
  <el-dialog v-model="confirmOpen" title="删除申报项目" width="min(92vw, 500px)"
    :show-close="!operationBusy" :close-on-click-modal="false" :close-on-press-escape="!operationBusy">
    <p v-if="pendingDeletion"><strong>{{ pendingDeletion.name }}</strong> · {{ pendingDeletion.year }} 年 · {{ pendingDeletion.target_title }}</p>
    <p v-if="impact">项目内有 {{ impact.materials }} 份直接上传的材料、{{ impact.exports }} 个导出记录。</p>
    <p>项目将移入「最近删除」。恢复项目时会一并找回这些材料和导出记录。成果库里的原始成果和佐证继续保留。</p>
    <template #footer>
      <el-button :disabled="operationBusy" @click="confirmOpen = false">取消</el-button>
      <el-button type="danger" :loading="operationBusy" @click="removeProject">确认删除</el-button>
    </template>
  </el-dialog>
  <el-dialog v-model="recentOpen" title="最近删除的申报项目" width="min(92vw, 720px)"
    :show-close="restoring === undefined" :close-on-click-modal="false" :close-on-press-escape="restoring === undefined">
    <div v-if="recentError">
      <p>最近删除列表加载失败。</p>
      <el-button @click="showRecent">重新加载</el-button>
    </div>
    <el-table v-else v-loading="recentLoading" :data="recent" empty-text="没有已删除的项目">
      <el-table-column prop="name" label="项目名称" min-width="150" />
      <el-table-column prop="year" label="年度" width="82" />
      <el-table-column prop="target_title" label="目标职称" width="100" />
      <el-table-column label="删除时间" min-width="160">
        <template #default="{ row }">{{ deletionDate.format(new Date(row.deleted_at)) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="82">
        <template #default="{ row }">
          <el-button link type="primary" :loading="restoring === row.id" :disabled="restoring !== undefined" @click="restore(row)">恢复</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>

<style scoped>
.project-select { width: min(100%, 360px); }
.danger-action { color: #b4232c; }
</style>
