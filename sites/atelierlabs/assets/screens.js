// 앱 소개 스크린샷 캐러셀: 좌우 스크롤(스와이프) + 이전/다음 버튼 + "n / 8" 표시.
(() => {
  document.querySelectorAll('[data-screens]').forEach((root) => {
    const track = root.querySelector('.screens');
    const prev = root.querySelector('[data-prev]');
    const next = root.querySelector('[data-next]');
    const count = root.querySelector('.screens-count');
    const total = track.children.length;
    const index = () => Math.round(track.scrollLeft / track.clientWidth);
    const update = () => {
      const i = index();
      count.textContent = `${i + 1} / ${total}`;
      prev.disabled = i <= 0;
      next.disabled = i >= total - 1;
    };
    const go = (d) => track.scrollTo({ left: (index() + d) * track.clientWidth });
    prev.addEventListener('click', () => go(-1));
    next.addEventListener('click', () => go(1));
    track.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); go(1); }
    });
    let raf = 0;
    track.addEventListener('scroll', () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(update); }, { passive: true });
    window.addEventListener('resize', update);
    update();
  });
})();
