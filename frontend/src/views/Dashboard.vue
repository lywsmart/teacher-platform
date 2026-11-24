<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Plus } from '@element-plus/icons-vue'
import { api, errorMessage } from '../api'
type Project = { id: number; name: string; year: number; target_title: string; incomplete: number; waiting: number; returned: number }
const projects = ref<Project[]>([])
const ready = ref(false)
onMounted(async () => {
  try {
    projects.value = (await api.get('/title-applications/workspace/overview')).data
    ready.value = true
  } catch (error) { ElMessage.error(errorMessage(error)) }
})
</script>

<template>
  <section class="panel">
    <div class="panel-title dashboard-heading">
      <h3>申报待办</h3>
      <router-link class="action-button" to="/achievements">
        进入成果库 <el-icon aria-hidden="true"><ArrowRight /></el-icon>
      </router-link>
    </div>
    <el-table v-if="projects.length" :data="projects">
      <el-table-column prop="name" label="申报项目" min-width="150" />
      <el-table-column prop="target_title" label="目标职称" min-width="110" />
      <el-table-column prop="incomplete" label="有待办的成果" min-width="110" />
      <el-table-column prop="waiting" label="待审核文件" min-width="110" />
      <el-table-column prop="returned" label="需补充文件" min-width="110" />
      <el-table-column label="操作" min-width="122">
        <template #default="{ row }">
          <router-link class="action-button action-button--compact" :to="{ path: '/titles', query: { project: row.id } }">
            继续申报 <el-icon aria-hidden="true"><ArrowRight /></el-icon>
          </router-link>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else-if="ready" description="暂无申报项目">
      <router-link class="action-button action-button--primary" :to="{ path: '/titles', query: { new: '1' } }">
        <el-icon aria-hidden="true"><Plus /></el-icon> 创建申报项目
      </router-link>
    </el-empty>
  </section>
</template>

<style scoped>
.dashboard-heading { gap: 12px; flex-wrap: wrap; }
</style>
