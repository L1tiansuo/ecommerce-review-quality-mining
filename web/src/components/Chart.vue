<script setup>
// 图表跟随容器尺寸变化；销毁实例与观察器，防止切页泄漏。
import {ref,onMounted,onBeforeUnmount,watch} from 'vue';import * as echarts from 'echarts';const props=defineProps({option:Object});const emit=defineEmits(['select']);const root=ref();let chart,observer;onMounted(()=>{chart=echarts.init(root.value);chart.setOption(props.option||{});chart.on('click',e=>emit('select',e));observer=new ResizeObserver(()=>chart.resize());observer.observe(root.value);});watch(()=>props.option,v=>chart?.setOption(v||{},true),{deep:true});onBeforeUnmount(()=>{observer?.disconnect();chart?.dispose();});
</script><template><div ref="root" class="chart"></div></template>
