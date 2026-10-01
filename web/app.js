const state = {
  config: null,
  notices: [],
  payload: null,
  selectedId: null,
  loading: false,
  requestVersion: 0,
  requestController: null,
  feed: "notices",
  nearbyDistances: new Map(),
  push: { config: null, registration: null, subscribed: false },
  language: localStorage.getItem("school-news-language") || "ja",
};

const I18N = {
  ja: {
    "page.title": "おたより desk — 学校のお知らせベータ", "brand.subtitle": "東京の学校だより / ベータ", "status.public": "公開ページを確認中", "status.errorPrefix": "確認できませんでした：", "language.label": "表示言語", "theme.toggle": "テーマを切り替え", "detail.view": "詳細を見る",
    "hero.eyebrow": "保護者向けベータ · 公開ソース", "hero.title": "学校のお知らせを、<br><em>ひとつにまとめて</em>。",
    "hero.lede": "学校ごとに別々のページを探さなくても、学校だより・学年だより・行事のお知らせをここでまとめて確認できます。", "hero.note": "お子さまの学校・学年を選ぶと、必要なお知らせだけを表示します。",
    "metrics.schools": "登録校", "metrics.schoolsFoot": "小・中・高のサンプル", "metrics.notices": "今回の掲載数", "metrics.noticesFoot": "公開原文を基準", "metrics.wards": "対応地域", "metrics.wardsFoot": "23区拡張用レジストリ", "metrics.scanned": "最終確認", "metrics.scannedFoot": "キャッシュ5分・手動更新可",
    "workspace.eyebrow": "うちの子の学校デスク", "workspace.title": "今日確認したいお知らせ", "actions.refresh": "今すぐ更新", "actions.notifications": "通知を受け取る", "feeds.notices": "学校・生活", "feeds.events": "イベント",
    "groups.school": "学校", "groups.municipality": "武蔵野市・教育委員会／市役所", "groups.afterSchool": "学童",
    "filters.change": "学校・学年を変更", "filters.school": "学校", "filters.allSchools": "すべての学校", "filters.group": "発信元", "filters.allGroups": "すべての発信元", "filters.level": "学校種別", "filters.all": "すべて", "filters.ward": "地域", "filters.allAreas": "すべての地域", "filters.grade": "学年", "filters.nearby": "近くの学校を探す", "filters.map": "地図で見る ↗",
    "levels.elementary": "小学校", "levels.middle": "中学校", "levels.high": "高等学校", "grades.one": "1年生", "grades.two": "2年生", "grades.three": "3年生", "grades.four": "4年生", "grades.five": "5年生", "grades.six": "6年生", "grades.all": "全学年",
    "status.checking": "学校のページを確認しています。", "status.loading": "学校ページを確認中です…", "empty.title": "表示できるお知らせがありません", "empty.body": "絞り込みを変えるか、もう一度更新してください。",
    "detail.eyebrow": "原文を優先", "detail.placeholderTitle": "お知らせを選択すると<br>原文がここに表示されます。", "detail.placeholderBody": "要約だけでなく、分類した項目と日本語原文・公式リンクを一緒に確認できます。",
    "detail.original": "日本語の原文", "detail.openOriginal": "公式の原文を開く ↗", "detail.loading": "本文を読み込んでいます…", "detail.errorEyebrow": "詳細エラー", "detail.errorTitle": "原文を読み込めませんでした。",
    "card.original": "原文 ↗", "common.items": "件", "common.published": "掲載", "common.unknownDate": "日付未確認", "common.latest": "LATEST", "archive.past": "過去のお知らせ", "archive.none": "過去のお知らせはありません", "summary.notices": "学校・生活のお知らせ", "summary.events": "イベント", "summary.noData": "表示できる情報がありません", "summary.warning": " · 一部ソースの確認警告 ", "summary.warningSuffix": "件", "summary.all": "全", "summary.archiveSuffix": "。",
    "kind.grade": "学年だより", "kind.school": "学校だより", "kind.afterSchool": "学童クラブ", "kind.city": "市・教育委員会", "kind.related": "関連資料", "category.supplies": "持ち物・準備", "category.submission": "提出物・締切", "category.events": "行事・予定", "category.parent": "保護者への連絡", "category.school": "学校全体への連絡", "category.study": "学習予定", "notifications.unavailable": "この公開ベータでは通知設定を準備中です。", "notifications.permission": "ブラウザの通知を許可してください。", "notifications.ready": "この条件の新着を通知します。", "notifications.enabled": "通知設定済み", "notifications.error": "通知を設定できませんでした。",
  },
  ko: {
    "page.title": "오타요리 desk — 학교 소식 베타", "brand.subtitle": "도쿄 학교 소식 / 베타", "status.public": "공개 페이지 확인 중", "status.errorPrefix": "확인하지 못했습니다: ", "language.label": "표시 언어", "theme.toggle": "테마 전환", "detail.view": "자세히 보기",
    "hero.eyebrow": "보호자용 베타 · 공개 자료", "hero.title": "학교 소식을,<br><em>한곳에 모아서</em>.", "hero.lede": "학교별 페이지를 따로 찾지 않아도 학교 소식·학년 소식·행사 안내를 한곳에서 확인할 수 있습니다.", "hero.note": "아이의 학교와 학년을 선택하면 필요한 소식만 표시합니다.",
    "metrics.schools": "등록 학교", "metrics.schoolsFoot": "초·중·고 샘플", "metrics.notices": "이번 표시 수", "metrics.noticesFoot": "공개 원문 기준", "metrics.wards": "지원 지역", "metrics.wardsFoot": "도쿄 확장용 레지스트리", "metrics.scanned": "마지막 확인", "metrics.scannedFoot": "5분 캐시 · 수동 갱신 가능",
    "workspace.eyebrow": "우리 아이 학교 데스크", "workspace.title": "오늘 확인할 소식", "actions.refresh": "지금 갱신", "actions.notifications": "알림 받기", "feeds.notices": "학교·생활", "feeds.events": "이벤트", "groups.school": "학교", "groups.municipality": "무사시노시·교육위원회／시청", "groups.afterSchool": "학동",
    "filters.change": "학교·학년 변경", "filters.school": "학교", "filters.allSchools": "모든 학교", "filters.group": "발신처", "filters.allGroups": "모든 발신처", "filters.level": "학교 종류", "filters.all": "전체", "filters.ward": "지역", "filters.allAreas": "모든 지역", "filters.grade": "학년", "filters.nearby": "가까운 학교 찾기", "filters.map": "지도에서 보기 ↗", "levels.elementary": "초등학교", "levels.middle": "중학교", "levels.high": "고등학교", "grades.one": "1학년", "grades.two": "2학년", "grades.three": "3학년", "grades.four": "4학년", "grades.five": "5학년", "grades.six": "6학년", "grades.all": "전 학년",
    "status.checking": "학교 페이지를 확인하고 있습니다.", "status.loading": "학교 페이지 확인 중…", "empty.title": "표시할 소식이 없습니다", "empty.body": "필터를 바꾸거나 다시 갱신해 주세요.", "detail.eyebrow": "원문 우선", "detail.placeholderTitle": "소식을 선택하면<br>원문이 여기에 표시됩니다.", "detail.placeholderBody": "요약뿐 아니라 분류된 내용과 일본어 원문·공식 링크를 함께 확인할 수 있습니다.", "detail.original": "일본어 원문", "detail.openOriginal": "공식 원문 열기 ↗", "detail.loading": "본문을 불러오는 중…", "detail.errorEyebrow": "상세 오류", "detail.errorTitle": "원문을 불러오지 못했습니다.", "card.original": "원문 ↗", "common.items": "건", "common.published": "게시", "common.unknownDate": "날짜 미확인", "common.latest": "최신", "archive.past": "지난 소식", "archive.none": "지난 소식이 없습니다", "summary.notices": "학교·생활 소식", "summary.events": "이벤트", "summary.noData": "표시할 정보가 없습니다", "summary.warning": " · 일부 자료 확인 경고 ", "summary.warningSuffix": "건", "summary.all": "전체", "summary.archiveSuffix": ".", "kind.grade": "학년 소식", "kind.school": "학교 소식", "kind.afterSchool": "학동 클럽", "kind.city": "시·교육위원회", "kind.related": "관련 자료", "category.supplies": "준비물", "category.submission": "제출물·마감", "category.events": "행사·일정", "category.parent": "보호자 안내", "category.school": "학교 전체 안내", "category.study": "학습 일정",
  },
  en: {
    "page.title": "Otayori desk — school updates beta", "brand.subtitle": "Tokyo school notes / beta", "status.public": "Checking public pages", "status.errorPrefix": "Could not check: ", "language.label": "Language", "theme.toggle": "Change theme", "detail.view": "View details", "hero.eyebrow": "Parent beta · public sources", "hero.title": "School updates,<br><em>all in one place</em>.", "hero.lede": "See school letters, grade updates, and event information together without searching each school page.", "hero.note": "Choose your child's school and grade to show only relevant updates.", "metrics.schools": "Registered schools", "metrics.schoolsFoot": "Elementary · middle · high", "metrics.notices": "Shown now", "metrics.noticesFoot": "Based on public originals", "metrics.wards": "Areas", "metrics.wardsFoot": "Registry ready for expansion", "metrics.scanned": "Last checked", "metrics.scannedFoot": "5-min cache · refresh anytime", "workspace.eyebrow": "My child's school desk", "workspace.title": "Updates to check today", "actions.refresh": "Refresh now", "actions.notifications": "Get notifications", "feeds.notices": "School & daily life", "feeds.events": "Events", "groups.school": "School", "groups.municipality": "Musashino City / Board of Education", "groups.afterSchool": "After-school care", "filters.change": "Change school / grade", "filters.school": "School", "filters.allSchools": "All schools", "filters.group": "Source", "filters.allGroups": "All sources", "filters.level": "School type", "filters.all": "All", "filters.ward": "Area", "filters.allAreas": "All areas", "filters.grade": "Grade", "filters.nearby": "Find nearby schools", "filters.map": "Open map ↗", "levels.elementary": "Elementary", "levels.middle": "Middle", "levels.high": "High school", "grades.one": "Grade 1", "grades.two": "Grade 2", "grades.three": "Grade 3", "grades.four": "Grade 4", "grades.five": "Grade 5", "grades.six": "Grade 6", "grades.all": "All grades", "status.checking": "Checking school pages.", "status.loading": "Checking school pages…", "empty.title": "No updates to show", "empty.body": "Change a filter or refresh again.", "detail.eyebrow": "Original first", "detail.placeholderTitle": "Select an update to see<br>the original here.", "detail.placeholderBody": "Review categorized items together with the Japanese original and official link.", "detail.original": "Japanese original", "detail.openOriginal": "Open official original ↗", "detail.loading": "Loading the original…", "detail.errorEyebrow": "Detail error", "detail.errorTitle": "Could not load the original.", "card.original": "Original ↗", "common.items": " items", "common.published": "Published", "common.unknownDate": "Date unknown", "common.latest": "LATEST", "archive.past": "Past updates", "archive.none": "No past updates", "summary.notices": "School & daily life", "summary.events": "Events", "summary.noData": "No information to show", "summary.warning": " · source warnings: ", "summary.warningSuffix": "", "summary.all": "All ", "summary.archiveSuffix": ".", "kind.grade": "Grade letter", "kind.school": "School letter", "kind.afterSchool": "After-school care", "kind.city": "City / board", "kind.related": "Related", "category.supplies": "What to bring", "category.submission": "Submissions & deadlines", "category.events": "Events & schedule", "category.parent": "For parents", "category.school": "School-wide notice", "category.study": "Study schedule",
  },
  zh: {
    "page.title": "おたより desk — 学校通知测试版", "brand.subtitle": "东京学校通知 / 测试版", "status.public": "正在检查公开页面", "status.errorPrefix": "无法确认：", "language.label": "显示语言", "theme.toggle": "切换主题", "detail.view": "查看详情", "hero.eyebrow": "家长测试版 · 公开来源", "hero.title": "学校通知，<br><em>集中在一处</em>。", "hero.lede": "无需逐个寻找学校网页，即可集中查看学校通知、年级通知和活动信息。", "hero.note": "选择孩子的学校和年级，只显示需要的信息。", "metrics.schools": "已登记学校", "metrics.schoolsFoot": "小学·初中·高中", "metrics.notices": "当前显示", "metrics.noticesFoot": "以公开原文为准", "metrics.wards": "覆盖地区", "metrics.wardsFoot": "可扩展东京地区", "metrics.scanned": "最后检查", "metrics.scannedFoot": "5分钟缓存·可手动更新", "workspace.eyebrow": "孩子的学校桌面", "workspace.title": "今天要确认的通知", "actions.refresh": "立即更新", "actions.notifications": "接收通知", "feeds.notices": "学校·日常", "feeds.events": "活动", "groups.school": "学校", "groups.municipality": "武藏野市·教育委员会／市政府", "groups.afterSchool": "课后托管", "filters.change": "更改学校·年级", "filters.school": "学校", "filters.allSchools": "所有学校", "filters.group": "来源", "filters.allGroups": "所有来源", "filters.level": "学校类型", "filters.all": "全部", "filters.ward": "地区", "filters.allAreas": "所有地区", "filters.grade": "年级", "filters.nearby": "查找附近学校", "filters.map": "在地图中查看 ↗", "levels.elementary": "小学", "levels.middle": "初中", "levels.high": "高中", "grades.one": "一年级", "grades.two": "二年级", "grades.three": "三年级", "grades.four": "四年级", "grades.five": "五年级", "grades.six": "六年级", "grades.all": "全年级", "status.checking": "正在检查学校页面。", "status.loading": "正在检查学校页面…", "empty.title": "没有可显示的通知", "empty.body": "请更改筛选条件或再次更新。", "detail.eyebrow": "优先查看原文", "detail.placeholderTitle": "选择通知后<br>将在这里显示原文。", "detail.placeholderBody": "可同时查看分类内容、日文原文和官方链接。", "detail.original": "日文原文", "detail.openOriginal": "打开官方原文 ↗", "detail.loading": "正在加载原文…", "detail.errorEyebrow": "详情错误", "detail.errorTitle": "无法加载原文。", "card.original": "原文 ↗", "common.items": "条", "common.published": "发布", "common.unknownDate": "日期未知", "common.latest": "最新", "archive.past": "过去的通知", "archive.none": "没有过去的通知", "summary.notices": "学校·日常通知", "summary.events": "活动", "summary.noData": "没有可显示的信息", "summary.warning": " · 部分来源有警告 ", "summary.warningSuffix": "条", "summary.all": "共", "summary.archiveSuffix": "。", "kind.grade": "年级通知", "kind.school": "学校通知", "kind.afterSchool": "课后托管", "kind.city": "市政府·教育委员会", "kind.related": "相关资料", "category.supplies": "携带物品·准备", "category.submission": "提交物·截止日期", "category.events": "活动·日程", "category.parent": "给家长的通知", "category.school": "全校通知", "category.study": "学习安排",
  },
};

