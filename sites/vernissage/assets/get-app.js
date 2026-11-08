// 앱에만 있는 화면(작가·작품·미술관 등) 링크를 앱 없이 열었을 때 쓰는 설치 안내.
// 일반 브라우저에서는 앱이 설치돼 있으면 App Links·Universal Links가 이 페이지 대신 앱을 연다.
// 카카오톡·인스타그램 같은 인앱 브라우저는 그 링크를 앱으로 넘기지 않으므로, 먼저 앱을 직접
// 열어 보고 앱이 열리지 않을 때만 스토어로 보낸다. 데스크톱은 스토어 배지만 보여준다.
(function () {
  // 언어 전환은 홈이 아니라 지금 화면의 다른 언어판으로 보낸다(public.js와 같은 규칙).
  var current = location.pathname.replace(/\/$/, "").replace(/^\/(?:en|ja)(?=\/|$)/, "");
  var langLinks = document.querySelectorAll(".lang-switch a[hreflang]");
  for (var i = 0; i < langLinks.length; i++) {
    var code = langLinks[i].getAttribute("hreflang");
    langLinks[i].href = (code === "ko" ? "" : "/" + code) + (current || "/") + location.search;
  }

  var ua = navigator.userAgent || "";
  // iPadOS 13+ Safari는 데스크톱(Macintosh) UA를 보내므로 터치 지원으로 구분한다.
  var isIOS = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var isAndroid = /Android/i.test(ua);
  if (!isIOS && !isAndroid) return;

  var badge = document.querySelector(isIOS ? ".store-badge.appstore" : ".store-badge.play");
  var storeUrl = badge && badge.href;
  if (!storeUrl) return;

  // 앱에는 상세 화면만 있다. /museums, /get-app처럼 열 화면이 없는 주소는 스토어로만 보낸다.
  var isDetail = /^\/(?:(?:en|ja)\/)?(?:museums|artworks|artists|art-concepts|art-figures)\/[^/]+\/?$/.test(
    location.pathname
  );
  if (!isDetail) {
    location.replace(storeUrl);
    return;
  }

  var IN_APP =
    /KAKAOTALK|KAKAOSTORY|NAVER\(inapp|DaumApps|Instagram|FBAN|FBAV|FB_IAB|FBIOS|Line\/|BAND\/|Twitter|Snapchat|everytimeApp|; wv\)/i;

  // 앱이 열리면 이 페이지가 가려진다. "앱에서 열까요?" 같은 시스템 확인창이 뜨면 창이 포커스를
  // 잃는다(blur). 어느 쪽이든 사람이 앱 쪽으로 넘어간 것이므로 스토어 전환을 취소한다.
  var FALLBACK_MS = 1600;
  var timer = null;
  function cancelFallback() {
    if (timer) clearTimeout(timer);
    timer = null;
  }
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) cancelFallback();
  });
  window.addEventListener("pagehide", cancelFallback);
  window.addEventListener("blur", cancelFallback);

  function openApp() {
    cancelFallback();
    var path = location.pathname + location.search;
    if (isAndroid) {
      // 패키지를 지정한 intent는 App Links 검증 여부와 관계없이 앱을 연다. 앱이 없으면 Chrome·인앱
      // 브라우저가 browser_fallback_url(스토어)로 보낸다. 언어 접두사는 앱의 +native-intent가 처리한다.
      location.href =
        "intent://" + location.host + path +
        "#Intent;scheme=https;package=com.atelierlabs.vernissage;" +
        "S.browser_fallback_url=" + encodeURIComponent(storeUrl) + ";end";
    } else {
      // 앱 라우트에는 /en/, /ja/ 접두사가 없다.
      location.href = "vernissage://" + path.replace(/^\/(?:en|ja)(?=\/)/, "").replace(/^\//, "");
    }
    // intent가 막히거나 앱이 없어 아무 일도 없으면 스토어로 보낸다.
    timer = setTimeout(function () {
      timer = null;
      if (!document.hidden) location.replace(storeUrl);
    }, FALLBACK_MS);
  }

  // 앱에서 돌아왔거나 자동 전환이 막혔을 때 다시 누를 수 있는 버튼.
  var openButton = document.querySelector("[data-open-app]");
  if (openButton) {
    openButton.hidden = false;
    openButton.addEventListener("click", openApp);
  }

  if (isAndroid || IN_APP.test(ua)) {
    openApp();
  } else {
    // iOS Safari: 등록되지 않은 scheme을 열면 "주소가 유효하지 않음" 경고가 뜬다. 앱이 있으면
    // Universal Links가 이미 앱을 열었을 것이므로 바로 App Store로 보낸다.
    location.replace(storeUrl);
  }
})();
