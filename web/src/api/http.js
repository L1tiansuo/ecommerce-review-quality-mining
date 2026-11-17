// 集中处理会话与中文错误，组件无需重复认证逻辑。
import axios from 'axios';import {ElMessage} from 'element-plus';
const http=axios.create({baseURL:'/api/v1',timeout:120000});
http.interceptors.request.use(c=>{const token=localStorage.getItem('qr-token');if(token)c.headers.Authorization=`Bearer ${token}`;return c;});
http.interceptors.response.use(r=>{if(r.config.responseType==='blob')return r.data;if(r.data.code!==0){ElMessage.error(r.data.message);return Promise.reject(new Error(r.data.message));}return r.data.data;},e=>{if(e.response?.status===401){localStorage.removeItem('qr-token');if(location.pathname!='/login')location.assign('/login');}ElMessage.error(e.response?.data?.message||'连接失败，请检查服务后重试');return Promise.reject(e);});export default http;