const LABEL_KEYS = {
  "学年だより": "kind.grade", "学校だより": "kind.school", "学童クラブ": "kind.afterSchool", "市・教育委員会": "kind.city", "関連資料": "kind.related",
  "持ち物・準備": "category.supplies", "提出物・締切": "category.submission", "行事・予定": "category.events", "保護者への連絡": "category.parent", "学校全体への連絡": "category.school", "学習予定": "category.study",
  "学校": "groups.school", "武蔵野市・教育委員会／市役所": "groups.municipality", "学童": "groups.afterSchool",
  "小学校": "levels.elementary", "中学校": "levels.middle", "高等学校": "levels.high", "1年生": "grades.one", "2年生": "grades.two", "3年生": "grades.three", "4年生": "grades.four", "5年生": "grades.five", "6年生": "grades.six", "全学年": "grades.all",
};

function t(key, fallback = key) {
  return I18N[state.language]?.[key] || I18N.ja[key] || fallback;
}

function localizeLabel(value) {
  const key = LABEL_KEYS[value];
  return key ? t(key, value) : value;
}

const NOTIFICATION_TEXT = {
  ja: { unavailable: "この公開ベータでは通知設定を準備中です。", permission: "ブラウザの通知を許可してください。", ready: "この条件の新着を通知します。", enabled: "通知設定済み", error: "通知を設定できませんでした。" },
  ko: { unavailable: "이 공개 베타에서는 알림 설정을 준비 중입니다.", permission: "브라우저 알림을 허용해 주세요.", ready: "이 조건의 새 소식을 알려드립니다.", enabled: "알림 설정됨", error: "알림을 설정하지 못했습니다." },
  en: { unavailable: "Notifications are being prepared for this public beta.", permission: "Please allow browser notifications.", ready: "You will get new updates for these filters.", enabled: "Notifications enabled", error: "Could not set up notifications." },
  zh: { unavailable: "此公开测试版正在准备通知设置。", permission: "请允许浏览器通知。", ready: "将通知这些筛选条件的新信息。", enabled: "通知已设置", error: "无法设置通知。" },
};

