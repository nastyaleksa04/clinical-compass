state.checkins=[];
state.adherence={total:0,taken:0,missed:0,percent:null,adverse_events:0,severe_events:0};
state.routingSignals=[];
state.tasks=[];
state.alerts=[];
state.scenario=null;
state.clinicalProfile=null;
state.timeline=[];
state.therapyDecisions=[];
state.recommendations=null;state.aiSummaries=[];

async function loadState(){
  state.loading=true;state.error=null;render();
  try{
    const [data,catalogue]=await Promise.all([api('/api/state'),api('/api/scales')]);
    state.scales=catalogue.scales;
    if(state.role==='patient'){
      state.patient=data.patient;state.currentPatient=data.patient;state.reports=data.reports;
      state.assessments=data.assessments;state.plan=data.plan;state.patients=[];
      state.checkins=data.checkins||[];state.adherence=data.adherence||{};
      state.routingSignals=data.routing_signals||[];state.tasks=data.tasks||[];state.unreadMessages=data.unread_messages||0;
      state.profile=data.profile||null;state.scenario=data.scenario||null;state.clinicalProfile=data.clinical_profile||null;state.timeline=data.timeline||[];state.therapyDecisions=data.therapy_decisions||[];state.recommendations=data.recommendations||null;state.aiSummaries=data.ai_summaries||[];
    }else{
      state.patients=data.patients;state.alerts=data.alerts||[];state.alerting=data.alerting||null;state.patient=null;state.currentPatient=null;
      state.reports=[];state.assessments=[];state.plan=null;state.checkins=[];
      state.adherence={};state.routingSignals=[];state.tasks=[];state.unreadMessages=0;state.scenario=null;state.clinicalProfile=null;state.timeline=[];state.therapyDecisions=[];state.recommendations=null;state.aiSummaries=[];
    }
    state.loading=false;render();
  }catch(error){state.loading=false;state.error=error.message;render()}
}

async function openPatient(id){
  state.loading=true;state.view='patient';render();
  try{
    const data=await api(`/api/patients/${id}`);
    state.currentPatient=data.patient;state.reports=data.reports;state.assessments=data.assessments;
    state.plan=data.plan;state.checkins=data.checkins||[];state.adherence=data.adherence||{};
    state.routingSignals=data.routing_signals||[];state.tasks=data.tasks||[];state.currentProfile=data.profile||null;state.scenario=data.scenario||null;state.clinicalProfile=data.clinical_profile||null;state.timeline=data.timeline||[];state.therapyDecisions=data.therapy_decisions||[];state.recommendations=data.recommendations||null;state.aiSummaries=data.ai_summaries||[];
    await api(`/api/patients/${id}/review`,{method:'POST'});
    state.loading=false;render();
  }catch(error){state.loading=false;state.error=error.message;render()}
}

function adherenceBlock(){
  const a=state.adherence||{};
  const percent=a.percent===null||a.percent===undefined?'—':a.percent+'%';
  return `<div class="adherence-gauge"><div class="gauge-value">${percent}</div><div><b>Приверженность по отметкам</b><p>${a.total||0} отметок · принято ${a.taken||0} · пропущено ${a.missed||0}</p></div></div>
  <div class="metric-row"><div class="metric"><b>${a.taken||0}</b><span>принято</span></div><div class="metric"><b>${a.missed||0}</b><span>пропущено</span></div><div class="metric ${a.severe_events?'metric-danger':''}"><b>${a.adverse_events||0}</b><span>реакций</span></div></div>`;
}

function checkinHistory(){
  if(!state.checkins.length)return '<div class="empty compact"><p>Отметок о терапии пока нет.</p></div>';
  const severity={none:'Нет реакции',mild:'Лёгкая',moderate:'Умеренная',severe:'Выраженная'};
  return `<div class="checkin-list">${state.checkins.slice(0,8).map(item=>`<div class="checkin-item ${item.side_effect_severity==='severe'?'is-severe':''}"><span class="check-status">${item.taken?'✓':'—'}</span><div><b>${item.taken?'Терапия принята':'Приём пропущен'}</b><p>${fmtDate(item.created_at)} · ${severity[item.side_effect_severity]}</p>${item.side_effect?`<small>${esc(item.side_effect)}</small>`:''}</div></div>`).join('')}</div>`;
}

