import axios from 'axios'
export function errorMessage(error: unknown) {
  if (axios.isAxiosError(error) && error.response?.status === 413) return '文件超过服务器允许的大小'
  const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined
  return typeof detail === 'string' ? detail : '操作失败，请检查输入或稍后重试'
}
export const api = axios.create({baseURL:'/api/v1',timeout:60000})
api.interceptors.request.use(config=>{const token=localStorage.getItem('token');if(token) config.headers.Authorization=`Bearer ${token}`;return config})
export function clearSession() {
  localStorage.removeItem('token')
  localStorage.removeItem('password_change_required')
}
api.interceptors.response.use(r=>r,err=>{if(err.response?.status===401&&location.pathname!=='/login'){clearSession();location.href='/login'}return Promise.reject(err)})
export const download = async(url:string,name:string)=>{const {data}=await api.get(url,{responseType:'blob'});const href=URL.createObjectURL(data);const a=document.createElement('a');a.href=href;a.download=name;a.click();URL.revokeObjectURL(href)}
