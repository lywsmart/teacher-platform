<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { api, errorMessage } from '../api'
import ProjectWorkspace from './ProjectWorkspace.vue'

type Project = { id: number; name: string; year: number; target_title: string; status: string }
const projects = ref<Project[]>([])
const selected = ref<Project>()
const dialog = ref(false)
const busy = ref(false)
const route = useRoute()
const form = reactive({ name: '', year: new Date().getFullYear(), target_title: '副教授', status: '准备中' })

onMounted(async () => {
  try {
    projects.value = (await api.get('/title-applications')).data
    selected.value = projects.value.find(project => String(project.id) === route.query.project) || projects.value[0]
  } catch (error) { ElMessage.error(errorMessage(error)) }
})

async function create() {
  busy.value = true
  try {
    const { data } = await api.post('/title-applications', form)
    projects.value.unshift(data)
    selected.value = data
    dialog.value = false
    form.name = ''
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busy.value = false }
}
</script>

<template>
  <div class="toolbar">
    <el-select :model-value="selected?.id" placeholder="选择申报项目" style="width:320px"
      @change="(id: number) => selected = projects.find(project => project.id === id)">
      <el-option v-for="project in projects" :key="project.id" :value="project.id" :label="project.name" />
    </el-select>
    <el-button type="primary" @click="dialog = true">新建申报项目</el-button>
  </div>
  <ProjectWorkspace v-if="selected" :key="selected.id" :project="selected" />
  <el-empty v-else description="创建申报项目后，可从成果库选入成果并准备佐证。" />
  <el-dialog v-model="dialog" title="新建申报项目" width="min(92vw, 520px)">
    <el-form label-position="top" @submit.prevent="create">
      <el-form-item label="项目名称"><el-input v-model.trim="form.name" maxlength="128" /></el-form-item>
      <el-form-item label="申报年度"><el-input-number v-model="form.year" :min="2000" :max="2100" /></el-form-item>
      <el-form-item label="目标职称">
        <el-select v-model="form.target_title">
          <el-option v-for="title in ['教授', '副教授', '讲师', '助教']" :key="title" :value="title" />
        </el-select>
      </el-form-item>
      <el-button type="primary" native-type="submit" :disabled="!form.name" :loading="busy">创建</el-button>
    </el-form>
  </el-dialog>
</template>