function notificationText(key) {
  return NOTIFICATION_TEXT[state.language]?.[key] || NOTIFICATION_TEXT.ja[key];
}

function updateFilterContext() {
  const context = $("filter-context");
  const sourceFilter = $("source-filter");
  const gradeFilter = $("grade-filter");
  const groupFilter = $("group-filter");
  if (!context || !sourceFilter || !gradeFilter) return;
  const school = sourceFilter.selectedOptions[0]?.textContent || t("filters.allSchools");
  const grade = localizeLabel(gradeFilter.value || "全学年");
  const group = groupFilter && groupFilter.value !== "all" ? localizeLabel(groupFilter.value === "after_school" ? "学童" : groupFilter.value === "municipality" ? "武蔵野市・教育委員会／市役所" : "学校") : "";
  context.textContent = `${school} · ${grade}${group ? ` · ${group}` : ""}`;
  updateMapLink();
}

function applyLanguage(language = state.language) {
  state.language = I18N[language] ? language : "ja";
  localStorage.setItem("school-news-language", state.language);
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : state.language;
  document.title = t("page.title", document.title);
  document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n, element.textContent); });
  document.querySelectorAll("[data-i18n-html]").forEach((element) => { element.innerHTML = t(element.dataset.i18nHtml, element.innerHTML); });
  const languageFilter = $("language-filter");
  if (languageFilter) {
    languageFilter.value = state.language;
    languageFilter.setAttribute("aria-label", t("language.label"));
  }
  const themeToggle = $("theme-toggle");
  if (themeToggle) { themeToggle.setAttribute("aria-label", t("theme.toggle")); themeToggle.title = themeToggle.getAttribute("aria-label"); }
  const refreshButton = $("refresh-button");
  const refreshLabel = refreshButton?.querySelector("[data-i18n='actions.refresh']");
  if (refreshLabel && !state.loading) refreshLabel.textContent = t("actions.refresh");
  updateFilterContext();
}

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function selectedValue(id) {
  return $(id).value || "all";
}

