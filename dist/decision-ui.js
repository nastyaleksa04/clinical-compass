const therapyIndications=['Генерализованное тревожное расстройство у взрослых','Тревожные состояния после COVID-19','Стрессовая реакция и нарушение адаптации лёгкой и средней степени'];
const decisionLabels={approved:'Подтверждено',rejected:'Не применять',deferred:'Отложено',cancelled:'Отменено'};
const safetyLabels={suitable:'Противопоказания не отмечены',review_required:'Нужна дополнительная оценка',not_suitable:'Есть противопоказание'};
function decisionFindings(item){if(!item.safety_findings?.length)return '<p class="decision-safe">'+icon('check')+' По чек-листу факторов риска не отмечено</p>';return '<ul class="decision-findings">'+item.safety_findings.map(function(f){return '<li class="finding-'+f.level+'">'+esc(f.text)+'</li>'}).join('')+'</ul>'}
function decisionHistory(){
 if(!state.therapyDecisions?.length)return '<div class="empty compact"><p>Решений по терапии пока нет.</p></div>';
 return '<div class="decision-list">'+state.therapyDecisions.map(function(item){
  const regimen=item.decision==='approved'||item.decision==='cancelled'?'<div class="decision-regimen"><span><b>'+esc(item.dosage)+'</b> доза</span><span><b>'+esc(item.schedule)+'</b> режим</span><span><b>'+esc(item.duration)+'</b> длительность</span></div>':'';
  return '<article class="decision-item status-'+item.decision+'"><div class="decision-head"><div><span class="decision-status">'+(decisionLabels[item.decision]||esc(item.decision))+'</span><h4>'+esc(item.medication_name)+'</h4></div><time>'+fmtDate(item.cancelled_at||item.created_at)+'</time></div>'+(item.indication?'<p>'+esc(item.indication)+'</p>':'')+regimen+(item.rationale?'<p class="decision-rationale"><b>Обоснование:</b> '+esc(item.rationale)+'</p>':'')+'<details><summary>'+(safetyLabels[item.safety_status]||'Результат проверки безопасности')+'</summary>'+decisionFindings(item)+'</details><div class="decision-foot"><small>'+esc(item.confirmed_by)+' · '+fmtDate(item.created_at)+'</small>'+(item.decision==='approved'?'<button class="btn btn-ghost" data-cancel-therapy="'+item.id+'">Отменить решение</button>':'')+'</div></article>'
 }).join('')+'</div>'
}
function therapyDecisionBlock(){
 const check=state.therapyResult;
 const note=check?'<div class="decision-check result-'+check.status+'">'+icon(check.status==='not_suitable'?'warning':'shield')+'<div><b>'+esc(check.title)+'</b><span>Результат текущего чек-листа будет приложен к решению</span></div></div>':'<div class="notice notice-neutral">Перед подтверждением заполните чек-лист факторов выше. Сервер повторно проверит выбранные факторы при сохранении решения.</div>';
 return '<section class="section therapy-decision-section" id="patient-therapy-decision"><div class="section-head"><div><h2>Решение по терапии</h2><p>Фиксируется врачом после проверки показаний и рисков</p></div><span class="badge badge-new">Контроль врача</span></div><div class="therapy-decision-grid"><article class="card"><h3>Новое решение</h3>'+note+'<form id="therapy-decision-form" class="decision-form"><div class="field"><label for="therapy-decision">Статус решения</label><select id="therapy-decision" name="decision"><option value="approved">Подтвердить терапию</option><option value="deferred">Отложить решение</option><option value="rejected">Не применять</option></select></div><div class="field"><label for="therapy-indication">Показание</label><select id="therapy-indication" name="indication">'+therapyIndications.map(function(x){return '<option value="'+esc(x)+'">'+esc(x)+'</option>'}).join('')+'</select></div><div class="decision-form-grid"><div class="field"><label>Доза</label><input name="dosage" value="20 мг"></div><div class="field"><label>Режим приёма</label><input name="schedule" value="2 раза в сутки за 30 минут до еды"></div><div class="field"><label>Длительность</label><input name="duration" placeholder="Например, 4 недели"></div></div><div class="field"><label>Клиническое обоснование</label><textarea name="rationale" rows="3" placeholder="Обязательно при рисках, отказе или отсрочке"></textarea></div><button class="btn btn-primary btn-wide" type="submit">Сохранить решение '+icon('arrow')+'</button></form></article><article class="card"><div class="section-head"><h3>История решений</h3><span class="badge">'+(state.therapyDecisions?.length||0)+'</span></div>'+decisionHistory()+'</article></div></section>'
}
function confirmedTherapyBlock(){
 const items=state.therapyDecisions||[],active=items.find(function(x){return x.decision==='approved'}),cancelled=!active&&items.find(function(x){return x.decision==='cancelled'});
 if(!active&&!cancelled)return '<article class="card confirmed-therapy empty compact"><span class="status-orb">'+icon('pill')+'</span><h3>Подтверждённой терапии пока нет</h3><p>После решения врача здесь появятся препарат, режим и длительность.</p></article>';
 if(!active)return '<article class="card confirmed-therapy therapy-cancelled"><div class="section-head"><h3>Решение по терапии отменено</h3><span class="badge">Отменено</span></div><p>'+esc(cancelled.medication_name)+' больше не отображается как активное назначение.</p><small>Изменено врачом · '+fmtDate(cancelled.cancelled_at||cancelled.created_at)+'</small></article>';
 return '<article class="card confirmed-therapy"><div class="section-head"><div><p class="eyebrow">Подтверждено лечащим врачом</p><h3>'+esc(active.medication_name)+'</h3></div><span class="badge badge-new">Актуально</span></div><p>'+esc(active.indication)+'</p><div class="confirmed-regimen"><div>'+icon('pill')+'<span><b>'+esc(active.dosage)+'</b><small>Доза</small></span></div><div>'+icon('clock')+'<span><b>'+esc(active.schedule)+'</b><small>Режим</small></span></div><div>'+icon('calendar')+'<span><b>'+esc(active.duration)+'</b><small>Длительность</small></span></div></div>'+(active.rationale?'<div class="notice notice-neutral"><b>Комментарий врача:</b> '+esc(active.rationale)+'</div>':'')+'<div class="decision-foot"><small>'+esc(active.confirmed_by)+' · '+fmtDate(active.created_at)+'</small><a href="'+esc(active.source_url)+'" target="_blank" rel="noreferrer">Инструкция</a></div></article>'
}
const basePatientDetailDecision=patientDetail;
patientDetail=function(){const html=basePatientDetailDecision();return state.role==='doctor'?html.replace('<!--/sheet-->',therapyDecisionBlock()+'<!--/sheet-->'):html};
const basePlanViewDecision=planView;
planView=function(){const html=basePlanViewDecision();return state.role==='patient'?html.replace('<!--/sheet-->','<section class="section patient-confirmed-therapy"><div class="section-head"><h2>Назначенная терапия</h2></div>'+confirmedTherapyBlock()+'</section><!--/sheet-->'):html};
function currentTherapyFactors(){return Object.fromEntries(therapyFactors.map(function(pair){const key=pair[0];return [key,Boolean(document.querySelector('#therapy-check-form input[name="'+key+'"]')?.checked)]}))}
const baseBindDecision=bind;
bind=function(){
 baseBindDecision();
 document.querySelector('#therapy-decision-form')?.addEventListener('submit',async function(event){event.preventDefault();const button=event.submitter;button.disabled=true;const data=new FormData(event.target),payload={medication_id:'aviandr',decision:data.get('decision'),indication:data.get('indication'),dosage:data.get('dosage').trim(),schedule:data.get('schedule').trim(),duration:data.get('duration').trim(),rationale:data.get('rationale').trim(),factors:currentTherapyFactors()};try{const id=state.currentPatient.id;await api('/api/patients/'+id+'/therapy-decisions',{method:'POST',body:JSON.stringify(payload)});await openPatient(id);toast(payload.decision==='approved'?'Терапия подтверждена и доступна пациенту':'Решение сохранено во внутренней истории')}catch(error){button.disabled=false;toast(error.message)}});
 document.querySelectorAll('[data-cancel-therapy]').forEach(function(button){button.addEventListener('click',async function(){button.disabled=true;try{const id=state.currentPatient.id;await api('/api/therapy-decisions/'+button.dataset.cancelTherapy+'/cancel',{method:'PUT'});await openPatient(id);toast('Решение по терапии отменено')}catch(error){button.disabled=false;toast(error.message)}})})
};

/* Keep the evaluated checklist attached to the following doctor decision. */
function currentTherapyFactors(){
 const live=Object.fromEntries(therapyFactors.map(function(pair){const key=pair[0];return [key,Boolean(document.querySelector('#therapy-check-form input[name="'+key+'"]')?.checked)]}));
 return Object.values(live).some(Boolean)||!state.therapyResult?live:(state.therapyCheckedFactors||live)
}
const baseBindDecisionFactors=bind;
bind=function(){
 baseBindDecisionFactors();
 document.querySelector('#therapy-check-form')?.addEventListener('submit',function(){state.therapyCheckedFactors=currentTherapyFactors()})
};
