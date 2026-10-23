function fmtDue(value){
  if(!value)return 'Без срока';
  return new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'long'}).format(new Date(value+'T00:00:00'));
}

function tasksBlock(editable=false){
  const categories={therapy:'Терапия',assessment:'Опросник',consultation:'Консультация',monitoring:'Наблюдение'};
  if(!state.tasks.length)return '<div class="empty compact"><p>Назначенных действий пока нет.</p></div>';
  return `<div class="task-list">${state.tasks.map(task=>`<article class="task-item task-${task.status}"><button class="task-check" data-task="${task.id}" data-task-status="${task.status==='completed'?'pending':'completed'}" ${task.status==='cancelled'?'disabled':''} aria-label="${task.status==='completed'?'Вернуть в работу':'Отметить выполненным'}">${task.status==='completed'?'✓':''}</button><div class="task-copy"><div><span class="task-category">${categories[task.category]}</span><span class="task-due">${fmtDue(task.due_date)}</span></div><b>${esc(task.title)}</b>${task.description?`<p>${esc(task.description)}</p>`:''}<small>${task.status==='completed'?'Выполнено':task.status==='cancelled'?'Отменено врачом':'Ожидает выполнения'}</small></div>${editable&&task.status!=='cancelled'?`<button class="task-cancel" data-task="${task.id}" data-task-status="cancelled" aria-label="Отменить">×</button>`:''}</article>`).join('')}</div>`;
}

const basePlanTasks=planView;
planView=function(){
  let html=basePlanTasks();
  if(state.role!=='patient')return html;
  const pending=state.tasks.filter(task=>task.status==='pending').length;
  const block=`<section class="section care-section"><div class="section-head"><h2>План наблюдения</h2><span class="badge badge-new">${pending} к выполнению</span></div><article class="card">${tasksBlock(false)}</article></section>`;
  return html.replace('<!--/sheet-->',block+'<!--/sheet-->');
}

const basePatientDetailTasks=patientDetail;
patientDetail=function(){
  let html=basePatientDetailTasks();
  const block=`<section class="section care-section"><div class="detail-grid"><article class="card"><div class="section-head"><h3>Действия пациента</h3><span class="badge badge-new">${state.tasks.filter(task=>task.status==='pending').length} активных</span></div>${tasksBlock(true)}</article><article class="card"><div class="section-head"><h3>Добавить в план</h3><span class="badge badge-new">Подтвердит врач</span></div><form id="task-form">
  <div class="field"><label for="task-title">Действие</label><input class="text-input" id="task-title" name="title" list="task-templates" maxlength="200" placeholder="Например, пройти PHQ-9" required><datalist id="task-templates"><option value="Пройти PHQ-9"><option value="Пройти GAD-7"><option value="Контрольная консультация"><option value="Ежедневно отмечать приём терапии"><option value="Связаться с врачом"></datalist></div>
  <div class="form-grid"><div class="field"><label for="task-category">Категория</label><select id="task-category" name="category"><option value="assessment">Опросник</option><option value="consultation">Консультация</option><option value="therapy">Терапия</option><option value="monitoring">Наблюдение</option></select></div><div class="field"><label for="task-date">Срок</label><input class="text-input" id="task-date" type="date" name="due_date"></div></div>
  <div class="field"><label for="task-description">Комментарий пациенту</label><textarea id="task-description" name="description" rows="3"></textarea></div>
  <button class="btn btn-primary btn-wide" type="submit">${icon('plus')} Добавить и отправить</button></form></article></div></section>`;
  return html.replace('<!--/sheet-->',block+'<!--/sheet-->');
}

const baseBindTasks=bind;
bind=function(){
  baseBindTasks();
  document.querySelector('#task-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;const data=new FormData(event.target);
    try{
      await api(`/api/patients/${state.currentPatient.id}/tasks`,{method:'POST',body:JSON.stringify({
        title:data.get('title').trim(),description:data.get('description').trim(),
        category:data.get('category'),due_date:data.get('due_date')||null
      })});
      await openPatient(state.currentPatient.id);toast('Действие добавлено в план пациента');
    }catch(error){button.disabled=false;toast(error.message)}
  });
  document.querySelectorAll('[data-task-status]').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;
    try{
      await api(`/api/tasks/${button.dataset.task}`,{method:'PUT',body:JSON.stringify({status:button.dataset.taskStatus})});
      if(state.role==='doctor')await openPatient(state.currentPatient.id);
      else{await loadState();state.view='plan';render()}
      toast(button.dataset.taskStatus==='completed'?'Отмечено как выполненное':button.dataset.taskStatus==='cancelled'?'Действие отменено':'Возвращено в работу');
    }catch(error){button.disabled=false;toast(error.message)}
  }));
}
