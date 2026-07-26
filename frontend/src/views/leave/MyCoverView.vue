<template><section><h1>我的顶班</h1><el-table :data="items" v-loading="loading" border><el-table-column prop="biz_no" label="顶班单号" min-width="180"/><el-table-column prop="applicant_name" label="原值机员"/><el-table-column prop="duty_date" label="日期"/><el-table-column prop="status" label="状态"/><el-table-column label="操作"><template #default="{row}"><el-button v-if="row.status==='wait_cover_confirm'" link type="primary" @click="act(row.id,true)">确认</el-button><el-button v-if="row.status==='wait_cover_confirm'" link type="danger" @click="act(row.id,false)">拒绝</el-button></template></el-table-column></el-table></section></template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { httpClient, resolveErrorMessage } from '@/services/http'
interface Cover { id: number; biz_no: string; applicant_name: string; duty_date: string; status: string }
const items = ref<Cover[]>([]); const loading = ref(false)
async function load() { loading.value = true; try { items.value = (await httpClient.get<{items: Cover[]}>('/cover-assignments/mine?page_size=100')).data.items } catch (e) { ElMessage.error(resolveErrorMessage(e, '加载顶班任务失败')) } finally { loading.value = false } }
async function act(id: number, yes: boolean) { try { let opinion = ''; if (!yes) opinion = (await ElMessageBox.prompt('请填写拒绝原因', '拒绝顶班', { inputValidator: v => !!v || '拒绝原因必填' })).value; await httpClient.post(`/cover-assignments/${id}/${yes ? 'confirm' : 'reject'}`, { opinion }); ElMessage.success('操作成功'); await load() } catch (e) { if (e !== 'cancel') ElMessage.error(resolveErrorMessage(e, '操作失败')) } }
onMounted(load)
</script>
