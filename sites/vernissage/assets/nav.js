// 휴대폰 화면(≤560px)에서 상단 메뉴를 ☰ 버튼으로 여닫는다.
(() => {
  const header = document.querySelector('.site-header');
  const toggle = header && header.querySelector('.nav-toggle');
  const nav = header && header.querySelector('.site-nav');
  if (!toggle || !nav) return;

  const setOpen = (open) => {
    header.classList.toggle('nav-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? toggle.dataset.labelClose : toggle.dataset.labelOpen);
  };

  toggle.addEventListener('click', () => setOpen(!header.classList.contains('nav-open')));
  // 메뉴 항목을 누르면(앵커 이동·화면 전환 모두) 닫는다
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && header.classList.contains('nav-open')) { setOpen(false); toggle.focus(); }
  });
  document.addEventListener('click', (e) => { if (!header.contains(e.target)) setOpen(false); });
  // 화면이 넓어지면 열린 상태를 정리한다
  matchMedia('(min-width: 561px)').addEventListener('change', (e) => { if (e.matches) setOpen(false); });
})();
