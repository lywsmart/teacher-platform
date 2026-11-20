<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, download } from '../api'
const list = ref<any[]>([])
const keyword = ref('')
async function load() { list.value = (await api.get('/files', { params: { keyword: keyword.value } })).data }
const size = (n:number) => n > 1048576 ? (n/1048576).toFixed(1)+' MB' : (n/1024).toFixed(1)+' KB'
onMounted(load)
</script>
<template><div class="panel"><div class="toolbar"><el-input v-model="keyword" placeholder="搜索文件或关联成果" style="width:280px" @keyup.enter="load"/><el-button @click="load">查询</el-button><div class="spacer"/><span class="muted">共 {{list.length}} 份电子材料</span></div><el-table :data="list"><el-table-column prop="original_name" label="文件名"><template #default="s"><b>{{s.row.original_name}}</b><div class="muted">关联：{{s.row.achievement_title}}</div></template></el-table-column><el-table-column prop="year" label="年度"/><el-table-column prop="file_category" label="分类"/><el-table-column label="大小"><template #default="s">{{size(s.row.file_size)}}</template></el-table-column><el-table-column label="操作"><template #default="s"><el-button link type="primary" @click="download(`/files/${s.row.id}/download`,s.row.original_name)">下载</el-button></template></el-table-column></el-table><div v-if="!list.length" class="empty">还没有电子材料。</div></div></template>
