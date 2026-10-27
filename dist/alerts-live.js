// Живые алерты у врача: опрос /api/alerts, всплывающее оповещение и замер времени доставки.

const alertLive={timer:null,seen:new Set(),queue:[],busy:false};

function alertBeep(){
  try{
    const audio=new (window.AudioContext||window.webkitAudioContext)();
    [0,0.22].forEach(offset=>{const osc=audio.createOscillator(),gain=audio.createGain();osc.frequency.value=880;gain.gain.setValueAtTime(0.0001,audio.currentTime+offset);gain.gain.exponentialRampToValueAtTime(0.25,audio.currentTime+offset+0.02);gain.gain.exponentialRampToValueAtTime(0.0001,audio.currentTime+offset+0.18);osc.connect(gain).connect(audio.destination);osc.start(audio.currentTime+offset);osc.stop(audio.currentTime+offset+0.2)});
  }catch{}
}

function alertOverlay(alert){
  document.querySelector('#alert-live')?.remove();
  const node=document.createElement('div');
  node.id='alert-live';node.className='alert-live';node.setAttribute('role','alertdialog');node.setAttribute('aria-live','assertive');
  const seconds=alert.delivery_seconds;
  const delivered=seconds==null?'':seconds<60?`Доставлено за ${seconds<10?seconds.toFixed(1):Math.round(seconds)} с`:`Сработал ${seconds<3600?Math.round(seconds/60)+' мин':Math.round(seconds/3600)+' ч'} назад, пока вы были не в сети`;
  node.innerHTML=`<div class="alert-live-card ${alert.status==='escalated'?'is-escalated':''}">
    <div class="alert-live-head"><span class="alert-live-pulse">${icon('sos')}</span><div><span class="eyebrow">${alert.status==='escalated'?'Эскалация':'Критический алерт'} · обязательно</span><b>${esc(alert.patient_name)}</b></div><button class="alert-live-close" aria-label="Скрыть">✕</button></div>
    <p>${esc(alert.reason_text)}</p>
    <div class="alert-live-meta">${icon('clock')}<span>${delivered}</span></div>
    <div class="alert-live-actions"><button class="btn btn-danger" data-live-ack="${alert.id}">Принять в работу</button><button class="btn btn-secondary" data-live-open="${alert.patient_id}">Открыть карточку</button></div>
  </div>`;
  document.body.appendChild(node);
  const close=()=>{node.remove();alertLive.busy=false;document.title=alertLive.title||document.title;showNextAlert()};
  node.querySelector('.alert-live-close').onclick=close;
  node.querySelector('[data-live-open]').onclick=async()=>{close();await openPatient(alert.patient_id)};
  node.querySelector('[data-live-ack]').onclick=async event=>{
    event.target.disabled=true;
    try{const saved=await api(`/api/alerts/${alert.id}/acknowledge`,{method:'POST'});toast(`Алерт принят в работу через ${Math.max(1,Math.round(saved.response_seconds))} с`);close();if(state.view==='home')loadState()}
    catch(error){event.target.disabled=false;toast(error.message)}
  };
  alertLive.title=alertLive.title||document.title;
  document.title='⚠ Критический алерт';
  alertBeep();
}

function showNextAlert(){
  if(alertLive.busy||!alertLive.queue.length)return;
  alertLive.busy=true;
  alertOverlay(alertLive.queue.shift());
}

async function pollAlerts(){
  if(state.role!=='doctor'||!window.ccAuth.session)return;
  try{
    const data=await api('/api/alerts');
    state.alerts=data.alerts;state.alertDelivery=data.delivery;
    for(const alert of data.alerts){
      if(alert.status==='acknowledged'||alertLive.seen.has(alert.id))continue;
      alertLive.seen.add(alert.id);
      if(alert.delivered_at)continue;
      const saved=await api(`/api/alerts/${alert.id}/delivered`,{method:'POST'});
      alertLive.queue.push({...alert,...saved});
    }
    showNextAlert();
  }catch{}
}

function startAlertPolling(){
  clearInterval(alertLive.timer);
  if(state.role!=='doctor'||!window.ccAuth.session)return;
  const seconds=state.alerting?.poll_seconds||3;
  pollAlerts();
  alertLive.timer=setInterval(pollAlerts,seconds*1000);
}

const baseLoadStateLive=loadState;
loadState=async function(){
  await baseLoadStateLive();
  if(state.role==='doctor'){if(!alertLive.timer)startAlertPolling()}
  else{clearInterval(alertLive.timer);alertLive.timer=null}
};
['cc-auth-expired','cc-auth-logout'].forEach(name=>window.addEventListener(name,()=>{clearInterval(alertLive.timer);alertLive.timer=null;alertLive.seen.clear();alertLive.queue=[];document.querySelector('#alert-live')?.remove();alertLive.busy=false}));
if(state.role==='doctor'&&window.ccAuth.session)startAlertPolling();