function queryString() {
  const params = new URLSearchParams();
  ["source-filter", "level-filter", "ward-filter", "grade-filter", "group-filter"].forEach((id) => {
    const value = selectedValue(id);
    const key = id.replace("-filter", "");
    if (value && value !== "all") params.set(key === "source" ? "source_id" : key === "group" ? "group" : key, value);
  });
  params.set("feed", state.feed);
  return params.toString();
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { Accept: "application/json" }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function populateConfig(config) {
  state.config = config;
  const sourceFilter = $("source-filter");
  const savedSource = localStorage.getItem("school-news-source");
  const sourceExists = config.sources.some((source) => source.id === savedSource);
  renderSourceOptions(sourceExists ? savedSource : (config.default_source_id || "all"));
  const wardFilter = $("ward-filter");
  config.wards.forEach((ward) => {
    const option = document.createElement("option");
    option.value = ward;
    option.textContent = ward;
    wardFilter.appendChild(option);
  });
  const savedGrade = localStorage.getItem("school-news-grade");
  const gradeExists = Array.from($("grade-filter").options).some((option) => option.value === savedGrade);
  $("grade-filter").value = gradeExists ? savedGrade : (config.default_grade || "全学年");
  const savedGroup = localStorage.getItem("school-news-group");
  $("group-filter").value = ["all", "school", "municipality", "after_school"].includes(savedGroup) ? savedGroup : "all";
  updateFilterContext();
  $("metric-schools").textContent = config.school_count ?? config.source_count;
  $("metric-wards").textContent = config.wards.length;
}

function renderSourceOptions(selectedId = "all") {
  const sourceFilter = $("source-filter");
  if (!sourceFilter || !state.config) return;
  sourceFilter.replaceChildren();
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = t("filters.allSchools");
  sourceFilter.appendChild(allOption);
  const sources = [...state.config.sources].sort((a, b) => {
    const distanceA = state.nearbyDistances.get(a.id);
    const distanceB = state.nearbyDistances.get(b.id);
    if (distanceA == null && distanceB == null) return a.name.localeCompare(b.name, "ja");
    if (distanceA == null) return 1;
    if (distanceB == null) return -1;
    return distanceA - distanceB;
  });
  sources.forEach((source) => {
    const option = document.createElement("option");
    option.value = source.id;
    const distance = state.nearbyDistances.get(source.id);
    option.textContent = `${source.name} · ${source.ward}${distance == null ? "" : ` · ${formatDistance(distance)}`}`;
    sourceFilter.appendChild(option);
  });
  sourceFilter.value = state.config.sources.some((source) => source.id === selectedId) ? selectedId : "all";
}

function formatDistance(kilometers) {
  if (kilometers < 1) return `${Math.round(kilometers * 1000)}m`;
  return `${kilometers.toFixed(1)}km`;
}

function updateMapLink() {
  const link = $("map-link");
  const source = state.config?.sources.find((item) => item.id === selectedValue("source-filter"));
  if (!link || !source?.latitude || !source?.longitude) {
    if (link) link.hidden = true;
    return;
  }
  link.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${source.latitude},${source.longitude}`)}`;
  link.hidden = false;
}

function savePreferences() {
  localStorage.setItem("school-news-source", selectedValue("source-filter"));
  localStorage.setItem("school-news-grade", selectedValue("grade-filter"));
  localStorage.setItem("school-news-group", selectedValue("group-filter"));
}

function setLoading(value) {
  state.loading = value;
  $("loading-state").hidden = !value;
  const refreshButton = $("refresh-button");
  refreshButton.disabled = value;
  refreshButton.setAttribute("aria-busy", String(value));
  refreshButton.title = value ? t("status.loading") : t("actions.refresh");
  const refreshLabel = refreshButton.querySelector("[data-i18n='actions.refresh']");
  if (refreshLabel) refreshLabel.textContent = value ? t("status.loading") : t("actions.refresh");
  if (value) {
    $("empty-state").hidden = true;
    $("notice-list").replaceChildren();
  }
}

function formatScanTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return state.language === "ja" ? "たった今" : "Just now";
  const locale = state.language === "ko" ? "ko-KR" : state.language === "en" ? "en-US" : state.language === "zh" ? "zh-CN" : "ja-JP";
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}

