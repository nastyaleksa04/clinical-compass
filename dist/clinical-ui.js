function clinicalProfileCard(){
  const p=state.clinicalProfile||{};
  const filled=Boolean(p.visit_reason||p.complaints||p.history||p.working_hypothesis);
  const pregnancy={unknown:'Не уточнено',no:'Нет',yes:'Да',not_applicable:'Не применимо'}[p.pregnancy_status||'unknown'];
  const risk=p.self_harm_concern?'Риск самоповреждения':p.psychosis_signs?'Психотические симптомы':'Критические признаки не отмечены';
  return `<section class="section clinical-section" id="patient-clinical"><article class="card clinical-card">
    <div class="section-head"><div><h3>Клиническая сводка</h3><p class="eyebrow">Заполняет лечащий врач</p></div><span class="badge ${p.self_harm_concern||p.psychosis_signs?'badge-danger':filled?'badge-new':'badge-warn'}">${filled?'Сохранена':'Не заполнена'}</span></div>
    ${filled?`<div class="clinical-summary-grid">
      <div><span>Причина обращения</span><b>${esc(p.visit_reason||'Не указана')}</b></div>
      <div><span>Длительность</span><b>${esc(p.symptom_duration||'Не указана')}</b></div>
      <div class="clinical-wide"><span>Жалобы</span><b>${esc(p.complaints||'Не указаны')}</b></div>
      <div><span>Рабочая гипотеза</span><b>${esc(p.working_hypothesis||'Не сформулирована')}</b></div>
      <div><span>Беременность</span><b>${pregnancy}</b></div>
    </div><div class="clinical-risk ${p.self_harm_concern||p.psychosis_signs?'has-risk':''}">${icon(p.self_harm_concern||p.psychosis_signs?'warning':'shield')}<span><b>${risk}</b><small>Ручная отметка врача; не является автоматическим диагнозом</small></span></div>`:''}
    <details class="clinical-editor" ${filled?'':'open'}><summary>${filled?'Редактировать сводку':'Заполнить клиническую сводку'}</summary>
      <form id="clinical-profile-form">
        <div class="form-grid"><div class="field"><label>Причина обращения</label><input class="text-input" name="visit_reason" maxlength="500" value="${esc(p.visit_reason||'')}" placeholder="Что привело пациента"></div>
        <div class="field"><label>Длительность симптомов</label><input class="text-input" name="symptom_duration" maxlength="300" value="${esc(p.symptom_duration||'')}" placeholder="Например, около 3 месяцев"></div></div>
        <div class="field"><label>Основные жалобы</label><textarea name="complaints" rows="3" maxlength="4000" placeholder="Симптомы, частота, влияние на повседневную жизнь">${esc(p.complaints||'')}</textarea></div>
        <div class="field"><label>Анамнез и динамика</label><textarea name="history" rows="4" maxlength="6000" placeholder="Начало, течение, предыдущая помощь">${esc(p.history||'')}</textarea></div>
        <div class="form-grid"><div class="field"><label>Сопутствующие состояния</label><textarea name="comorbidities" rows="3" maxlength="3000">${esc(p.comorbidities||'')}</textarea></div>
        <div class="field"><label>Текущие препараты</label><textarea name="current_medications" rows="3" maxlength="3000">${esc(p.current_medications||'')}</textarea></div></div>
        <div class="form-grid"><div class="field"><label>Аллергии и непереносимость</label><textarea name="allergies" rows="2" maxlength="2000">${esc(p.allergies||'')}</textarea></div>
        <div class="field"><label>Рабочая гипотеза врача</label><textarea name="working_hypothesis" rows="2" maxlength="1000">${esc(p.working_hypothesis||'')}</textarea></div></div>
        <div class="form-grid"><div class="field"><label>Беременность</label><select name="pregnancy_status">
          <option value="unknown" ${p.pregnancy_status==='unknown'||!p.pregnancy_status?'selected':''}>Не уточнено</option>
          <option value="no" ${p.pregnancy_status==='no'?'selected':''}>Нет</option>
          <option value="yes" ${p.pregnancy_status==='yes'?'selected':''}>Да</option>
          <option value="not_applicable" ${p.pregnancy_status==='not_applicable'?'selected':''}>Не применимо</option>
        </select></div><div class="clinical-checks">
          <label class="check-row"><input type="checkbox" name="psychosis_signs" ${p.psychosis_signs?'checked':''}><span><b>Психотические симптомы</b><br>Требуют отдельной клинической оценки</span></label>
          <label class="check-row"><input type="checkbox" name="self_harm_concern" ${p.self_harm_concern?'checked':''}><span><b>Опасения самоповреждения</b><br>Зафиксировано врачом при оценке</span></label>
        </div></div>
        <div class="notice notice-neutral">Сводка сохраняет введённые врачом сведения. Система не формирует диагноз и не меняет лечение автоматически.</div>
        <button class="btn btn-primary btn-wide" type="submit">${icon('check')} Сохранить сводку</button>
      </form>
    </details>
  </article></section>`;
}

function patientWorkflowBar(){
  const a=state.adherence||{};
  const pending=(state.tasks||[]).filter(x=>x.status==='pending').length;
  const signals=(state.routingSignals||[]).filter(x=>x.status==='pending').length;
  const latestResult=state.assessments[0];
  return `<section class="patient-workflow">
    <div class="patient-kpis">
      <div><b>${latestResult?latestResult.total:'—'}</b><span>${latestResult?latestResult.scale_id.toUpperCase():'нет шкал'}</span></div>
      <div><b>${a.percent==null?'—':a.percent+'%'}</b><span>приверженность</span></div>
      <div class="${signals?'is-alert':''}"><b>${signals}</b><span>решения</span></div>
      <div><b>${pending}</b><span>действия</span></div>
    </div>
    <nav class="patient-jumpbar" aria-label="Разделы карточки пациента">
      <button data-patient-jump="patient-clinical">${icon('clipboard')} Сводка</button>
      <button data-patient-view="progress">${icon('activity')} Динамика</button>
      <button data-patient-jump="patient-plan">${icon('list')} План</button>
      <button data-patient-jump="patient-therapy">${icon('pill')} Терапия</button>
      <button data-patient-jump="patient-risks">${icon('warning')} Риски</button>
      <button data-patient-view="messages">${icon('message')} Написать</button>
    </nav>
  </section>`;
}

