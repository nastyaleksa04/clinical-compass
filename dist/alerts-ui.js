function alertElapsed(alert){
  if(alert.response_seconds!=null)return Math.max(1,Math.round(alert.response_seconds))+' сек до реакции';
  const seconds=Math.max(0,(Date.now()-new Date(alert.triggered_at).getTime())/1000);
  return seconds<60?Math.round(seconds)+' сек':Math.round(seconds/60)+' мин';
}
function alertsBlock(){
  const alerts=(state.alerts||[]).filter(item=>item.status!=='acknowledged');
  if(!alerts.length)return '';
  return `<section class="alert-center"><div class="section-head"><h2>Критические алерты</h2><span class="badge badge-danger">${alerts.length} активных</span></div>${alerts.map(alert=>`<article class="critical-alert alert-${alert.status}"><div class="alert-pulse">!</div><div><div class="alert-meta"><span>${alert.status==='escalated'?'Эскалировано дежурному':'Новый алерт'}</span><time>${alertElapsed(alert)}</time></div><h3>${esc(alert.patient_name)}</h3><p>${esc(alert.reason_text)}</p><small>Система показала пациенту экстренную инструкцию и уведомила врача.</small><div class="route-actions"><button class="btn btn-primary" data-alert-ack="${alert.id}">${icon('check')} Принять в работу</button><button class="btn btn-ghost" data-patient="${alert.patient_id}">Открыть карточку</button></div></div></article>`).join('')}</section>`;
}
const baseDoctorHomeAlerts=doctorHome;
doctorHome=function(){
  let html=baseDoctorHomeAlerts();
  const block=alertsBlock();
  return block?html.replace('<div class="doctor-stats">',block+'<div class="doctor-stats">'):html;
}
const baseBindAlerts=bind;
bind=function(){
  baseBindAlerts();
  document.querySelectorAll('[data-alert-ack]').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;
    try{
      const saved=await api(`/api/alerts/${button.dataset.alertAck}/acknowledge`,{method:'POST'});
      await loadState();toast(`Алерт принят · реакция ${Math.max(1,Math.round(saved.response_seconds))} сек`);
    }catch(error){button.disabled=false;toast(error.message)}
  }));
}