function localizeDateLabel(value) {
  const raw = String(value || "");
  if (!raw || raw === "更新資料") return t("common.unknownDate");
  const issue = raw.match(/^(\d{4})\/(\d{1,2})月号$/);
  if (issue) {
    const year = Number(issue[1]);
    const month = Number(issue[2]);
    if (state.language === "en") return new Date(year, month - 1, 1).toLocaleDateString("en-US", { year: "numeric", month: "long" });
    if (state.language === "ko") return `${year}년 ${month}월호`;
    if (state.language === "zh") return `${year}年${month}月刊`;
    return `${year}年${month}月号`;
  }
  const date = raw.match(/^(\d{4})\/(\d{2})\/(\d{2})$/);
  if (!date) return raw;
  const parsed = new Date(Number(date[1]), Number(date[2]) - 1, Number(date[3]));
  const locale = state.language === "ko" ? "ko-KR" : state.language === "en" ? "en-US" : state.language === "zh" ? "zh-CN" : "ja-JP";
  return parsed.toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" });
}

function formatCount(value) {
  return `${value}${t("common.items")}`;
}

function formatArchiveSummary(count) {
  if (!count) return t("archive.none");
  if (state.language === "ko") return `지난 ${count}개월은 접어 둠`;
  if (state.language === "en") return `past ${count} month${count === 1 ? "" : "s"} collapsed`;
  if (state.language === "zh") return `过去${count}个月已收起`;
  return `過去${count}か月は折りたたみ`;
}

function formatFilterSummary(latest, total, warningCount, archiveCount) {
  const feedLabel = state.feed === "events" ? t("summary.events") : t("summary.notices");
  const warningText = warningCount ? `${t("summary.warning")}${warningCount}${t("summary.warningSuffix")}` : "";
  const archiveText = formatArchiveSummary(archiveCount);
  if (state.language === "ko") {
    return `${feedLabel}: ${latest ? `${latest.label} ${formatCount(latest.items.length)} 표시` : t("summary.noData")} (${t("summary.all")} ${formatCount(total)})${warningText}. ${archiveText}.`;
  }
  if (state.language === "en") {
    return `${feedLabel}: ${latest ? `${latest.items.length}${t("common.items")} shown for ${latest.label}` : t("summary.noData")} (${t("summary.all")}${formatCount(total)})${warningText}. ${archiveText}.`;
  }
  if (state.language === "zh") {
    return `${feedLabel}：${latest ? `${latest.label}显示${formatCount(latest.items.length)}` : t("summary.noData")}（${t("summary.all")}${formatCount(total)}）${warningText}。${archiveText}。`;
  }
  return `${latest ? `${latest.label} ${formatCount(latest.items.length)}` : t("summary.noData")}（${t("summary.all")}${formatCount(total)}）${warningText}・${archiveText}`;
}

