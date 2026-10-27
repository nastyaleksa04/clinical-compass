// Рекламный блок препарата в боковой панели кабинета врача (только десктоп).
// Реклама рецептурного препарата допустима только для специалистов здравоохранения (ФЗ «О рекламе», ст. 24).

function aviandrPromo(){
  return `<aside class="promo-card" aria-label="Реклама препарата Авиандр">
    <span class="promo-label">Реклама</span>
    <img class="promo-pack" src="assets/promo/aviandr.png" alt="Упаковка препарата Авиандр 20 мг, 30 таблеток" draggable="false">
    <b>Авиандр<sup>®</sup></b>
    <span>Маритупирдин · 20 мг, 30 таблеток</span>
    <span class="promo-maker">${icon('shield')}Производитель: «Химрар»</span>
    <small>Информация для специалистов здравоохранения. Рецептурный препарат. Имеются противопоказания. Перед назначением ознакомьтесь с инструкцией по медицинскому применению.</small>
  </aside>`;
}

const baseShellPromo=shell;
shell=function(content,active,options){
  const html=baseShellPromo(content,active,options);
  if(state.role!=='doctor')return html;
  return html.replace('<div class="side-bottom">',aviandrPromo()+'<div class="side-bottom">');
};
