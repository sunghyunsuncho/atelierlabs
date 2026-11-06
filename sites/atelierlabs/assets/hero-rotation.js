(() => {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll("[data-hero-rotation]").forEach((frame) => {
    const slides = Array.from(frame.querySelectorAll(".hero-slide"));
    if (prefersReducedMotion || slides.length < 2) return;

    const interval = Number(frame.dataset.interval) || 6000;
    let activeIndex = slides.findIndex((slide) => slide.classList.contains("is-active"));
    if (activeIndex < 0) activeIndex = 0;
    let timerId;

    const loadSlide = (slide) => {
      if (!slide.dataset.src) return;
      slide.src = slide.dataset.src;
      delete slide.dataset.src;
    };

    const advance = () => {
      slides[activeIndex].classList.remove("is-active");
      activeIndex = (activeIndex + 1) % slides.length;
      loadSlide(slides[activeIndex]);
      slides[activeIndex].classList.add("is-active");
      schedule();
    };

    const schedule = () => {
      if (!document.hidden) timerId = window.setTimeout(advance, interval);
    };

    const stop = () => {
      window.clearTimeout(timerId);
      timerId = undefined;
    };

    // 첫 화면을 그린 뒤 나머지 장면을 미리 받아, 전환 시 빈 화면을 막는다.
    window.requestAnimationFrame(() => slides.forEach(loadSlide));
    schedule();

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stop();
      else if (timerId === undefined) schedule();
    });
  });
})();