const basePatientDetailClinical=patientDetail;
patientDetail=function(){
  let html=basePatientDetailClinical();
  const firstClose='</section>';
  if(html.includes(firstClose))html=html.replace(firstClose,firstClose+patientWorkflowBar());
  const marker='<div class="detail-grid section">';
  if(html.includes(marker))html=html.replace(marker,clinicalProfileCard()+marker);
  return html;
}

const baseDoctorHomeWorkflow=doctorHome;
doctorHome=function(){
  let html=baseDoctorHomeWorkflow();
  const counts={
    all:state.patients.length,
    critical:state.patients.filter(p=>(p.mandatory_signals||0)>0||p.scenario?.expected_route==='mandatory').length,
    decision:state.patients.filter(p=>(p.pending_signals||0)>0).length,
    new:state.patients.filter(p=>(p.unread_messages||0)>0||(p.latest_scale_id&&!p.latest_scale_reviewed)||(p.latest_report_id&&!p.latest_report_reviewed)).length
  };
  const filters=`<div class="patient-filters" role="group" aria-label="Фильтр пациентов">
    <button class="active" data-patient-filter="all">Все <span>${counts.all}</span></button>
    <button data-patient-filter="critical">Критические <span>${counts.critical}</span></button>
    <button data-patient-filter="decision">Ждут решения <span>${counts.decision}</span></button>
    <button data-patient-filter="new">Новые данные <span>${counts.new}</span></button>
    <button data-patient-filter="stable">Стабильные</button>
  </div>`;
  return html.replace('<div class="patient-list">',filters+'<div class="patient-list">');
}

const baseProgressWorkflow=progressView;
progressView=function(){
  let html=baseProgressWorkflow();
  if(state.role!=='doctor'||!state.currentPatient)return html;
  const context=`<div class="doctor-context-head"><button class="back" data-view="patient">${icon('chevron')}</button><div class="avatar">${esc(state.currentPatient.initials)}</div><div><span>Динамика пациента</span><b>${esc(state.currentPatient.name)}</b></div><button class="btn btn-secondary" data-patient-view="messages">${icon('message')} Связаться</button></div>`;
  return html.replace('<div class="sheet">','<div class="sheet">'+context);
}

const baseBindClinical=bind;
bind=function(){
  baseBindClinical();

  const plan=document.querySelector('.care-section');if(plan)plan.id='patient-plan';
  const therapy=document.querySelector('.therapy-reference')?.closest('section');if(therapy)therapy.id='patient-therapy';
  const risks=document.querySelector('.routing-list')?.closest('section');if(risks)risks.id='patient-risks';

  document.querySelectorAll('[data-patient-jump]').forEach(button=>button.addEventListener('click',()=>{
    const target=document.getElementById(button.dataset.patientJump);
    if(target)target.scrollIntoView({behavior:'smooth',block:'start'});
  }));
  document.querySelectorAll('[data-patient-view]').forEach(button=>button.addEventListener('click',()=>{
    const view=button.dataset.patientView;
    if(view==='messages')openMessages(state.currentPatient.id);
    else{state.view=view;render();scrollTo(0,0)}
  }));

  document.querySelectorAll('[data-patient-filter]').forEach(button=>button.addEventListener('click',()=>{
    const value=button.dataset.patientFilter;
    document.querySelectorAll('[data-patient-filter]').forEach(x=>x.classList.toggle('active',x===button));
    document.querySelectorAll('.patient-list>.patient-card[data-patient]').forEach(card=>{
      const p=state.patients.find(x=>x.id===Number(card.dataset.patient));
      const critical=(p.mandatory_signals||0)>0||p.scenario?.expected_route==='mandatory';
      const decision=(p.pending_signals||0)>0;
      const fresh=(p.unread_messages||0)>0||(p.latest_scale_id&&!p.latest_scale_reviewed)||(p.latest_report_id&&!p.latest_report_reviewed);
      const stable=!critical&&!decision&&!fresh;
      card.hidden=value!=='all'&&!({critical,decision,new:fresh,stable}[value]);
    });
  }));

  document.querySelector('#clinical-profile-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const form=event.target;const button=event.submitter;button.disabled=true;
    const value=name=>form.elements[name].value.trim();
    const payload={
      visit_reason:value('visit_reason'),complaints:value('complaints'),symptom_duration:value('symptom_duration'),
      history:value('history'),comorbidities:value('comorbidities'),current_medications:value('current_medications'),
      allergies:value('allergies'),working_hypothesis:value('working_hypothesis'),
      pregnancy_status:form.elements.pregnancy_status.value,
      psychosis_signs:form.elements.psychosis_signs.checked,self_harm_concern:form.elements.self_harm_concern.checked
    };
    try{
      const patientId=state.currentPatient.id;
      await api(`/api/patients/${patientId}/clinical-profile`,{method:'PUT',body:JSON.stringify(payload)});
      await openPatient(patientId);
      requestAnimationFrame(()=>document.getElementById('patient-clinical')?.scrollIntoView({block:'start'}));toast('Клиническая сводка сохранена');
    }catch(error){button.disabled=false;toast(error.message)}
  });
}
