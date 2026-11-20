<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
const options=ref<any>({categories:[],levels:[]}),backups=ref<any[]>([]),busy=ref(false)
async function load(){options.value=(await api.get('/settings/options')).data;backups.value=(await api.get('/backups')).data}
async function backup(){busy.value=true;try{await api.post('/backups');ElMessage.success('完整备份已生成');await load()}finally{busy.value=false}}
onMounted(load)
</script>
<template><el-tabs><el-tab-pane label="成果分类"><div class="panel"><div v-for="x in options.categories" :key="x.name" class="setting-row"><b>{{x.name}}</b><div><el-tag v-for="c in x.children" :key="c">{{c}}</el-tag></div></div></div></el-tab-pane><el-tab-pane label="成果级别"><div class="panel"><el-tag v-for="x in options.levels" :key="x" size="large" style="margin:8px">{{x}}</el-tag></div></el-tab-pane><el-tab-pane label="DeepSeek API"><div class="panel"><el-alert title="API Key 仅通过后端环境变量配置，前端不会读取或显示密钥。" type="info" :closable="false"/></div></el-tab-pane><el-tab-pane label="数据备份"><div class="panel"><div class="panel-title"><h3>数据库与电子材料备份</h3><el-button type="primary" :loading="busy" @click="backup">创建完整备份</el-button></div><el-table :data="backups"><el-table-column prop="file_name" label="备份文件"/><el-table-column prop="file_size" label="大小"/><el-table-column prop="created_at" label="时间"/></el-table></div></el-tab-pane></el-tabs></template>
