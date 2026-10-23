state.therapyResult=null;
const therapyFactors=[['pregnancy','Беременность'],['breastfeeding','Грудное вскармливание'],['epilepsy_or_brain_disease','Эпилепсия или органическое заболевание мозга'],['egfr_below_60','СКФ менее 60 мл/мин'],['hepatic_impairment','Печёночная недостаточность'],['maoi_recent','ИМАО сейчас или менее 2 недель назад'],['lactose_disorder','Нарушение усвоения галактозы/лактозы'],['serotonergic_drugs','Серотонинергические препараты'],['cyp2d6_inhibitors','Ингибиторы CYP2D6'],['sedatives','Седативные препараты'],['alcohol','Употребление алкоголя'],['driving','Необходимость управлять транспортом']];

function therapyResultBlock(){
  const r=state.therapyResult;if(!r)return '';
  return `<div class="therapy-result result-${r.status}"><h4>${esc(r.title)}</h4>${r.findings.length?`<ul>${r.findings.map(x=>`<li class="finding-${x.level}">${esc(x.text)}</li>`).join('')}</ul>`:'<p>Чек-лист не заменяет сбор анамнеза и проверку всех назначений.</p>'}<small>${esc(r.disclaimer)}</small></div>`;
}
const basePatientDetailTherapy=patientDetail;
patientDetail=function(){
  let html=basePatientDetailTherapy();
  const block=`<section class="section"><article class="card therapy-reference"><div class="section-head"><div><h3>Справочник терапии</h3><p class="eyebrow">АВИАНДР® · рецептурный препарат</p></div><span class="badge badge-warn">Решение врача</span></div><p class="therapy-dose">По инструкции: 20 мг 2 раза в сутки за 30 минут до еды. Назначение и длительность определяет врач.</p><details><summary>Показания и источник</summary><p>ГТР у взрослых; тревожные состояния после COVID-19; стрессовая реакция и нарушение адаптации лёгкой и средней степени.</p><a href="https://aviandr.ru/patient" target="_blank" rel="noreferrer">Инструкция и сведения о регистрации</a></details><form id="therapy-check-form"><h4>Проверка индивидуальных факторов</h4><div class="risk-grid">${therapyFactors.map(([key,label])=>`<label><input type="checkbox" name="${key}"><span>${label}</span></label>`).join('')}</div><button class="btn btn-secondary btn-wide" type="submit">Проверить по инструкции</button></form>${therapyResultBlock()}</article></section>`;
  return html.replace('<!--/sheet-->',block+'<!--/sheet-->');
}
const baseBindTherapy=bind;
bind=function(){
  baseBindTherapy();
  document.querySelector('#therapy-check-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;const data=new FormData(event.target);
    const factors=Object.fromEntries(therapyFactors.map(([key])=>[key,data.get(key)==='on']));
    try{state.therapyResult=await api(`/api/patients/${state.currentPatient.id}/therapy-check`,{method:'POST',body:JSON.stringify({medication_id:'aviandr',factors})});render();toast('Проверка завершена')}catch(error){button.disabled=false;toast(error.message)}
  });
}
