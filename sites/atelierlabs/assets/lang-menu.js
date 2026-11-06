// 상단 바 언어 버튼(<details class="lang-switch">): 바깥을 누르거나 Esc를 누르면 닫는다.
(() => {
  const menus = [...document.querySelectorAll('details.lang-switch')];
  if (!menus.length) return;
  document.addEventListener('click', (e) => {
    menus.forEach((d) => { if (d.open && !d.contains(e.target)) d.open = false; });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    menus.forEach((d) => {
      if (d.open) { d.open = false; d.querySelector('summary').focus(); }
    });
  });
})();
