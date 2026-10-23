const recommendationPriority={critical:['Критично','danger'],high:['Высокий приоритет','danger'],attention:['Обратить внимание','warning'],routine:['Планово','neutral']};
function recommendationSource(source){
 if(!source)return '';
 const type={clinical_guideline:'Клинические рекомендации',validation:'Валидация шкалы',drug_instruction:'Инструкция препарата',clinical_record:'Клиническая запись',patient_report:'Данные пациента'}[source.kind]||'Источник';
 return source.url?'<a class="recommendation-source" href="'+esc(source.url)+'" target="_blank" rel="noreferrer">'+icon('book')+'<span>'+type+'<small>'+esc(source.label)+'</small></span></a>':'<span class="recommendation-source source-local">'+icon('file')+'<span>'+type+'<small>'+esc(source.label)+'</small></span></span>'
}
function recommendationBlock(){
 const data=state.recommendations;
 if(!data)return '';
 const priority=recommendationPriority[data.priority]||recommendationPriority.routine;
 return '<section class="section recommendation-section" id="patient-recommendations"><article class="card recommendation-card"><div class="section-head"><div><p class="eyebrow">Поддержка принятия решений</p><h2>Клинические рекомендации</h2></div><span class="recommendation-summary tone-'+priority[1]+'">'+priority[0]+'</span></div><p class="recommendation-lead">'+esc(data.summary)+'</p><div class="recommendation-evidence">'+data.evidence.map(function(item){return '<div class="evidence-pill tone-'+item.tone+'"><span>'+esc(item.label)+'</span><b>'+esc(item.value)+'</b></div>'}).join('')+'</div><div class="recommendation-actions">'+data.actions.map(function(item,index){const label=recommendationPriority[item.priority]||recommendationPriority.routine;return '<article class="recommendation-action priority-'+item.priority+'"><div class="recommendation-number">'+(index+1)+'</div><div class="recommendation-copy"><div class="recommendation-title"><h3>'+esc(item.title)+'</h3><span class="tone-'+label[1]+'">'+label[0]+'</span></div><p>'+esc(item.rationale)+'</p><div class="recommendation-next">'+icon('arrow')+'<span><b>Предлагаемый следующий шаг</b>'+esc(item.plan_text)+'</span></div>'+recommendationSource(item.source)+'</div></article>'}).join('')+'</div><div class="recommendation-footer"><div class="notice notice-neutral">'+icon('shield')+' <span>'+esc(data.disclaimer)+'</span></div><button class="btn btn-secondary" id="use-plan-draft">'+icon('edit')+' Перенести в черновик плана</button></div></article></section>'
}
const basePatientDetailRecommendations=patientDetail;
patientDetail=function(){
 let html=basePatientDetailRecommendations();
 if(state.role!=='doctor'||!state.recommendations)return html;
 html=html.replace('<button data-patient-jump="patient-clinical"', '<button data-patient-jump="patient-recommendations">'+icon('sparkles')+' Рекомендации</button><button data-patient-jump="patient-clinical"');
 const block=recommendationBlock();
 const anchor='<section class="section clinical-section" id="patient-clinical">';
 return html.includes(anchor)?html.replace(anchor,block+anchor):html.replace('<!--/sheet-->',block+'<!--/sheet-->')
};
const baseBindRecommendations=bind;
bind=function(){
 baseBindRecommendations();
 document.querySelector('#use-plan-draft')?.addEventListener('click',function(){
  const field=document.querySelector('#plan');
  if(!field||!state.recommendations?.plan_draft)return toast('Нет пунктов для черновика');
  field.value=state.recommendations.plan_draft;
  field.focus();
  field.scrollIntoView({behavior:'smooth',block:'center'});
  toast('Черновик заполнен — проверьте и подтвердите')
 })
};