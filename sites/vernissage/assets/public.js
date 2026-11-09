(() => {
  const app = document.querySelector('#public-web-app');
  // 언어는 shell의 <html lang>으로 정한다. 한국어는 루트, 영어·일본어는 /en/·/ja/ 아래 같은 경로다.
  const LANG = ['en', 'ja'].includes(document.documentElement.lang) ? document.documentElement.lang : 'ko';
  const BASE = LANG === 'ko' ? '' : `/${LANG}`;
  const LOCALE = { ko: 'ko-KR', en: 'en-US', ja: 'ja-JP' }[LANG];
  const path = window.location.pathname.replace(/\/$/, '').replace(/^\/(en|ja)(?=\/)/, '');
  // 언어 전환은 홈이 아니라 지금 보고 있는 화면의 다른 언어판으로 보낸다
  document.querySelectorAll('.lang-switch a[hreflang]').forEach(link => {
    const code = link.getAttribute('hreflang');
    link.href = `${code === 'ko' ? '' : `/${code}`}${path || '/'}${location.search}`;
  });
  const plural = (n, one, many) => `${n.toLocaleString(LOCALE)} ${n === 1 ? one : many}`;
  // 화면 문구 — 한국어가 기준이고, 영어·일본어는 직역이 아니라 각 언어에서 자연스러운 표현으로 옮긴다.
  // 앱(vernissage/mobile/locales)의 용어와 맞춘다: Docent·Journal·Art fairs · Biennials / ドーセント·記録·アートの好みテスト
  const T = {
    ko: {
      untitledEvent: '이름 없는 행사', pages: '페이지', prevPage: '이전 페이지', nextPage: '다음 페이지',
      noMatch: q => `‘${q}’에 맞는 결과가 없어요.`, count: n => `${n.toLocaleString(LOCALE)}건`,
      loadFailed: '정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      backExhibitions: '← 전시 목록', exhibitionNoDesc: '전시 상세 정보는 준비 중입니다.', exhibitionSite: '전시 공식 홈페이지 ↗',
      exhibitionTabs: { ongoing: '진행 중', upcoming: '예정', ended: '지난 전시' },
      exhibitionsTitle: '전시 찾기', exhibitionsIntro: '지금 보고 싶은 전시를 찾아보세요.',
      closingSoon: '7일 안에 끝나는 전시', justOpened: '최근 7일 안에 시작한 전시',
      exhibitionListing: { ongoing: '진행 중인 전시 전체', upcoming: '예정된 전시 전체', ended: '최근 지난 전시' },
      exhibitionSearch: '전시명·미술관으로 검색', noExhibitions: '표시할 전시가 없습니다.',
      mapTitle: '진행 중인 전시 지도', mapCount: n => `전시 ${n}건`,
      mapHintPins: '핀을 누르면 해당 미술관의 진행 중인 전시를 볼 수 있어요.',
      mapHintAll: '나라를 고르면 그 나라 미술관의 위치를 핀으로 볼 수 있어요.',
      mapHintNone: '이 나라에는 아직 지도에 표시할 미술관 위치가 없어요.',
      backNotes: '← 도슨트 목록', notesTitle: '도슨트', notesIntro: '작품과 장소에 얽힌 이야기를 천천히 읽어보세요.', noNotes: '표시할 도슨트 글이 없습니다.', cardLoading: '작품 정보를 불러오는 중이에요.', cardUntitled: '제목 없는 작품', cardUnavailable: '작품 보기',
      backEvents: '← 비엔날레 · 아트페어 목록', eventNoDesc: '행사 상세 정보는 준비 중입니다.', eventSite: '행사 공식 홈페이지 ↗',
      tabCalendar: '연간 캘린더', tabList: '진행 중 · 예정',
      eventsTitle: '비엔날레 · 아트페어', eventsIntro: '세계 곳곳에서 열리는 예술 행사를 살펴보세요.',
      worldwide: '전 세계', more: '더 보기', less: '접기',
      eventStatus: { ongoing: '진행 중', upcoming: '개막 예정', tba: '일정 미정', ended: '종료' },
      noEvents: '표시할 행사가 없습니다.', noEventsAtAll: '등록된 행사가 없습니다.', noEventsYear: '이 해에 등록된 행사가 없어요.',
      prevYear: '이전 해', nextYear: '다음 해', year: y => `${y}년`, eventCount: n => `${n}개 행사`, month: m => `${m}월`, today: '오늘',
      shortDate: (y, m, d, sameYear) => `${sameYear ? '' : `${y}. `}${m}.${d}`,
      taste: {
        title: '나의 예술 취향은?', question: '나는 어떤 작품에 마음이 끌릴까요?',
        lead1: '전시를 보다 보면 이유는 잘 모르겠지만<br />유난히 눈길이 머무는 작품이 있죠.',
        lead2: '마음이 가는 쪽을 하나씩 골라보세요.<br />선택 끝에 나만의 예술 취향을 만나볼 수 있어요.',
        tipsTitle: '이렇게 답하면 좋아요', tips: ['아는 작품보다 더 끌리는 쪽을 골라보세요.', '익숙한 장면을 떠올리면 더 쉬워요.', '오래 고민하지 말고 첫 느낌대로 골라주세요.'],
        note: '로그인 없이 바로 할 수 있어요', start: n => `${n}문항 시작하기`,
        referenceTitle: '어떤 연구를 참고했나요?',
        referenceText: '이 테스트는 심리 진단도, 정해진 성격 유형도 아닙니다. 미학 심리학에서 작품 반응을 살필 때 자주 다루는 표현 방식, 복잡성, 정서성, 색감, 친숙함과 새로움의 차원을 일상적인 선택 문장으로 바꿔 구성했어요.',
        helper: '가장 마음에 드는 답을 골라주세요.', scoring: '취향을 읽고 있어요…', recommendations: '이런 작품을 만나보세요', retake: '다시 하기',
      },
    },
    en: {
      untitledEvent: 'Untitled event', pages: 'Pages', prevPage: 'Previous page', nextPage: 'Next page',
      noMatch: q => `Nothing matches “${q}”.`, count: n => n.toLocaleString(LOCALE),
      loadFailed: 'Something went wrong while loading. Please try again in a moment.',
      backExhibitions: '← All exhibitions', exhibitionNoDesc: 'More details about this exhibition are coming soon.', exhibitionSite: 'Official exhibition website ↗',
      exhibitionTabs: { ongoing: 'On now', upcoming: 'Coming soon', ended: 'Past' },
      exhibitionsTitle: 'Exhibitions', exhibitionsIntro: 'Find a show worth seeing right now.',
      closingSoon: 'Closing within 7 days', justOpened: 'Opened in the past week',
      exhibitionListing: { ongoing: 'All exhibitions on now', upcoming: 'All upcoming exhibitions', ended: 'Recently closed' },
      exhibitionSearch: 'Search exhibitions or museums', noExhibitions: 'No exhibitions to show.',
      mapTitle: 'Exhibitions on now, mapped', mapCount: n => plural(n, 'exhibition', 'exhibitions'),
      mapHintPins: 'Tap a pin to see what’s on at that museum.',
      mapHintAll: 'Pick a country to see its museums pinned on the map.',
      mapHintNone: 'We don’t have museum locations to show for this country yet.',
      backNotes: '← All docent stories', notesTitle: 'Docent', notesIntro: 'Slow down and enjoy the stories behind the art and the places it lives.', noNotes: 'No docent stories to show yet.', cardLoading: 'Loading artwork…', cardUntitled: 'Untitled artwork', cardUnavailable: 'View artwork',
      backEvents: '← All biennials & art fairs', eventNoDesc: 'More details about this event are coming soon.', eventSite: 'Official event website ↗',
      tabCalendar: 'Yearly calendar', tabList: 'On now & upcoming',
      eventsTitle: 'Biennials & Art Fairs', eventsIntro: 'See what’s happening in the art world, wherever it’s happening.',
      worldwide: 'Worldwide', more: 'More', less: 'Less',
      eventStatus: { ongoing: 'On now', upcoming: 'Upcoming', tba: 'Dates TBA', ended: 'Ended' },
      noEvents: 'No events to show.', noEventsAtAll: 'No events listed yet.', noEventsYear: 'No events listed for this year.',
      prevYear: 'Previous year', nextYear: 'Next year', year: y => String(y), eventCount: n => plural(n, 'event', 'events'),
      month: m => new Intl.DateTimeFormat(LOCALE, { month: 'short', timeZone: 'UTC' }).format(Date.UTC(2000, m - 1, 1)), today: 'Today',
      shortDate: (y, m, d, sameYear) => new Intl.DateTimeFormat(LOCALE, { month: 'short', day: 'numeric', ...(sameYear ? {} : { year: 'numeric' }), timeZone: 'UTC' }).format(Date.UTC(y, m - 1, d)),
      taste: {
        title: 'What’s your taste in art?', question: 'What kind of art draws you in?',
        lead1: 'At every exhibition, there’s that one piece<br />you keep coming back to — even if you can’t say why.',
        lead2: 'Just pick whichever speaks to you, one at a time.<br />By the end, you’ll see what your taste in art looks like.',
        tipsTitle: 'A few tips', tips: ['Go with what draws you in, not what you know.', 'Picturing a familiar scene makes it easier.', 'Don’t overthink it — trust your first impression.'],
        note: 'No sign-in needed', start: n => `Start the ${n} questions`,
        referenceTitle: 'What research is this based on?',
        referenceText: 'This isn’t a psychological diagnosis, and it won’t box you into a personality type. It draws on dimensions that the psychology of aesthetics often uses to study how people respond to art — style of expression, complexity, emotion, color, and familiarity versus novelty — and turns them into everyday choices.',
        helper: 'Pick the one that draws you in more.', scoring: 'Reading your taste…', recommendations: 'Art you might love', retake: 'Take it again',
      },
    },
    ja: {
      untitledEvent: '名称未定のイベント', pages: 'ページ', prevPage: '前のページ', nextPage: '次のページ',
      noMatch: q => `「${q}」に一致する結果はありません。`, count: n => `${n.toLocaleString(LOCALE)}件`,
      loadFailed: '情報を読み込めませんでした。しばらくしてからもう一度お試しください。',
      backExhibitions: '← 展覧会一覧', exhibitionNoDesc: 'この展覧会の詳しい情報は準備中です。', exhibitionSite: '展覧会の公式サイト ↗',
      exhibitionTabs: { ongoing: '開催中', upcoming: '開催予定', ended: '終了した展覧会' },
      exhibitionsTitle: '展覧会を探す', exhibitionsIntro: '今見に行きたい展覧会を探してみましょう。',
      closingSoon: 'まもなく終了（7日以内）', justOpened: 'この1週間に始まった展覧会',
      exhibitionListing: { ongoing: '開催中の展覧会一覧', upcoming: '開催予定の展覧会一覧', ended: '最近終了した展覧会' },
      exhibitionSearch: '展覧会名・美術館名で検索', noExhibitions: '表示できる展覧会はありません。',
      mapTitle: '開催中の展覧会マップ', mapCount: n => `展覧会${n}件`,
      mapHintPins: 'ピンをタップすると、その美術館で開催中の展覧会を見られます。',
      mapHintAll: '国を選ぶと、その国の美術館の場所がピンで表示されます。',
      mapHintNone: 'この国には、まだ地図に表示できる美術館がありません。',
      backNotes: '← ドーセント一覧', notesTitle: 'ドーセント', notesIntro: '作品や場所にまつわる物語を、ゆっくり味わってみてください。', noNotes: '表示できるドーセント記事はありません。', cardLoading: '作品情報を読み込んでいます。', cardUntitled: '無題の作品', cardUnavailable: '作品を見る',
      backEvents: '← ビエンナーレ・アートフェア一覧', eventNoDesc: 'このイベントの詳しい情報は準備中です。', eventSite: 'イベントの公式サイト ↗',
      tabCalendar: '年間カレンダー', tabList: '開催中・開催予定',
      eventsTitle: 'ビエンナーレ・アートフェア', eventsIntro: '世界各地で開かれるアートイベントをチェックしましょう。',
      worldwide: 'すべての国', more: 'もっと見る', less: '閉じる',
      eventStatus: { ongoing: '開催中', upcoming: '開幕予定', tba: '日程未定', ended: '終了' },
      noEvents: '表示できるイベントはありません。', noEventsAtAll: '登録されたイベントはありません。', noEventsYear: 'この年に登録されたイベントはありません。',
      prevYear: '前の年', nextYear: '次の年', year: y => `${y}年`, eventCount: n => `${n}件のイベント`, month: m => `${m}月`, today: '今日',
      shortDate: (y, m, d, sameYear) => `${sameYear ? '' : `${y}/`}${m}/${d}`,
      taste: {
        title: 'あなたのアートの好みは？', question: 'わたしはどんな作品に心惹かれるのだろう？',
        lead1: '展覧会を見ていると、理由はよくわからないけれど<br />なぜか目が留まる作品がありますよね。',
        lead2: '心が向くほうをひとつずつ選んでみてください。<br />選び終えると、自分だけのアートの好みに出会えます。',
        tipsTitle: '答えるときのコツ', tips: ['知っている作品より、惹かれるほうを選んでください。', '身近な場面を思い浮かべると選びやすくなります。', '長く悩まず、第一印象で選んでください。'],
        note: 'ログイン不要ですぐに始められます', start: n => `${n}問をはじめる`,
        referenceTitle: 'どんな研究を参考にしていますか？',
        referenceText: 'このテストは心理診断でも、決められた性格タイプに当てはめるものでもありません。美学心理学で作品への反応を調べる際によく扱われる「表現のしかた」「複雑さ」「情緒性」「色彩」「親しみやすさと新しさ」といった観点を、日常的な選択肢に置き換えて構成しました。',
        helper: '惹かれるほうを選んでください。', scoring: 'あなたの好みを読み解いています…', recommendations: 'こんな作品に出会ってみませんか', retake: 'もう一度テストする',
      },
    },
  }[LANG];
  const escape = (value = '') => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const date = value => value ? new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium' }).format(new Date(value)) : '';
  const eventTitle = item => item.display_title || item.title || item.series?.name || T.untitledEvent;
  const eventPlace = item => [item.city || item.series?.home_city, item.country || item.series?.home_country].filter(Boolean).join(' · ');
  const dday = (end, today) => {
    if (!end || !today) return '';
    const days = Math.round((Date.parse(end) - Date.parse(today)) / 86400000);
    return days > 365 ? '' : (days <= 0 ? 'D-day' : `D-${days}`);
  };
  const get = async endpoint => {
    const response = await fetch(`/api/vernissage/public-web/${endpoint}`, { headers: { 'X-App-Language': LANG } });
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.json();
  };
  const CARD_PATHS = {
    artwork: 'artworks', artist: 'artists', art_concept: 'art-concepts', art_figure: 'art-figures',
    museum: 'museums', exhibition: 'exhibitions', art_event: 'art-events',
  };
  const CARD_RESPONSE_KEYS = {
    artwork: 'artwork', artist: 'artist', art_concept: 'concept', art_figure: 'figure',
    museum: 'museum', exhibition: 'exhibition', art_event: 'event',
  };
  // 도슨트 원문은 편집기에서 Markdown 이미지와 참조 카드를 함께 저장한다. 이전에는
  // 원문 전체를 escape해서 이미지 문법과 [[cards:...]]가 그대로 노출됐다. HTML을 신뢰하지
  // 않고, 여기서 지원하는 두 문법만 HTML로 바꾼다.
  const docentText = value => escape(value)
    .replace(/\*\*([^*\n](?:[^*\n]|\*(?!\*))*)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br />');
  const docentContent = (content = '') => {
    const token = /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)|\[\[cards:((?:(?:artwork|artist|art_concept|art_figure|museum|exhibition|art_event):[0-9]+)(?:,(?:artwork|artist|art_concept|art_figure|museum|exhibition|art_event):[0-9]+)*)\]\]|\[\[image:(https?:\/\/[^\]|]+)(?:\|([^\]]*))?\]\]/g;
    let cursor = 0; let match; const parts = [];
    const text = String(content);
    const addText = value => {
      if (!value) return;
      parts.push(docentText(value));
    };
    while ((match = token.exec(text))) {
      addText(text.slice(cursor, match.index));
      if (match[1] !== undefined) {
        parts.push(`<figure class="docent-image"><img src="${escape(match[2])}" alt="${escape(match[1])}" loading="lazy" /></figure>`);
      } else if (match[3] !== undefined) {
        const cards = match[3].split(',').map(reference => {
          const [kind, id] = reference.split(':');
          return `<a class="docent-card" data-docent-card-kind="${kind}" data-docent-card-id="${id}" href="${BASE}/${CARD_PATHS[kind]}/${id}"><span class="docent-card-image" aria-hidden="true"></span><span class="docent-card-copy">${escape(T.cardLoading)}</span></a>`;
        });
        parts.push(cards.length > 1 ? `<div class="docent-card-grid" data-count="${cards.length}">${cards.join('')}</div>` : cards[0]);
      } else {
        const caption = match[5] || '';
        parts.push(`<figure class="docent-image"><img src="${escape(match[4])}" alt="${escape(caption)}" loading="lazy" />${caption ? `<figcaption>${escape(caption)}</figcaption>` : ''}</figure>`);
      }
      cursor = token.lastIndex;
    }
    addText(text.slice(cursor));
    // 줄바꿈만 사이에 둔 이미지들은 하나의 사진 묶음으로 보고 2~3열로 배치한다.
    return parts.join('').replace(/(?:<figure class="docent-image">(?:(?!<\/figure>)[\s\S])*<\/figure>(?:<br \/>)*){2,}/g, group => {
      const images = group.match(/<figure class="docent-image">(?:(?!<\/figure>)[\s\S])*<\/figure>/g) || [];
      return `<div class="docent-image-grid" data-count="${images.length}">${images.join('')}</div>`;
    });
  };
  const docentCardRequests = new Map();
  const docentCardQueue = [];
  let activeDocentCardRequests = 0;
  const runDocentCardRequest = task => new Promise((resolve, reject) => {
    docentCardQueue.push(async () => {
      activeDocentCardRequests += 1;
      try { resolve(await task()); } catch (error) { reject(error); }
      finally {
        activeDocentCardRequests -= 1;
        const next = docentCardQueue.shift();
        if (next) next();
      }
    });
    if (activeDocentCardRequests < 4) {
      const next = docentCardQueue.shift();
      if (next) next();
    }
  });
  const docentCardData = (kind, id) => {
    const key = `${kind}:${id}`;
    if (!docentCardRequests.has(key)) {
      const request = runDocentCardRequest(() => get(`${CARD_PATHS[kind]}/${id}`)).catch(error => {
        docentCardRequests.delete(key);
        throw error;
      });
      docentCardRequests.set(key, request);
    }
    return docentCardRequests.get(key);
  };
  // 작품 데이터는 수집처에 따라 대표 이미지가 여러 필드·배열 안에 들어올 수 있다.
  // 카드가 비어 보이지 않도록 URL 후보를 한 곳에서 정규화한다.
  const imageUrl = value => {
    if (typeof value === 'string') return /^https?:\/\//i.test(value) ? value : '';
    if (Array.isArray(value)) return value.map(imageUrl).find(Boolean) || '';
    if (!value || typeof value !== 'object') return '';
    return imageUrl(value.url || value.src || value.image_url || value.thumbnail_url || value.original_url || value.medium_url || value.large_url || value.file_url || value.source_url);
  };
  const artworkImage = item => {
    if (!item || typeof item !== 'object') return '';
    const candidates = [
      item.image_url, item.thumbnail_url, item.image, item.thumbnail, item.cover_image, item.primary_image,
      item.cover_url, item.photo_url, item.primary_image_url, item.imageUrl, item.thumbnailUrl,
      item.image_urls, item.images, item.photos, item.attachments,
    ];
    return candidates.map(imageUrl).find(Boolean) || '';
  };
  const hydrateDocentCards = root => root.querySelectorAll('[data-docent-card-id]').forEach(async card => {
    const { docentCardKind: kind, docentCardId: id } = card.dataset;
    try {
      const data = await docentCardData(kind, id);
      const responseKey = CARD_RESPONSE_KEYS[kind];
      const item = data[responseKey] || data[kind] || data.item
        || data.data?.[responseKey] || data.data?.[kind] || data.data || data;
      const image = artworkImage(item);
      const title = item.title || item.name || item.display_name || item.display_title || T.cardUntitled;
      card.querySelector('.docent-card-copy').textContent = title;
      if (image) {
        const imageSlot = card.querySelector('.docent-card-image');
        imageSlot.innerHTML = `<img src="${escape(image)}" alt="" loading="lazy" />`;
      }
    } catch (_) {
      // 카드 데이터를 가져오지 못해도 편집기 내부 토큰을 독자에게 노출하지 않는다.
      card.querySelector('.docent-card-copy').textContent = T.cardUnavailable;
    }
  });
  // 진행 중·예정 목록은 다음 페이지가 있으면 이어 받아 모두 보여 준다(지난 목록은 서버가 최근 50건 한 페이지만 준다).
  const getAll = async (endpoint, params) => {
    const first = await get(`${endpoint}?${params}`); let last = first;
    for (let page = 2; last.has_next && page <= 50; page += 1) {
      params.set('page', page); last = await get(`${endpoint}?${params}`); first.items.push(...last.items);
    }
    return first;
  };
  let listingRun = 0;

  // 목록 전체 — 받아 둔 항목 안에서 검색하고, 한 페이지에 LISTING_PAGE_SIZE개씩 나눠 보여 준다.
  const LISTING_PAGE_SIZE = 24;
  const listingSection = (title, placeholder) => `<section class="listing-all"><div class="listing-all-head"><h2 class="listing-all-title">${title} <span class="listing-count"></span></h2><input class="listing-search" type="search" placeholder="${placeholder}" aria-label="${placeholder}" autocomplete="off" /></div><div class="grid"></div><nav class="pager" aria-label="${T.pages}"></nav></section>`;
  const searchKey = value => String(value || '').normalize('NFC').toLowerCase().replace(/\s+/g, '');
  const pagerHtml = (page, pages) => {
    const numbers = [...new Set([1, page - 1, page, page + 1, pages])].filter(n => n >= 1 && n <= pages).sort((a, b) => a - b);
    const items = numbers.flatMap((n, i) => [...(i && n - numbers[i - 1] > 1 ? ['<span class="pager-gap">…</span>'] : []), `<button type="button" data-page="${n}"${n === page ? ' aria-current="page"' : ''}>${n}</button>`]);
    return `<button type="button" data-page="${page - 1}" aria-label="${T.prevPage}"${page === 1 ? ' disabled' : ''}>‹</button>${items.join('')}<button type="button" data-page="${page + 1}" aria-label="${T.nextPage}"${page === pages ? ' disabled' : ''}>›</button>`;
  };
  function pagedListing(root, items, card, fields, empty) {
    if (!root) return;
    const grid = root.querySelector('.grid'); const pager = root.querySelector('.pager');
    const input = root.querySelector('.listing-search'); const count = root.querySelector('.listing-count');
    const keys = items.map(item => searchKey(fields(item).filter(Boolean).join(' ')));
    let matches = items; let page = 1;
    const draw = scroll => {
      const pages = Math.max(1, Math.ceil(matches.length / LISTING_PAGE_SIZE));
      page = Math.min(Math.max(page, 1), pages);
      grid.innerHTML = matches.slice((page - 1) * LISTING_PAGE_SIZE, page * LISTING_PAGE_SIZE).map(card).join('')
        || `<p class="error">${input.value.trim() ? T.noMatch(escape(input.value.trim())) : empty}</p>`;
      count.textContent = items.length ? T.count(matches.length) : '';
      pager.innerHTML = pages > 1 ? pagerHtml(page, pages) : '';
      if (scroll) root.scrollIntoView({ block: 'start' });
    };
    input.addEventListener('input', () => {
      // 띄어 쓴 단어는 각각 들어 있어야 한다(예: "모네 리움")
      const terms = input.value.split(/\s+/).map(searchKey).filter(Boolean);
      matches = terms.length ? items.filter((_, i) => terms.every(term => keys[i].includes(term))) : items;
      page = 1; draw(false);
    });
    pager.addEventListener('click', event => {
      const button = event.target.closest('[data-page]');
      if (!button || button.disabled) return;
      page = Number(button.dataset.page); draw(true);
    });
    draw(false);
  }
  const fail = () => { app.innerHTML = `<p class="error">${T.loadFailed}</p>`; };
  const exhibitionCard = item => `<a class="card" href="${BASE}/exhibitions/${item.id}">${item.image_url ? `<img class="thumb" src="${escape(item.image_url)}" alt="" />` : '<span class="thumb"></span>'}<div class="body"><p class="meta">${escape(item.museum?.name || item.place_name || '')} · ${date(item.start_date)} — ${date(item.end_date)}</p><h2>${escape(item.title)}</h2></div></a>`;
  const noteCard = item => `<a class="card" href="${BASE}/docent/notes/${item.id}">${item.thumbnail_url ? `<img class="thumb" src="${escape(item.thumbnail_url)}" alt="" />` : '<span class="thumb"></span>'}<div class="body"><p class="meta">${escape(item.entity_label || '')} · ${date(item.published_at)}</p><h2>${escape(item.title)}</h2><p>${escape(item.excerpt || '')}</p></div></a>`;
  // 국가 코드 → 국기 이모지(지역 표시 문자 두 개)
  const flag = code => String.fromCodePoint(...[...code].map(c => 0x1F1A5 + c.charCodeAt(0)));
  const eventFlag = item => item.country_code ? `<span class="flag" aria-hidden="true">${flag(item.country_code)}</span> ` : '';
  const regionName = (() => {
    try { const names = new Intl.DisplayNames([LANG], { type: 'region' }); return code => names.of(code) || code; } catch { return code => code; }
  })();
  // 나라를 고르면 지도를 옮길 영역 [남, 서, 북, 동] — 백엔드 app/core/countries.py의 나라 목록과 맞춘다.
  // 영토가 넓은 나라는 미술관이 모인 본토·주요 지역 위주로 잡았다.
  const COUNTRY_BOUNDS = {
    KR: [33.0, 124.6, 38.7, 130.0], JP: [30.9, 129.4, 45.6, 145.9], CN: [18.0, 73.5, 53.6, 134.8], HK: [22.15, 113.82, 22.57, 114.44],
    MO: [22.10, 113.52, 22.22, 113.60], TW: [21.9, 120.0, 25.3, 122.0], SG: [1.20, 103.6, 1.48, 104.1], TH: [5.6, 97.3, 20.5, 105.7],
    VN: [8.4, 102.1, 23.4, 109.5], ID: [-11.0, 95.0, 6.1, 141.0], MY: [0.85, 99.6, 7.4, 119.3], PH: [4.6, 116.9, 21.1, 126.6],
    IN: [6.7, 68.1, 35.5, 97.4], AE: [22.6, 51.5, 26.1, 56.4], QA: [24.5, 50.7, 26.2, 51.7], IL: [29.5, 34.2, 33.3, 35.9],
    TR: [35.8, 25.7, 42.1, 44.8], US: [24.5, -125.0, 49.4, -66.9], CA: [41.7, -141.0, 70.0, -52.6], MX: [14.5, -118.4, 32.7, -86.7],
    BR: [-33.8, -74.0, 5.3, -34.8], AR: [-55.1, -73.6, -21.8, -53.6], CL: [-56.0, -75.7, -17.5, -66.4], CO: [-4.2, -79.0, 12.5, -66.9],
    GB: [49.9, -8.2, 58.7, 1.8], IE: [51.4, -10.5, 55.4, -6.0], FR: [41.3, -5.2, 51.1, 9.6], DE: [47.3, 5.9, 55.1, 15.0],
    IT: [36.6, 6.6, 47.1, 18.5], ES: [36.0, -9.3, 43.8, 3.3], PT: [36.9, -9.5, 42.2, -6.2], NL: [50.75, 3.36, 53.55, 7.23],
    BE: [49.5, 2.55, 51.5, 6.4], LU: [49.45, 5.73, 50.18, 6.53], CH: [45.8, 5.96, 47.81, 10.49], AT: [46.37, 9.53, 49.02, 17.16],
    DK: [54.56, 8.08, 57.75, 12.69], SE: [55.3, 11.1, 69.1, 24.2], NO: [57.9, 4.6, 71.2, 31.1], FI: [59.8, 20.5, 70.1, 31.6],
    PL: [49.0, 14.1, 54.84, 24.15], CZ: [48.55, 12.09, 51.06, 18.86], HU: [45.74, 16.11, 48.59, 22.9], GR: [34.8, 19.4, 41.75, 28.25],
    RU: [43.0, 28.0, 62.0, 62.0], AU: [-43.7, 113.3, -10.6, 153.6], NZ: [-47.3, 166.4, -34.4, 178.6], ZA: [-34.9, 16.4, -22.1, 32.9],
    EG: [22.0, 24.7, 31.7, 36.9], MA: [27.6, -13.2, 35.9, -1.0],
  };
  const WORLD_BOUNDS = [[-45, -130], [65, 150]];

  async function exhibitions(id) {
    if (id) {
      const data = await get(`exhibitions/${id}`); const item = data.exhibition;
      document.title = `${item.title} | Vernissage`;
      app.innerHTML = `<article class="detail"><a class="back" href="${BASE}/exhibitions">${T.backExhibitions}</a><h1>${escape(item.title)}</h1><p class="meta">${escape(item.museum?.name || item.place_name || '')} · ${date(item.start_date)} — ${date(item.end_date)}</p>${item.image_url ? `<img class="detail-image" src="${escape(item.image_url)}" alt="${escape(item.title)}" />` : ''}<p class="detail-text">${escape(item.description || T.exhibitionNoDesc)}</p>${item.homepage_url ? `<p><a class="back" href="${escape(item.homepage_url)}" target="_blank" rel="noopener">${T.exhibitionSite}</a></p>` : ''}</article>`;
      return;
    }
    const params = new URLSearchParams(location.search);
    const query = new URLSearchParams({ tab: params.get('tab') || 'ongoing' });
    if (/^([A-Z]{2}|ALL)$/.test(params.get('country') || '')) query.set('country', params.get('country'));
    const run = ++listingRun;
    const data = await getAll('exhibitions', query);
    if (run !== listingRun) return; // 그 사이 다른 나라를 골랐다
    const tabs = Object.entries(T.exhibitionTabs);
    const countryLink = (code, icon, label) => `<a class="${data.country === code ? 'active' : ''}" href="${BASE}/exhibitions?tab=${data.tab}&country=${code}" data-country="${code}"><span class="flag" aria-hidden="true">${icon}</span>${escape(label)}</a>`;
    const countries = (data.countries || []).map(code => countryLink(code, flag(code), regionName(code))).join('');
    const highlights = (label, title, items, badges, withImages = items?.some(item => item.image_url)) => !items?.length ? '' : `<section class="listing-highlight"><p class="highlight-label">${label}</p><h2>${title}</h2><div class="mini-grid">${items.map(item => `<a class="mini-card" href="${BASE}/exhibitions/${item.id}">${item.image_url ? `<img class="mini-thumb" src="${escape(item.image_url)}" alt="" loading="lazy" />` : withImages ? '<span class="mini-thumb"></span>' : ''}${badges ? `<span class="badge">${dday(item.end_date, data.today)}</span>` : ''}<strong>${escape(item.title)}</strong><p class="meta">${escape(item.museum?.name || item.place_name || '')}</p></a>`).join('')}</div></section>`;
    app.innerHTML = `<h1>${T.exhibitionsTitle}</h1><p class="intro">${T.exhibitionsIntro}</p><div class="tabs">${tabs.map(([key, label]) => `<a class="${key === data.tab ? 'active' : ''}" href="${BASE}/exhibitions?tab=${key}">${label}</a>`).join('')}</div>${countries ? `<div class="tabs country-tabs">${countries}</div>` : ''}${data.tab === 'ongoing' ? `<div id="exhibition-map-root"></div>${highlights('Closing soon', T.closingSoon, data.ending_soon, true)}${highlights('Just opened', T.justOpened, data.just_opened, false)}` : ''}${listingSection(T.exhibitionListing[data.tab], T.exhibitionSearch)}`;
    pagedListing(app.querySelector('.listing-all'), data.items, exhibitionCard, item => [item.title, item.museum?.name, item.place_name], T.noExhibitions);
    // 나라를 바꿔도 지도는 그대로 두고 그 나라로 옮긴다
    const kept = data.tab === 'ongoing' && mapView ? mapView.root : null;
    if (kept) app.querySelector('#exhibition-map-root').replaceWith(kept);
    app.querySelectorAll('[data-country]').forEach(link => link.addEventListener('click', event => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
      event.preventDefault();
      history.pushState(null, '', link.getAttribute('href'));
      app.querySelectorAll('[data-country]').forEach(other => other.classList.toggle('active', other === link));
      exhibitions().catch(fail);
    }));
    if (data.tab === 'ongoing') {
      // 지도 CDN이 차단되어도 전시 목록 전체가 오류 화면으로 바뀌면 안 된다.
      renderMap(data.map_pins || [], data.today, data.country).catch(() => {
        const root = document.querySelector('#exhibition-map-root');
        if (root) root.innerHTML = `<p class="error">${T.loadFailed}</p>`;
        mapView = null;
      });
    }
    else mapView = null;
  }
  async function notes(id) {
    if (id) {
      const data = await get(`docent/notes/${id}`); const note = data.note;
      document.title = `${note.title} | Vernissage`;
      app.innerHTML = `<article class="detail"><a class="back" href="${BASE}/docent/notes">${T.backNotes}</a><h1>${escape(note.title)}</h1><p class="meta">${date(note.published_at)}</p>${note.thumbnail_url ? `<img class="detail-image" src="${escape(note.thumbnail_url)}" alt="" />` : ''}<div class="detail-text docent-content">${docentContent(note.content || note.excerpt || '')}</div></article>`;
      hydrateDocentCards(app);
      return;
    }
    const data = await get('docent/notes');
    app.innerHTML = `<h1>${T.notesTitle}</h1><p class="intro">${T.notesIntro}</p><div class="grid">${data.items.map(noteCard).join('') || `<p class="error">${T.noNotes}</p>`}</div>`;
  }
  async function events(id) {
    if (id) {
      const data = await get(`art-events/${id}`); const item = data.event;
      const title = eventTitle(item); const officialUrl = item.official_url || item.series?.official_url;
      document.title = `${title} | Vernissage`;
      app.innerHTML = `<article class="detail"><a class="back" href="${BASE}/art-events">${T.backEvents}</a><h1>${escape(title)}</h1><p class="meta">${escape(eventPlace(item))} · ${date(item.start_date)} — ${date(item.end_date)}</p>${item.image_url ? `<img class="detail-image" src="${escape(item.image_url)}" alt="${escape(title)}" />` : ''}<p class="detail-text">${escape(item.description || item.series?.description || T.eventNoDesc)}</p>${officialUrl ? `<p><a class="back" href="${escape(officialUrl)}" target="_blank" rel="noopener">${T.eventSite}</a></p>` : ''}</article>`;
      return;
    }
    // 탭: 연간 캘린더(/art-events, 기본) / 진행 중·예정 목록(?view=list, 나라 필터 &country=JP). 지난 행사는
    // 캘린더의 지난 연도로 본다 — 예전 주소(?view=calendar, 지난 행사 ?status=ended)는 캘린더 탭으로 정리한다.
    const params = new URLSearchParams(location.search);
    const calendar = params.get('view') !== 'list';
    let country = !calendar && /^[A-Z]{2}$/.test(params.get('country') || '') ? params.get('country') : 'ALL';
    const listUrl = code => `${BASE}/art-events?view=list${code === 'ALL' ? '' : `&country=${code}`}`;
    const canonical = calendar ? `${BASE}/art-events` : listUrl(country);
    if (location.pathname + location.search !== canonical) history.replaceState(null, '', canonical);
    const run = ++listingRun;
    const data = await getAll('art-events', new URLSearchParams({ status: 'current' }));
    if (run !== listingRun) return;
    const tabs = `<div class="tabs"><a class="${calendar ? 'active' : ''}" href="${BASE}/art-events">${T.tabCalendar}</a><a class="${calendar ? '' : 'active'}" href="${BASE}/art-events?view=list">${T.tabList}</a></div>`;
    if (calendar) {
      app.innerHTML = `<h1>${T.eventsTitle}</h1><p class="intro">${T.eventsIntro}</p>${tabs}<section id="art-calendar" class="listing-highlight calendar"></section>`;
      renderCalendar(data.calendar_events || data.items, data.today);
      return;
    }
    // 나라 필터 — 행사가 있는 나라만, 한국 먼저·행사 많은 순. 나라를 모르는 회차는 "전 세계"에만 나온다.
    const counts = {};
    data.items.forEach(item => { if (item.country_code) counts[item.country_code] = (counts[item.country_code] || 0) + 1; });
    const codes = Object.keys(counts).sort((a, b) => (b === 'KR') - (a === 'KR') || counts[b] - counts[a] || regionName(a).localeCompare(regionName(b), LANG));
    if (country !== 'ALL' && !counts[country]) country = 'ALL';
    // 행사가 많은 상위 TOP_COUNTRIES개 나라만 보이고 나머지는 "더 보기"로 편다(고른 나라가 뒤쪽이면 펴 둔다)
    const TOP_COUNTRIES = 5;
    const countryLink = (code, icon, label, count, extra = false) => `<a href="${listUrl(code)}" data-event-country="${code}"${extra ? ' class="extra-country"' : ''}><span class="flag" aria-hidden="true">${icon}</span>${escape(label)}<span class="tab-count">${count}</span></a>`;
    const labels = T.eventStatus;
    const cards = items => `<div class="grid">${items.map(item => `<a class="card" href="${BASE}/art-events/${item.id}">${item.image_url ? `<img class="thumb" src="${escape(item.image_url)}" alt="" loading="lazy" />` : '<span class="thumb"></span>'}<div class="body">${item.status === 'ongoing' && dday(item.end_date, data.today) ? `<span class="badge">${dday(item.end_date, data.today)}</span>` : ''}<p class="meta">${eventFlag(item)}${escape(eventPlace(item))} · ${date(item.start_date)} — ${date(item.end_date)}</p><h2>${escape(eventTitle(item))}</h2></div></a>`).join('')}</div>`;
    app.innerHTML = `<h1>${T.eventsTitle}</h1><p class="intro">${T.eventsIntro}</p>${tabs}${codes.length ? `<div class="tabs country-tabs${codes.indexOf(country) >= TOP_COUNTRIES ? ' expanded' : ''}">${countryLink('ALL', '🌐', T.worldwide, data.items.length)}${codes.map((code, i) => countryLink(code, flag(code), regionName(code), counts[code], i >= TOP_COUNTRIES)).join('')}${codes.length > TOP_COUNTRIES ? `<button type="button" class="more-countries" aria-expanded="false">${T.more} <span class="tab-count">+${codes.length - TOP_COUNTRIES}</span></button>` : ''}</div>` : ''}<div id="event-list"></div>`;
    const list = app.querySelector('#event-list');
    const draw = () => {
      app.querySelectorAll('[data-event-country]').forEach(link => link.classList.toggle('active', link.dataset.eventCountry === country));
      const items = country === 'ALL' ? data.items : data.items.filter(item => item.country_code === country);
      list.innerHTML = ['ongoing', 'upcoming', 'tba'].map(key => [key, items.filter(item => item.status === key)]).filter(([, group]) => group.length).map(([key, group]) => `<section><h2>${labels[key]}</h2>${cards(group)}</section>`).join('') || `<p class="error">${T.noEvents}</p>`;
    };
    const more = app.querySelector('.more-countries');
    const setExpanded = open => {
      app.querySelector('.country-tabs').classList.toggle('expanded', open);
      more.setAttribute('aria-expanded', String(open));
      more.innerHTML = open ? T.less : `${T.more} <span class="tab-count">+${codes.length - TOP_COUNTRIES}</span>`;
    };
    if (more) {
      more.addEventListener('click', () => setExpanded(more.getAttribute('aria-expanded') !== 'true'));
      if (codes.indexOf(country) >= TOP_COUNTRIES) setExpanded(true);
    }
    // 나라를 바꿔도 다시 받지 않고, 받아 둔 목록을 거른다
    app.querySelectorAll('[data-event-country]').forEach(link => link.addEventListener('click', event => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
      event.preventDefault();
      country = link.dataset.eventCountry;
      history.pushState(null, '', link.getAttribute('href'));
      draw();
    }));
    draw();
  }
  // 지도는 한 번 만들고, 나라를 바꾸면 핀을 갈아 끼운 뒤 그 나라 영역으로 옮긴다.
  let mapView = null;
  let mapRender = 0;
  let leafletLoading = null;
  const loadLeaflet = () => leafletLoading ||= new Promise((resolve, reject) => {
    const stylesheet = document.createElement('link'); stylesheet.rel = 'stylesheet'; stylesheet.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'; document.head.append(stylesheet);
    const script = document.createElement('script'); script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'; script.onload = () => resolve(window.L); script.onerror = reject; document.head.append(script);
  });
  async function renderMap(pins, today, country) {
    const render = ++mapRender;
    if (!mapView) {
      const root = document.querySelector('#exhibition-map-root');
      if (!root) return;
      root.innerHTML = `<section class="listing-highlight"><p class="highlight-label">Map</p><h2>${T.mapTitle}</h2><div id="exhibition-map" class="map-canvas"></div><div class="map-panel"></div></section>`;
      mapView = { root, panel: root.querySelector('.map-panel'), ready: loadLeaflet().then(L => {
        const map = L.map(root.querySelector('.map-canvas'), { worldCopyJump: true }).setView([36.4, 127.8], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap' }).addTo(map);
        return { L, map, markers: L.layerGroup().addTo(map), moved: false };
      }) };
    }
    const view = mapView;
    const { L, map, markers } = await view.ready;
    if (render !== mapRender || view !== mapView) return; // 그 사이 다른 나라를 골랐다
    map.invalidateSize();
    const show = group => { view.panel.innerHTML = `<div class="map-items">${group.map(pin => `<article class="map-museum"><h3>${escape(pin.name)}</h3><p class="meta">${escape(pin.city || '')} · ${T.mapCount(pin.exhibitions.length)}</p><ul>${pin.exhibitions.map(item => `<li><a href="${BASE}/exhibitions/${item.id}">${escape(item.title)}</a>${dday(item.end_date, today) ? ` <span class="badge">${dday(item.end_date, today)}</span>` : ''}</li>`).join('')}</ul></article>`).join('')}</div>`; };
    view.panel.innerHTML = `<p>${pins.length ? T.mapHintPins : country === 'ALL' ? T.mapHintAll : T.mapHintNone}</p>`;
    markers.clearLayers();
    pins.forEach(pin => L.marker([pin.latitude, pin.longitude]).addTo(markers).bindTooltip(pin.name).on('click', () => show([pin])));
    const area = country === 'ALL' ? WORLD_BOUNDS : COUNTRY_BOUNDS[country] ? [COUNTRY_BOUNDS[country].slice(0, 2), COUNTRY_BOUNDS[country].slice(2)] : pins.length ? pins.map(pin => [pin.latitude, pin.longitude]) : null;
    if (!area) return;
    const options = { padding: [24, 24], maxZoom: 11 };
    const animate = view.moved && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    animate ? map.flyToBounds(area, { ...options, duration: 0.9 }) : map.fitBounds(area, options);
    view.moved = true;
  }
  // 연간 캘린더 — 1~12월 눈금 위에 회차 기간을 가로 막대로 그린다(간트 차트).
  const EVENT_STATUS = T.eventStatus;
  function renderCalendar(events, today) {
    const root = document.querySelector('#art-calendar'); if (!root) return;
    if (!events.length) { root.innerHTML = `<p class="highlight-label">Calendar</p><h2>${T.tabCalendar}</h2><p class="error">${T.noEventsAtAll}</p>`; return; }
    const DAY = 86400000;
    const todayTime = Date.parse(today);
    let year = Number(today.slice(0, 4));
    const years = events.filter(item => item.start_date).flatMap(item => [Number(item.start_date.slice(0, 4)), Number((item.end_date || item.start_date).slice(0, 4))]);
    const firstYear = Math.min(year, ...years); const lastYear = Math.max(year, ...years);
    const render = () => {
      const start = Date.UTC(year, 0, 1); const end = Date.UTC(year + 1, 0, 1); const span = end - start;
      const at = time => (Math.min(Math.max(time, start), end) - start) / span * 100;
      const short = value => { const [y, m, d] = value.split('-').map(Number); return T.shortDate(y, m, d, y === year); };
      const rows = events
        .filter(item => item.start_date)
        .map(item => ({ item, from: Date.parse(item.start_date), to: Date.parse(item.end_date || item.start_date) + DAY }))
        .filter(row => row.from < end && row.to > start)
        .sort((a, b) => a.from - b.from || a.to - b.to);
      const months = Array.from({ length: 12 }, (_, m) => ({ m, from: Date.UTC(year, m, 1), to: Date.UTC(year, m + 1, 1) }));
      const thisMonth = todayTime >= start && todayTime < end ? new Date(todayTime).getUTCMonth() : -1;
      const bar = ({ item, from, to }) => {
        const left = at(from); const width = at(to) - left;
        const dates = `${short(item.start_date)} – ${short(item.end_date || item.start_date)}`;
        return `<a class="tl-row status-${item.status}" href="${BASE}/art-events/${item.id}"><span class="tl-label"><strong>${eventFlag(item)}${escape(eventTitle(item))}</strong><small>${escape(eventPlace(item))}</small></span><span class="tl-lane"><span class="tl-bar${from < start ? ' cut-start' : ''}${to > end ? ' cut-end' : ''}" style="left:${left}%;width:${width}%"><span class="tl-dates${left + width > 72 ? ' before' : ''}">${dates}<span class="visually-hidden"> · ${EVENT_STATUS[item.status] || ''}</span></span></span></span></a>`;
      };
      root.innerHTML = `<div class="cal-head"><div><p class="highlight-label">Calendar</p><h2>${T.tabCalendar}</h2></div><div class="cal-controls"><button type="button" data-year="-1" aria-label="${T.prevYear}"${year <= firstYear ? ' disabled' : ''}>‹</button><strong>${T.year(year)}</strong><button type="button" data-year="1" aria-label="${T.nextYear}"${year >= lastYear ? ' disabled' : ''}>›</button></div></div>`
        + `<div class="tl-scroll"><div class="tl"><div class="tl-months" aria-hidden="true"><span class="tl-corner">${T.eventCount(rows.length)}</span><span class="tl-lane">${months.map(({ m, from, to }) => `<span class="${m === thisMonth ? 'now' : ''}" style="left:${at(from)}%;width:${at(to) - at(from)}%">${T.month(m + 1)}</span>`).join('')}</span></div>`
        + `<div class="tl-body"><div class="tl-grid" aria-hidden="true">${months.slice(1).map(({ from }) => `<i style="left:${at(from)}%"></i>`).join('')}${thisMonth >= 0 ? `<b class="tl-today" style="left:${at(todayTime)}%"><em>${T.today}</em></b>` : ''}</div>`
        + `${rows.map(bar).join('') || `<p class="tl-empty">${T.noEventsYear}</p>`}</div></div></div>`
        + `<p class="tl-legend"><span class="status-ongoing"><i></i>${EVENT_STATUS.ongoing}</span><span class="status-upcoming"><i></i>${EVENT_STATUS.upcoming}</span><span class="status-ended"><i></i>${EVENT_STATUS.ended}</span></p>`;
      root.querySelectorAll('[data-year]').forEach(button => button.onclick = () => { year += Number(button.dataset.year); render(); });
      // 올해를 보면 오늘 위치가 보이도록 가로 스크롤을 맞춘다(휴대폰)
      const scroller = root.querySelector('.tl-scroll'); const now = root.querySelector('.tl-today');
      if (now && scroller.scrollWidth > scroller.clientWidth) scroller.scrollLeft = now.getBoundingClientRect().left - scroller.getBoundingClientRect().left - scroller.clientWidth / 2;
    };
    render();
  }
  async function tasteTest() {
    const test = await getTaste('test'); let index = 0; const answers = [];
    const intro = () => {
      app.innerHTML = `<section class="quiz taste-intro"><p class="highlight-label">ART TASTE TEST · ${test.questions.length} QUESTIONS</p><h1>${T.taste.title}</h1><p class="taste-question">${T.taste.question}</p><p class="intro">${T.taste.lead1}</p><p class="intro">${T.taste.lead2}</p><div class="taste-guide"><h2>${T.taste.tipsTitle}</h2><ul>${T.taste.tips.map(tip => `<li>${tip}</li>`).join('')}</ul></div><p class="quiz-note">${T.taste.note}</p><button id="start-taste-test" class="start-taste-button" type="button">${T.taste.start(test.questions.length)} <span aria-hidden="true">→</span></button><section class="taste-reference"><h2>${T.taste.referenceTitle}</h2><p>${T.taste.referenceText}</p><ul><li>Vartanian et al. (2018), <em>Prediction of beauty and liking ratings for abstract and representational paintings</em>, PLOS ONE</li><li>Schlotz et al. (2021), <em>The Aesthetic Responsiveness Assessment (AReA)</em>, Psychology of Aesthetics, Creativity, and the Arts</li></ul></section></section>`;
      app.querySelector('#start-taste-test').onclick = async () => {
        app.querySelector('#start-taste-test').disabled = true;
        getTaste('web-events', { method: 'POST', body: JSON.stringify({ test_version: test.version }) }).catch(() => {});
        render();
      };
    };
    const render = () => { const question = test.questions[index]; app.innerHTML = `<section class="quiz"><p class="quiz-progress">${index + 1} / ${test.questions.length}</p><h1>${escape(question.prompt)}</h1><p class="intro">${T.taste.helper}</p>${question.options.map(option => `<button class="quiz-option" data-option="${escape(option.id)}">${escape(option.label)}</button>`).join('')}</section>`; app.querySelectorAll('[data-option]').forEach(button => button.onclick = () => { answers.push({ question_id: question.id, option_id: button.dataset.option }); index += 1; index < test.questions.length ? render() : score(); }); };
    const score = async () => {
      app.innerHTML = `<p class="loading">${T.taste.scoring}</p>`;
      try {
        const result = await getTaste('score', { method: 'POST', body: JSON.stringify({ test_version: test.version, answers }) });
        const recommendations = Array.isArray(result.recommendations) ? result.recommendations : [];
        app.innerHTML = `<section class="quiz-result"><p class="highlight-label">YOUR ART TASTE</p><h2>${escape(result.primary_profile_name)}</h2><p>${escape(result.primary_profile_tagline)}</p><p>${escape(result.primary_profile_description)}</p><h3>${T.taste.recommendations}</h3><ul>${recommendations.map(item => `<li>${escape(item.display_name || item.name)}</li>`).join('')}</ul><button class="quiz-option" onclick="location.reload()">${T.taste.retake}</button></section>`;
      } catch {
        // 이벤트 핸들러 안의 비동기 예외는 바깥 초기 렌더의 catch에 닿지 않는다.
        fail();
      }
    };
    intro();
  }
  const getTaste = async (endpoint, options = {}) => { const response = await fetch(`/api/vernissage/art-taste/${endpoint}`, { headers: { 'Content-Type': 'application/json', 'X-App-Language': LANG }, ...options }); if (!response.ok) throw new Error(`API ${response.status}`); return response.json(); };
  const match = path.match(/^\/(docent\/notes|exhibitions|art-events)(?:\/(\d+))?$/);
  if (path === '/art-taste-test') return tasteTest().catch(fail);
  if (!match) return fail();
  const [, section, id] = match;
  // 나라 탭은 주소만 바꾸므로, 뒤로·앞으로 가기 때 목록과 지도를 다시 맞춘다
  if (section === 'exhibitions' && !id) window.addEventListener('popstate', () => exhibitions().catch(fail));
  if (section === 'art-events' && !id) window.addEventListener('popstate', () => events().catch(fail));
  ({ 'docent/notes': () => notes(id), exhibitions: () => exhibitions(id), 'art-events': () => events(id) }[section])().catch(fail);
})();
