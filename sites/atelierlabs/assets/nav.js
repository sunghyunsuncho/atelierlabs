// 좁은 화면에서 상단 메뉴를 ☰ 버튼으로 여닫는다. 버튼이 보이는 폭은 CSS가 정한다.
(() => {
  const header = document.querySelector('.site-header');
  const toggle = header && header.querySelector('.nav-toggle');
  const nav = header && header.querySelector('.site-nav');
  if (!toggle || !nav) return;
  const langMenus = [...header.querySelectorAll('details.lang-switch')];
  const isOpen = () => header.classList.contains('nav-open');

  const setOpen = (open) => {
    header.classList.toggle('nav-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? toggle.dataset.labelClose : toggle.dataset.labelOpen);
    // 메뉴와 언어 선택이 겹쳐 열리지 않게 한다
    if (open) langMenus.forEach((d) => { d.open = false; });
  };

  toggle.addEventListener('click', () => setOpen(!isOpen()));
  langMenus.forEach((d) => d.addEventListener('toggle', () => { if (d.open && isOpen()) setOpen(false); }));
  // 메뉴 항목을 누르면(앵커 이동·화면 전환 모두) 닫는다
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen()) { setOpen(false); toggle.focus(); }
  });
  document.addEventListener('click', (e) => { if (isOpen() && !header.contains(e.target)) setOpen(false); });
  // 화면이 넓어져 ☰ 버튼이 사라지면 열린 상태를 정리한다
  window.addEventListener('resize', () => {
    if (isOpen() && getComputedStyle(toggle).display === 'none') setOpen(false);
  }, { passive: true });
})();