function renderNoticeCard(notice) {
  const categories = (notice.category_names || []).slice(0, 3).map((category) => `<span>${escapeHtml(localizeLabel(category))}</span>`).join("");
  const levelClass = notice.level === "高等学校" ? "coral" : notice.level === "中学校" ? "mint" : "";
  const sourceGroup = notice.source_group || "school";
  const sourceGroupLabel = localizeLabel(notice.source_group_label || "学校");
  const dateLabel = localizeDateLabel(notice.date_label);
  const publishedLabel = localizeDateLabel(notice.published_label);
  return `<article class="notice-card group-${escapeHtml(sourceGroup)}" data-notice-id="${escapeHtml(notice.id)}">
    <button type="button" aria-label="${escapeHtml(notice.source_name)} ${escapeHtml(notice.title)} ${escapeHtml(t("detail.view"))}">
      <div class="notice-meta">
        <span class="pill source-pill">${escapeHtml(notice.source_name)}</span>
        <span class="pill group-pill">${escapeHtml(sourceGroupLabel)}</span>
        <span class="pill ${levelClass}">${escapeHtml(localizeLabel(notice.level))}</span>
        <span class="pill soft">${escapeHtml(localizeLabel(notice.kind_label))}</span>
      </div>
      <h3 class="notice-title">${escapeHtml(notice.title)}</h3>
      <p class="notice-excerpt">${escapeHtml(notice.excerpt || t("detail.openOriginal"))}</p>
    </button>
    <div class="notice-footer"><span class="source-line">${escapeHtml(notice.ward)} · ${escapeHtml(dateLabel)}${notice.published_label && notice.published_label !== notice.date_label ? ` · ${escapeHtml(t("common.published"))} ${escapeHtml(publishedLabel)}` : ""}</span><span class="category-list">${categories}</span><a class="card-source-link" href="${escapeHtml(notice.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(t("card.original"))}</a></div>
    <div class="inline-detail" aria-live="polite"></div>
  </article>`;
}

function noticeMonthKey(notice) {
  const match = String(notice.date_label || "").match(/^(\d{4})\/(\d{2})/);
  return match ? `${match[1]}-${match[2]}` : "unknown";
}

function noticeMonthLabel(key) {
  if (key === "unknown") return t("common.unknownDate");
  const [year, month] = key.split("-");
  if (state.language === "en") return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("en-US", { year: "numeric", month: "long" });
  if (state.language === "ko") return `${year}년 ${Number(month)}월`;
  if (state.language === "zh") return `${year}年${Number(month)}月`;
  return `${year}年${Number(month)}月`;
}

function groupedNotices(notices) {
  const groups = new Map();
  notices.forEach((notice) => {
    const key = noticeMonthKey(notice);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(notice);
  });
  return [...groups.entries()].sort((a, b) => {
    if (a[0] === "unknown") return 1;
    if (b[0] === "unknown") return -1;
    return b[0].localeCompare(a[0]);
  }).map(([key, items]) => ({ key, label: noticeMonthLabel(key), items }));
}

function renderNoticeGroup(group) {
  return `<div class="notice-list-group">${group.items.map(renderNoticeCard).join("")}</div>`;
}

function renderNotices(payload) {
  state.payload = payload;
  state.notices = payload.notices || [];
  const list = $("notice-list");
  const groups = groupedNotices(state.notices);
  const latest = groups[0];
  const archiveHtml = groups.slice(1).map((group) => `<details class="archive-group"><summary><span><strong>${escapeHtml(group.label)}</strong><small>${escapeHtml(t("archive.past"))}</small></span><b>${escapeHtml(formatCount(group.items.length))}</b></summary>${renderNoticeGroup(group)}</details>`).join("");
  list.innerHTML = latest
    ? `<section class="latest-section"><div class="feed-section-head"><div><p class="eyebrow">${escapeHtml(t("common.latest"))}</p><h3>${escapeHtml(latest.label)}</h3></div><span>${escapeHtml(formatCount(latest.items.length))}</span></div>${renderNoticeGroup(latest)}</section>${archiveHtml}`
    : "";
  $("empty-state").hidden = state.notices.length !== 0;
  $("metric-notices").textContent = payload.notice_count ?? state.notices.length;
  $("metric-scanned").textContent = formatScanTime(payload.scanned_at);
  const archiveCount = Math.max(0, groups.length - 1);
  $("filter-summary").textContent = formatFilterSummary(latest, state.notices.length, payload.warnings?.length || 0, archiveCount);
  list.querySelectorAll(".notice-card").forEach((card) => {
    card.querySelector("button")?.addEventListener("click", () => selectNotice(card.dataset.noticeId));
  });
  if (!state.notices.length) {
    renderPlaceholder();
    return;
  }
  const selectedStillVisible = state.notices.some((notice) => notice.id === state.selectedId);
  selectNotice(selectedStillVisible ? state.selectedId : state.notices[0].id, { showInline: false });
}

function renderPlaceholder() {
  $("detail-panel").innerHTML = `<div class="detail-placeholder"><div class="placeholder-mark" aria-hidden="true">お</div><p class="eyebrow">${escapeHtml(t("detail.eyebrow"))}</p><h3>${t("detail.placeholderTitle")}</h3><p>${escapeHtml(t("empty.body"))}</p></div>`;
}

