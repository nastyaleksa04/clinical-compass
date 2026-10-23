function scenarioCard(){
  const s=state.scenario;
  if(!s)return '';
  const routeLabels={none:'Маршрутизация не ожидается',recommended:'Желательно к психиатру',mandatory:'Обязательно к психиатру'};
  const routeClass=s.expected_route==='mandatory'?'badge-danger':s.expected_route==='recommended'?'badge-warn':'badge-new';
  const therapyClass=s.therapy_status==='blocked'||s.therapy_status==='defer'?'scenario-danger':s.therapy_status==='eligible'?'scenario-success':'scenario-review';
  return `<section class="section scenario-section"><article class="card scenario-card scenario-${esc(s.tone)}">
    <div class="scenario-head"><div><span class="eyebrow">Демонстрационный сценарий</span><h3>${esc(s.title)}</h3></div><span class="badge ${routeClass}">${routeLabels[s.expected_route]||'Решение врача'}</span></div>
    <p class="scenario-summary">${esc(s.summary)}</p>
    <div class="scenario-grid">
      <div><span>Жалобы</span><b>${s.complaints.map(esc).join(' · ')}</b></div>
      <div><span>Контекст</span><b>${esc(s.history)}</b></div>
      <div class="${therapyClass}"><span>Рассмотрение АВИАНДР®</span><b>${esc(s.therapy_label)}</b><small>${esc(s.therapy_text)}</small></div>
    </div>
    <details class="scenario-steps"><summary>Как показать сценарий</summary><ol>${s.demo_steps.map(step=>`<li>${esc(step)}</li>`).join('')}</ol></details>
    <div class="notice notice-neutral">Профиль и события синтетические. Подсказка описывает ожидаемый путь демонстрации и не является клиническим назначением.</div>
  </article></section>`;
}

const basePatientDetailScenario=patientDetail;
patientDetail=function(){
  const html=basePatientDetailScenario();
  const marker='<div class="detail-grid section">';
  return state.scenario&&html.includes(marker)?html.replace(marker,scenarioCard()+marker):html;
}

const baseBindScenario=bind;
bind=function(){
  baseBindScenario();
  const factors=new Set(state.scenario?.therapy_factors||[]);
  factors.forEach(key=>{
    const input=document.querySelector(`#therapy-check-form input[name="${CSS.escape(key)}"]`);
    if(input)input.checked=true;
  });
}
