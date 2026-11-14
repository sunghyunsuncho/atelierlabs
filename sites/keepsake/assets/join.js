// 공유 앨범 초대 링크(/join?code=…)를 앱 없이 열었을 때 쓰는 페이지.
// 앱이 설치돼 있으면 App Links·Universal Links가 이 페이지 대신 앱의 참여 화면을 연다.
// 카카오톡·인스타그램 같은 인앱 브라우저는 그 링크를 앱으로 넘기지 않으므로, 휴대폰에서는 앱을 직접 열어 본다.
// 아직 스토어 출시 전이라 앱이 없을 때 보낼 곳이 없다. 그때는 이 페이지에 남아 초대 코드를 보여준다.
(function () {
  // 앱의 normalizeCode(lib/cloud/shared.ts)와 같은 규칙.
  var code = (new URLSearchParams(location.search).get("code") || "")
    .replace(/[^0-9a-z]/gi, "")
    .toUpperCase()
    .slice(0, 16);

  // 언어 전환은 홈이 아니라 같은 초대의 다른 언어판으로 보낸다.
  var langLinks = document.querySelectorAll(".lang-switch a[hreflang]");
  for (var i = 0; i < langLinks.length; i++) {
    var lang = langLinks[i].getAttribute("hreflang");
    langLinks[i].href = (lang === "ko" ? "" : "/" + lang) + "/join" + location.search;
  }

  if (!code) {
    document.querySelector("[data-no-code]").hidden = false;
    return;
  }
  document.querySelector("[data-code-box]").hidden = false;
  document.querySelector("[data-code]").textContent = code;

  var copyButton = document.querySelector("[data-copy]");
  if (navigator.clipboard) {
    copyButton.addEventListener("click", function () {
      // 권한 거부 등으로 실패하면 코드는 화면에 그대로 있으니 버튼 문구만 바꾸지 않는다.
      navigator.clipboard.writeText(code).then(
        function () {
          copyButton.textContent = copyButton.getAttribute("data-copied");
        },
        function () {}
      );
    });
  } else {
    copyButton.hidden = true;
  }

  var ua = navigator.userAgent || "";
  // iPadOS 13+ Safari는 데스크톱(Macintosh) UA를 보내므로 터치 지원으로 구분한다.
  var isIOS = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var isAndroid = /Android/i.test(ua);
  if (!isIOS && !isAndroid) return;

  var IN_APP =
    /KAKAOTALK|KAKAOSTORY|NAVER\(inapp|DaumApps|Instagram|FBAN|FBAV|FB_IAB|FBIOS|Line\/|BAND\/|Twitter|Snapchat|everytimeApp|; wv\)/i;
  // 앱의 참여 화면(src/app/shared-albums/join.tsx). 코드가 채워진 채로 열린다.
  var appPath = "shared-albums/join?code=" + encodeURIComponent(code);
  // 앱이 없을 때 Android가 돌아올 주소. 해시만 바뀌므로 페이지를 다시 불러오지 않는다.
  var NO_APP = "#no-app";

  function openApp() {
    if (isAndroid) {
      // 패키지를 지정한 intent는 App Links 검증 여부와 관계없이 앱을 연다. 앱이 없으면 Play 스토어 대신
      // browser_fallback_url(이 페이지)로 돌아온다. 출시 뒤에는 스토어 주소로 바꾼다.
      location.href =
        "intent://" + appPath +
        "#Intent;scheme=keepsake;package=com.atelierlabs.keepsake;" +
        "S.browser_fallback_url=" + encodeURIComponent(location.href.split("#")[0] + NO_APP) + ";end";
    } else {
      location.href = "keepsake://" + appPath;
    }
  }

  // 앱에서 돌아왔거나 자동으로 열리지 않았을 때 다시 누를 수 있는 버튼.
  var openButton = document.querySelector("[data-open-app]");
  openButton.hidden = false;
  openButton.addEventListener("click", openApp);

  // iOS Safari는 앱이 있으면 Universal Links가 이미 앱을 열었을 것이고, 없는 scheme을 열면
  // "주소가 유효하지 않음" 경고가 뜬다. 그래서 Android와 인앱 브라우저에서만 바로 열어 본다.
  if (location.hash !== NO_APP && (isAndroid || IN_APP.test(ua))) openApp();
})();