function detailMarkup(notice) {
  const categoryHtml = Object.entries(notice.categories || {}).map(([name, items]) => {
    const list = items.slice(0, 8).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    return `<section class="detail-section"><h4>${escapeHtml(localizeLabel(name))}</h4><ul>${list}</ul></section>`;
  }).join("");
  const dateLabel = localizeDateLabel(notice.date_label);
  const publishedLabel = localizeDateLabel(notice.published_label);
  return `<div class="detail-content">
    <div class="notice-meta"><span class="pill">${escapeHtml(notice.source_name)}</span><span class="pill group-pill">${escapeHtml(localizeLabel(notice.source_group_label || "学校"))}</span><span class="pill soft">${escapeHtml(localizeLabel(notice.kind_label))}</span><span class="pill soft">${escapeHtml(dateLabel)}</span></div>
    <h3>${escapeHtml(notice.title)}</h3>
    <p class="source-line">${escapeHtml(notice.ward)} · ${escapeHtml(localizeLabel(notice.level))} · ${escapeHtml(localizeLabel(notice.grade))}${notice.published_label ? ` · ${escapeHtml(t("common.published"))} ${escapeHtml(publishedLabel)}` : ""}</p>
    <a class="detail-link" href="${escapeHtml(notice.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(t("detail.openOriginal"))}</a>
    ${categoryHtml}
    <section class="detail-section"><h4>${escapeHtml(t("detail.original"))}</h4><div class="original-copy">${escapeHtml(notice.text)}</div></section>
  </div>`;
}

function renderDetail(notice, card = null, showInline = true) {
  $("detail-panel").innerHTML = detailMarkup(notice);
  document.querySelectorAll(".notice-card.expanded").forEach((otherCard) => {
    if (otherCard !== card || !showInline) {
      otherCard.classList.remove("expanded");
      const inlineDetail = otherCard.querySelector(".inline-detail");
      if (inlineDetail) inlineDetail.replaceChildren();
    }
  });
  if (card && showInline) {
    const inlineDetail = card.querySelector(".inline-detail");
    if (inlineDetail) {
      inlineDetail.innerHTML = detailMarkup(notice);
      card.classList.add("expanded");
    }
  }
}

async function selectNotice(id, { showInline = true } = {}) {
  const selectedCard = [...document.querySelectorAll(".notice-card")].find((card) => card.dataset.noticeId === id);
  if (showInline && selectedCard?.classList.contains("expanded") && state.selectedId === id) {
    selectedCard.classList.remove("expanded", "selected");
    selectedCard.querySelector(".inline-detail")?.replaceChildren();
    state.selectedId = null;
    renderPlaceholder();
    return;
  }
  state.selectedId = id;
  document.querySelectorAll(".notice-card").forEach((card) => card.classList.toggle("selected", card.dataset.noticeId === id));
  if (selectedCard && showInline) {
    const inlineDetail = selectedCard.querySelector(".inline-detail");
    if (inlineDetail) inlineDetail.innerHTML = `<p class="inline-loading">${escapeHtml(t("detail.loading"))}</p>`;
    selectedCard.classList.add("expanded");
  }
  try {
    const suffix = queryString();
    const detail = await api(`/api/notices/${encodeURIComponent(id)}${suffix ? `?${suffix}` : ""}`);
    if (state.selectedId !== id) return;
    renderDetail(detail, selectedCard, showInline);
  } catch (error) {
    if (state.selectedId !== id) return;
    const message = `<div class="detail-placeholder"><div class="placeholder-mark" aria-hidden="true">!</div><p class="eyebrow">${escapeHtml(t("detail.errorEyebrow"))}</p><h3>${escapeHtml(t("detail.errorTitle"))}</h3><p>${escapeHtml(error.message)}</p></div>`;
    $("detail-panel").innerHTML = message;
    if (selectedCard && showInline) {
      const inlineDetail = selectedCard.querySelector(".inline-detail");
      if (inlineDetail) inlineDetail.innerHTML = message;
    }
  }
}

async function loadNotices(refresh = false) {
  state.requestVersion += 1;
  const requestVersion = state.requestVersion;
  state.requestController?.abort();
  const controller = new AbortController();
  state.requestController = controller;
  setLoading(true);
  try {
    const query = queryString();
    const path = `/api/${refresh ? "refresh" : "notices"}${query ? `?${query}` : ""}`;
    const options = refresh ? { method: "POST", signal: controller.signal } : { signal: controller.signal };
    const payload = await api(path, options);
    if (requestVersion !== state.requestVersion) return;
    renderNotices(payload);
    if (refresh && payload.refreshed) {
      $("filter-summary").setAttribute("data-refreshed-at", payload.scanned_at || "");
    }
  } catch (error) {
    if (error?.name === "AbortError" || requestVersion !== state.requestVersion) return;
    $("notice-list").replaceChildren();
    $("empty-state").hidden = false;
    $("filter-summary").textContent = `${t("status.errorPrefix")}${error.message}`;
    renderPlaceholder();
  } finally {
    if (requestVersion === state.requestVersion) {
      state.requestController = null;
      setLoading(false);
    }
  }
}

