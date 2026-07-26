<template>
  <section><div class="header"><h1>请假申请</h1><el-button type="primary" @click="dialog=true">发起请假</el-button></div>
    <el-table :data="items" v-loading="loading" border><el-table-column prop="biz_no" label="单号" min-width="180" /><el-table-column prop="duty_date" label="日期" width="120" /><el-table-column label="类型" width="110"><template #default="{row}">{{ types[row.leave_type] }}</template></el-table-column><el-table-column prop="status" label="审批状态" width="150" /><el-table-column prop="cover_status" label="顶班状态" width="150" /><el-table-column label="操作" width="100"><template #default="{row}"><el-button v-if="row.status==='wait_director_approval'" link @click="withdraw(row.id)">撤回</el-button></template></el-table-column></el-table>
    <el-dialog v-model="dialog" title="发起请假" width="480px"><el-form label-width="90px"><el-form-item label="本人班次"><el-select v-model="form.schedule_shift_id" placeholder="选择已发布班次"><el-option v-for="s in shifts" :key="s.id" :value="s.id" :label="`${s.duty_date} ${s.shift_name}`" /></el-select></el-form-item><el-form-item label="请假类型"><el-select v-model="form.leave_type"><el-option label="公休假" value="public" /><el-option label="事假" value="personal" /><el-option label="病假" value="sick" /></el-select></el-form-item><el-form-item label="原因"><el-input v-model="form.reason" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="submit">提交</el-button></template></el-dialog>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { httpClient, resolveErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
interface Leave {id:number;biz_no:string;duty_date:string;leave_type:string;status:string;cover_status?:string}
interface Shift {id:number;duty_date:string;shift_name:string}
const route=useRoute(); const auth=useAuthStore(); const loading=ref(false); const dialog=ref(Boolean(route.query.source_shift_id)); const items=ref<Leave[]>([]); const shifts=ref<Shift[]>([]); const form=ref({schedule_shift_id:Number(route.query.source_shift_id)||undefined as number|undefined,leave_type:'public',reason:''}); const types:Record<string,string>={public:'公休假',personal:'事假',sick:'病假'}
async function load(){loading.value=true;try{items.value=(await httpClient.get<{items:Leave[]}>('/leaves?view=mine&page_size=100')).data.items}catch(e){ElMessage.error(resolveErrorMessage(e,'加载请假记录失败'))}finally{loading.value=false}}
async function loadShifts(){if(auth.personId) shifts.value=(await httpClient.get<Shift[]>('/leaves/eligible-shifts')).data}
async function submit(){try{await httpClient.post('/leaves',form.value);ElMessage.success('请假申请已提交');dialog.value=false;await load()}catch(e){ElMessage.error(resolveErrorMessage(e,'提交失败'))}}
async function withdraw(id:number){try{await httpClient.post(`/leaves/${id}/withdraw`);ElMessage.success('已撤回');await load()}catch(e){ElMessage.error(resolveErrorMessage(e,'撤回失败'))}}
onMounted(async()=>{await load();await loadShifts()})
</script>
<style scoped>.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.header h1{margin:0}</style>