const basePlanView=planView;
planView=function(){
  if(state.role==='doctor')return basePlanView();
  const plan=state.plan;
  const route=state.routingSignals[0];
  return shell(`<div class="page-head"><h2>Мой план и терапия</h2><p>Назначения врача и ежедневная отметка приёма</p></div>
  ${route?`<article class="routing-card route-${route.level}"><span class="route-label">${route.level==='mandatory'?'Обязательно':'Желательно'}</span><h3>Маршрутизация подтверждена врачом</h3><p>${esc(route.reason_text)}</p>${route.decision_comment?`<small>${esc(route.decision_comment)}</small>`:''}</article>`:''}
  ${plan?`<article class="card plan-preview"><div class="section-head"><h3>План подтверждён</h3><span class="badge badge-new">Актуально</span></div><p>${esc(plan.text)}</p><div class="notice notice-success">${icon('check')} Подтверждено врачом · ${fmtDate(plan.created_at)}</div></article>`:`<article class="card empty compact"><h3>План ещё не готов</h3><p>Врач отправит рекомендации после просмотра данных.</p></article>`}
  <div class="therapy-layout section"><article class="card"><div class="section-head"><h3>Сегодняшний приём</h3><span class="badge badge-new">Самоотчёт</span></div><form id="checkin-form">
    <div class="choice-row"><label><input type="radio" name="taken" value="true" required><span>✓ Принято</span></label><label><input type="radio" name="taken" value="false" required><span>— Пропущено</span></label></div>
    <div class="field"><label for="severity">Нежелательная реакция</label><select id="severity" name="severity"><option value="none">Нет</option><option value="mild">Лёгкая</option><option value="moderate">Умеренная</option><option value="severe">Выраженная</option></select></div>
    <div class="field"><label for="side-effect">Что произошло?</label><textarea id="side-effect" name="side_effect" rows="3" placeholder="Опишите симптомы, если они есть"></textarea></div>
    <div class="notice notice-neutral">Не меняйте назначение самостоятельно. При выраженной реакции данные сразу попадут врачу. При непосредственной угрозе жизни звоните 112.</div>
    <button class="btn btn-primary btn-wide" type="submit">Сохранить отметку ${icon('arrow')}</button>
  </form></article>
  <article class="card"><div class="section-head"><h3>Последние 30 отметок</h3></div>${adherenceBlock()}${checkinHistory()}</article></div>`,'plan');
}

function routingBlock(){
  if(!state.routingSignals.length)return `<article class="card"><div class="section-head"><h3>Маршрутизация</h3></div><div class="empty compact"><p>Активных сигналов нет.</p></div></article>`;
  return `<article class="card wide"><div class="section-head"><h3>Сигналы и маршрутизация</h3><span class="badge badge-warn">${state.routingSignals.filter(x=>x.status==='pending').length} ожидают решения</span></div>
  <div class="routing-list">${state.routingSignals.map(signal=>`<div class="routing-card route-${signal.level} status-${signal.status}"><div><span class="route-label">${signal.level==='mandatory'?'Обязательно':'Желательно'}</span><span class="route-status">${signal.status==='pending'?'Ожидает решения':signal.status==='confirmed'?'Подтверждено':'Отклонено'}</span></div><p>${esc(signal.reason_text)}</p><small>${signal.reason_code==='high_screening_score'||signal.reason_code==='missed_therapy'?'Правило прототипа · ':''}${fmtDate(signal.created_at)}</small>${signal.status==='pending'?`<div class="route-actions"><button class="btn btn-primary" data-route="${signal.id}" data-decision="confirmed">${icon('check')} Подтвердить</button><button class="btn btn-ghost" data-route="${signal.id}" data-decision="dismissed">Отклонить</button></div>`:''}</div>`).join('')}</div>
  <div class="notice notice-neutral">Система только формирует сигнал. Клиническое решение и маршрутизацию подтверждает врач.</div></article>`;
}

const basePatientDetail=patientDetail;
patientDetail=function(){
  let html=basePatientDetail();
  const extra=`<section class="section"><div class="detail-grid"><article class="card"><div class="section-head"><h3>Приверженность терапии</h3></div>${adherenceBlock()}</article><article class="card"><div class="section-head"><h3>Последние отметки</h3></div>${checkinHistory()}</article>${routingBlock()}</div></section>`;
  return html.replace('<!--/sheet-->',extra+'<!--/sheet-->');
}

const baseDoctorHome=doctorHome;
doctorHome=function(){
  const pending=state.patients.reduce((sum,p)=>sum+(p.pending_signals||0),0);
  const mandatory=state.patients.reduce((sum,p)=>sum+(p.mandatory_signals||0),0);
  let html=baseDoctorHome();
  if(!pending)return html;
  const banner=`<div class="signal-banner"><div><span class="badge ${mandatory?'badge-danger':'badge-warn'}">${mandatory?'Обязательно':'Желательно'}</span><b>${pending} ${pending===1?'сигнал ожидает':'сигнала ожидают'} решения врача</b></div><p>Откройте карточку пациента, чтобы подтвердить или отклонить маршрутизацию.</p></div>`;
  return html.replace('<div class="doctor-layout">',banner+'<div class="doctor-layout">');
}

const baseBind=bind;
bind=function(){
  baseBind();
  document.querySelector('#checkin-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;const data=new FormData(event.target);
    try{
      await api(`/api/patients/${state.patient.id}/medication-checkins`,{method:'POST',body:JSON.stringify({
        taken:data.get('taken')==='true',side_effect:data.get('side_effect').trim(),side_effect_severity:data.get('severity')
      })});
      await loadState();state.view='plan';render();toast('Отметка передана врачу');
    }catch(error){button.disabled=false;toast(error.message)}
  });
  document.querySelectorAll('[data-route]').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;
    try{
      await api(`/api/routing-signals/${button.dataset.route}`,{method:'PUT',body:JSON.stringify({status:button.dataset.decision,comment:''})});
      const id=state.currentPatient.id;await openPatient(id);
      toast(button.dataset.decision==='confirmed'?'Маршрутизация подтверждена':'Сигнал отклонён');
    }catch(error){button.disabled=false;toast(error.message)}
  }));
}

render();
loadState();