function setupFeedTabs() {
  document.querySelectorAll(".feed-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const nextFeed = tab.dataset.feed || "notices";
      if (nextFeed === state.feed) return;
      state.feed = nextFeed;
      state.selectedId = null;
      document.querySelectorAll(".feed-tab").forEach((item) => {
        const active = item.dataset.feed === state.feed;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", String(active));
      });
      loadNotices(false);
    });
  });
}

function setupLanguage() {
  applyLanguage(state.language);
  $("language-filter").addEventListener("change", (event) => {
    applyLanguage(event.target.value);
    if (state.payload && !state.loading) renderNotices(state.payload);
  });
}

function setupTheme() {
  const saved = localStorage.getItem("school-news-theme");
  if (saved === "dark") document.body.classList.add("dark");
  $("theme-toggle").addEventListener("click", () => {
    document.body.classList.toggle("dark");
    localStorage.setItem("school-news-theme", document.body.classList.contains("dark") ? "dark" : "light");
  });
}

function haversineDistanceKm(latitudeA, longitudeA, latitudeB, longitudeB) {
  const radians = (value) => value * Math.PI / 180;
  const latitudeDelta = radians(latitudeB - latitudeA);
  const longitudeDelta = radians(longitudeB - longitudeA);
  const a = Math.sin(latitudeDelta / 2) ** 2 + Math.cos(radians(latitudeA)) * Math.cos(radians(latitudeB)) * Math.sin(longitudeDelta / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function setupNearbySchools() {
  $("nearby-button")?.addEventListener("click", () => {
    const status = $("nearby-status");
    if (!navigator.geolocation) {
      if (status) status.textContent = "位置情報に対応していません";
      return;
    }
    if (status) status.textContent = "位置情報を確認中…";
    navigator.geolocation.getCurrentPosition((position) => {
      const { latitude, longitude } = position.coords;
      state.nearbyDistances = new Map(
        (state.config?.sources || [])
          .filter((source) => Number.isFinite(source.latitude) && Number.isFinite(source.longitude))
          .map((source) => [source.id, haversineDistanceKm(latitude, longitude, source.latitude, source.longitude)]),
      );
      const selected = selectedValue("source-filter");
      renderSourceOptions(selected);
      updateFilterContext();
      if (status) status.textContent = state.language === "ja" ? "近い順に並べました" : `${state.nearbyDistances.size} ${state.language === "ko" ? "개 학교를 가까운 순서로 정렬했습니다" : "nearby schools sorted"}`;
    }, () => {
      if (status) status.textContent = state.language === "ja" ? "位置情報が許可されませんでした" : state.language === "ko" ? "위치 정보 권한이 필요합니다" : "Location permission is needed";
    }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 });
  });
}

function urlBase64ToUint8Array(value) {
  const padding = "=".repeat((4 - value.length % 4) % 4);
  const base64 = (value + padding).replaceAll("-", "+").replaceAll("_", "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
}

function currentPushScope() {
  return {
    source_id: selectedValue("source-filter"),
    grade: selectedValue("grade-filter"),
    feed: state.feed,
    group: selectedValue("group-filter"),
  };
}

function setNotificationStatus(key) {
  const status = $("notification-status");
  if (status) status.textContent = notificationText(key);
  const button = $("notification-button");
  if (button) button.title = notificationText(key);
}

async function enablePushNotifications() {
  const button = $("notification-button");
  if (!button || !state.push.config?.enabled) {
    setNotificationStatus("unavailable");
    return;
  }
  if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    setNotificationStatus("unavailable");
    return;
  }
  button.disabled = true;
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setNotificationStatus("permission");
      return;
    }
    const registration = state.push.registration || await navigator.serviceWorker.ready;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(state.push.config.public_key) });
    }
    await api("/api/push/subscribe", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subscription: subscription.toJSON(), scope: currentPushScope() }) });
    state.push.subscribed = true;
    const label = button.querySelector("span:last-child");
    if (label) label.textContent = notificationText("enabled");
    setNotificationStatus("ready");
  } catch (error) {
    setNotificationStatus("error");
    button.title = error.message || notificationText("error");
  } finally {
    button.disabled = false;
  }
}

async function setupPushNotifications() {
  const button = $("notification-button");
  if (!button) return;
  button.addEventListener("click", enablePushNotifications);
  if (!("serviceWorker" in navigator)) {
    setNotificationStatus("unavailable");
    return;
  }
  try {
    state.push.registration = await navigator.serviceWorker.register("/sw.js");
    state.push.config = await api("/api/push/config");
    if (!state.push.config.enabled) setNotificationStatus("unavailable");
  } catch (error) {
    setNotificationStatus("error");
  }
}

async function boot() {
  setupLanguage();
  setupTheme();
  setupFeedTabs();
  setupNearbySchools();
  setupPushNotifications();
  try {
    state.config = await api("/api/config");
    populateConfig(state.config);
    ["source-filter", "level-filter", "ward-filter", "grade-filter", "group-filter"].forEach((id) => $(id).addEventListener("change", () => { savePreferences(); updateFilterContext(); loadNotices(false); }));
    $("refresh-button").addEventListener("click", () => loadNotices(true));
    await loadNotices(false);
  } catch (error) {
    $("filter-summary").textContent = `${t("status.errorPrefix")}${error.message}`;
    $("empty-state").hidden = false;
  }
}

document.addEventListener("DOMContentLoaded", boot);
