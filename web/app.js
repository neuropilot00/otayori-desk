const state = {
  config: null,
  notices: [],
  payload: null,
  selectedId: null,
  loading: false,
  requestVersion: 0,
  requestController: null,
  detailRequestVersion: 0,
  refreshStatus: null,
  feed: "notices",
  nearbyDistances: new Map(),
  push: { config: null, registration: null, subscribed: false, ready: false, busy: false, scopes: [], scopesKnown: false, statusKey: "consentRequired" },
  language: localStorage.getItem("school-news-language") || "ja",
};

const REFRESH_POLL_INTERVAL_MS = 2000;
const REFRESH_POLL_TIMEOUT_MS = 60000;

const I18N = {
  ja: {
    "detail.attachments": "添付資料（公式原文）", "detail.attachmentsNote": "リンク先の添付本文は自動確認の対象外です。内容・変更は原文でご確認ください。",
    "status.refreshing": "最新の資料を確認中です…", "status.refreshTimeout": "確認に時間がかかっています。しばらくしてから更新してください。", "status.refreshError": "最新情報の再確認に失敗しました。表示中の情報と原文をご確認ください。",
    "extraction.unverified": "本文未確認", "coverage.readable": "本文", "coverage.documents": "資料",
    "coverage.stale": "更新遅れ", "coverage.extraction": "本文未確認", "coverage.pending": "初回確認待ち", "coverage.refreshing": "更新確認中", "coverage.details": "詳細", "coverage.close": "閉じる", "coverage.refreshTimeout": "確認が遅れています", "coverage.refreshError": "再確認に失敗",
    "coverage.collection": "収集の問題", "coverage.reason.collection": "一部の公開ページ・資料を取得できませんでした。公式ページをご確認ください。",
    "coverage.reason.stale": "最新の更新をまだ確認できていません。前回取得した情報を表示しています。", "coverage.reason.extraction": "本文を読み取れない資料があります。公式の原文をご確認ください。", "coverage.reason.unavailable": "公開ページを取得できませんでした。公式ページをご確認ください。", "coverage.reason.limit": "収集上限のため、一部の過去資料は対象外です。", "coverage.reason.refreshing": "最新の資料を確認中です。", "coverage.reason.pending": "初回の取得結果を待っています。", "coverage.reason.unknown": "最終確認の状況を確認できていません。", "coverage.reason.partial": "一部の資料を確認できていません。下の確認内容と公式原文をご確認ください。",
    "common.event": "開催", "common.deadline": "締切", "events.upcoming": "開催・締切が近い順", "events.past": "終了したイベント", "reference.title": "施設案内（連絡帳ではありません）",
    "coverage.title": "収集範囲・確認状況", "coverage.official": "公式ページ ↗", "coverage.checked": "公開範囲を確認", "coverage.partial": "一部のみ確認", "coverage.reference": "施設案内", "coverage.unavailable": "取得できませんでした", "coverage.unknown": "確認状況不明", "coverage.collected": "取得", "coverage.discovered": "候補", "coverage.limit": "収集上限あり", "coverage.checkedAt": "確認日時", "coverage.attention": "確認の注意", "coverage.sourceUnknown": "発信元未確認",
    "page.title": "おたより desk — 学校のお知らせベータ", "brand.subtitle": "東京の学校だより / ベータ", "status.public": "公開ページを確認中", "status.errorPrefix": "確認できませんでした：", "language.label": "表示言語", "theme.toggle": "テーマを切り替え", "detail.view": "詳細を見る",
    "hero.eyebrow": "保護者向けベータ · 公開ソース", "hero.title": "学校のお知らせを、<br><em>ひとつにまとめて</em>。",
    "hero.lede": "学校ごとに別々のページを探さなくても、学校だより・学年だより・行事のお知らせをここでまとめて確認できます。", "hero.note": "お子さまの学校・学年を選ぶと、必要なお知らせだけを表示します。",
    "metrics.schools": "登録校", "metrics.schoolsFoot": "小・中・高のサンプル", "metrics.notices": "今回の掲載数", "metrics.noticesFoot": "公開原文を基準", "metrics.wards": "対応地域", "metrics.wardsFoot": "23区拡張用レジストリ", "metrics.scanned": "最終確認", "metrics.scannedFoot": "キャッシュ5分・手動更新可",
    "workspace.eyebrow": "うちの子の学校デスク", "workspace.title": "今日確認したいお知らせ", "actions.refresh": "今すぐ更新", "actions.notifications": "通知を受け取る", "feeds.notices": "学校・生活", "feeds.events": "イベント",
    "groups.school": "学校", "groups.municipality": "武蔵野市・教育委員会／市役所", "groups.afterSchool": "学童",
    "filters.change": "学校・学年を変更", "filters.school": "学校", "filters.allSchools": "すべての学校", "filters.group": "発信元", "filters.allGroups": "すべての発信元", "filters.level": "学校種別", "filters.all": "すべて", "filters.ward": "地域", "filters.allAreas": "すべての地域", "filters.grade": "学年", "filters.nearby": "近くの学校を探す", "filters.map": "地図で見る ↗",
    "levels.elementary": "小学校", "levels.middle": "中学校", "levels.high": "高等学校", "grades.one": "1年生", "grades.two": "2年生", "grades.three": "3年生", "grades.four": "4年生", "grades.five": "5年生", "grades.six": "6年生", "grades.all": "全学年",
    "status.checking": "学校のページを確認しています。", "status.loading": "学校ページを確認中です…", "empty.title": "表示できるお知らせがありません", "empty.body": "絞り込みを変えるか、もう一度更新してください。",
    "detail.eyebrow": "原文を優先", "detail.placeholderTitle": "お知らせを選択すると、原文がここに表示されます。", "detail.placeholderBody": "要約だけでなく、分類した項目と日本語原文・公式リンクを一緒に確認できます。",
    "detail.original": "日本語の原文", "detail.openOriginal": "公式の原文を開く ↗", "detail.loading": "本文を読み込んでいます…", "detail.errorEyebrow": "詳細エラー", "detail.errorTitle": "原文を読み込めませんでした。",
    "card.original": "原文 ↗", "common.items": "件", "common.published": "掲載", "common.unknownDate": "日付未確認", "common.latest": "LATEST", "archive.past": "過去のお知らせ", "archive.none": "過去のお知らせはありません", "summary.notices": "学校・生活のお知らせ", "summary.events": "イベント", "summary.noData": "表示できる情報がありません", "summary.warning": " · 一部ソースの確認警告 ", "summary.warningSuffix": "件", "summary.all": "全", "summary.archiveSuffix": "。",
    "kind.grade": "学年だより", "kind.school": "学校だより", "kind.afterSchool": "学童クラブ", "kind.city": "市・教育委員会", "kind.related": "関連資料", "category.supplies": "持ち物・準備", "category.submission": "提出物・締切", "category.events": "行事・予定", "category.parent": "保護者への連絡", "category.school": "学校全体への連絡", "category.study": "学習予定", "notifications.unavailable": "この公開ベータでは通知設定を準備中です。", "notifications.permission": "ブラウザの通知を許可してください。", "notifications.ready": "この条件の新着を通知します。", "notifications.enabled": "通知設定済み", "notifications.error": "通知を設定できませんでした。",
  },
  ko: {
    "detail.attachments": "첨부자료 공식 원문", "detail.attachmentsNote": "첨부파일 본문은 자동 확인 대상이 아닙니다. 내용과 변경 사항은 원문에서 확인해 주세요.",
    "status.refreshing": "최신 자료를 확인 중입니다…", "status.refreshTimeout": "확인이 지연되고 있습니다. 잠시 후 다시 갱신해 주세요.", "status.refreshError": "최신 정보 재확인에 실패했습니다. 표시된 정보와 원문을 확인해 주세요.",
    "extraction.unverified": "본문 미확인", "coverage.readable": "본문", "coverage.documents": "자료",
    "coverage.stale": "갱신 지연", "coverage.extraction": "본문 미확인", "coverage.pending": "첫 확인 대기", "coverage.refreshing": "갱신 확인 중", "coverage.details": "상세", "coverage.close": "접기", "coverage.refreshTimeout": "확인이 지연되고 있습니다", "coverage.refreshError": "재확인 실패",
    "coverage.collection": "수집 문제", "coverage.reason.collection": "일부 공개 페이지나 자료를 가져오지 못했습니다. 공식 페이지를 확인해 주세요.",
    "coverage.reason.stale": "최신 변경 사항을 아직 확인하지 못해 이전에 수집한 정보를 표시합니다.", "coverage.reason.extraction": "본문을 읽지 못한 자료가 있습니다. 공식 원문을 확인해 주세요.", "coverage.reason.unavailable": "공개 페이지를 가져오지 못했습니다. 공식 페이지를 확인해 주세요.", "coverage.reason.limit": "수집 상한으로 일부 과거 자료는 대상에서 제외됩니다.", "coverage.reason.refreshing": "최신 자료를 확인 중입니다.", "coverage.reason.pending": "첫 수집 결과를 기다리고 있습니다.", "coverage.reason.unknown": "마지막 확인 상태를 알 수 없습니다.", "coverage.reason.partial": "일부 자료를 확인하지 못했습니다. 아래 확인 내용과 공식 원문을 확인해 주세요.",
    "common.event": "개최", "common.deadline": "마감", "events.upcoming": "개최·마감이 가까운 순", "events.past": "종료된 이벤트", "reference.title": "시설 안내 (가정 통신문이 아닙니다)",
    "coverage.title": "수집 범위·확인 현황", "coverage.official": "공식 페이지 ↗", "coverage.checked": "공개 범위 확인", "coverage.partial": "일부만 확인", "coverage.reference": "시설 안내", "coverage.unavailable": "가져오지 못함", "coverage.unknown": "확인 상태 불명", "coverage.collected": "수집", "coverage.discovered": "후보", "coverage.limit": "수집 상한 있음", "coverage.checkedAt": "확인 일시", "coverage.attention": "확인 주의", "coverage.sourceUnknown": "출처 미확인",
    "page.title": "오타요리 desk — 학교 소식 베타", "brand.subtitle": "도쿄 학교 소식 / 베타", "status.public": "공개 페이지 확인 중", "status.errorPrefix": "확인하지 못했습니다: ", "language.label": "표시 언어", "theme.toggle": "테마 전환", "detail.view": "자세히 보기",
    "hero.eyebrow": "보호자용 베타 · 공개 자료", "hero.title": "학교 소식을,<br><em>한곳에 모아서</em>.", "hero.lede": "학교별 페이지를 따로 찾지 않아도 학교 소식·학년 소식·행사 안내를 한곳에서 확인할 수 있습니다.", "hero.note": "아이의 학교와 학년을 선택하면 필요한 소식만 표시합니다.",
    "metrics.schools": "등록 학교", "metrics.schoolsFoot": "초·중·고 샘플", "metrics.notices": "이번 표시 수", "metrics.noticesFoot": "공개 원문 기준", "metrics.wards": "지원 지역", "metrics.wardsFoot": "도쿄 확장용 레지스트리", "metrics.scanned": "마지막 확인", "metrics.scannedFoot": "5분 캐시 · 수동 갱신 가능",
    "workspace.eyebrow": "우리 아이 학교 데스크", "workspace.title": "오늘 확인할 소식", "actions.refresh": "지금 갱신", "actions.notifications": "알림 받기", "feeds.notices": "학교·생활", "feeds.events": "이벤트", "groups.school": "학교", "groups.municipality": "무사시노시·교육위원회／시청", "groups.afterSchool": "학동",
    "filters.change": "학교·학년 변경", "filters.school": "학교", "filters.allSchools": "모든 학교", "filters.group": "발신처", "filters.allGroups": "모든 발신처", "filters.level": "학교 종류", "filters.all": "전체", "filters.ward": "지역", "filters.allAreas": "모든 지역", "filters.grade": "학년", "filters.nearby": "가까운 학교 찾기", "filters.map": "지도에서 보기 ↗", "levels.elementary": "초등학교", "levels.middle": "중학교", "levels.high": "고등학교", "grades.one": "1학년", "grades.two": "2학년", "grades.three": "3학년", "grades.four": "4학년", "grades.five": "5학년", "grades.six": "6학년", "grades.all": "전 학년",
    "status.checking": "학교 페이지를 확인하고 있습니다.", "status.loading": "학교 페이지 확인 중…", "empty.title": "표시할 소식이 없습니다", "empty.body": "필터를 바꾸거나 다시 갱신해 주세요.", "detail.eyebrow": "원문 우선", "detail.placeholderTitle": "소식을 선택하면 원문이 여기에 표시됩니다.", "detail.placeholderBody": "요약뿐 아니라 분류된 내용과 일본어 원문·공식 링크를 함께 확인할 수 있습니다.", "detail.original": "일본어 원문", "detail.openOriginal": "공식 원문 열기 ↗", "detail.loading": "본문을 불러오는 중…", "detail.errorEyebrow": "상세 오류", "detail.errorTitle": "원문을 불러오지 못했습니다.", "card.original": "원문 ↗", "common.items": "건", "common.published": "게시", "common.unknownDate": "날짜 미확인", "common.latest": "최신", "archive.past": "지난 소식", "archive.none": "지난 소식이 없습니다", "summary.notices": "학교·생활 소식", "summary.events": "이벤트", "summary.noData": "표시할 정보가 없습니다", "summary.warning": " · 일부 자료 확인 경고 ", "summary.warningSuffix": "건", "summary.all": "전체", "summary.archiveSuffix": ".", "kind.grade": "학년 소식", "kind.school": "학교 소식", "kind.afterSchool": "학동 클럽", "kind.city": "시·교육위원회", "kind.related": "관련 자료", "category.supplies": "준비물", "category.submission": "제출물·마감", "category.events": "행사·일정", "category.parent": "보호자 안내", "category.school": "학교 전체 안내", "category.study": "학습 일정",
  },
  en: {
    "detail.attachments": "Official attachments", "detail.attachmentsNote": "Attachment contents are not automatically verified. Check the originals for details and changes.",
    "status.refreshing": "Checking for the latest documents…", "status.refreshTimeout": "Checking is taking longer. Please refresh again later.", "status.refreshError": "Could not recheck the latest updates. Please review the displayed information and originals.",
    "extraction.unverified": "Text unverified", "coverage.readable": "Readable", "coverage.documents": "Documents",
    "coverage.stale": "Update overdue", "coverage.extraction": "Text unverified", "coverage.pending": "First check pending", "coverage.refreshing": "Checking updates", "coverage.details": "Details", "coverage.close": "Close", "coverage.refreshTimeout": "Check delayed", "coverage.refreshError": "Recheck failed",
    "coverage.collection": "Retrieval issue", "coverage.reason.collection": "Some public pages or documents could not be retrieved. Please check the official page.",
    "coverage.reason.stale": "Recent changes have not been checked yet. Previously collected information is shown.", "coverage.reason.extraction": "Some document text could not be read. Please check the official originals.", "coverage.reason.unavailable": "The public page could not be retrieved. Please check the official page.", "coverage.reason.limit": "Some older documents are outside the collection limit.", "coverage.reason.refreshing": "Checking for the latest documents.", "coverage.reason.pending": "Waiting for the first collection result.", "coverage.reason.unknown": "The last check status is unknown.", "coverage.reason.partial": "Some documents could not be checked. Review the details below and the official originals.",
    "common.event": "Event", "common.deadline": "Deadline", "events.upcoming": "Upcoming dates first", "events.past": "Past events", "reference.title": "Facility information (not school messages)",
    "coverage.title": "Collection scope & status", "coverage.official": "Official page ↗", "coverage.checked": "Public scope checked", "coverage.partial": "Partly checked", "coverage.reference": "Facility information", "coverage.unavailable": "Could not retrieve", "coverage.unknown": "Status unknown", "coverage.collected": "Collected", "coverage.discovered": "Candidates", "coverage.limit": "Collection limit reached", "coverage.checkedAt": "Checked at", "coverage.attention": "Source warnings", "coverage.sourceUnknown": "Unknown source",
    "page.title": "Otayori desk — school updates beta", "brand.subtitle": "Tokyo school notes / beta", "status.public": "Checking public pages", "status.errorPrefix": "Could not check: ", "language.label": "Language", "theme.toggle": "Change theme", "detail.view": "View details", "hero.eyebrow": "Parent beta · public sources", "hero.title": "School updates,<br><em>all in one place</em>.", "hero.lede": "See school letters, grade updates, and event information together without searching each school page.", "hero.note": "Choose your child's school and grade to show only relevant updates.", "metrics.schools": "Registered schools", "metrics.schoolsFoot": "Elementary · middle · high", "metrics.notices": "Shown now", "metrics.noticesFoot": "Based on public originals", "metrics.wards": "Areas", "metrics.wardsFoot": "Registry ready for expansion", "metrics.scanned": "Last checked", "metrics.scannedFoot": "5-min cache · refresh anytime", "workspace.eyebrow": "My child's school desk", "workspace.title": "Updates to check today", "actions.refresh": "Refresh now", "actions.notifications": "Get notifications", "feeds.notices": "School & daily life", "feeds.events": "Events", "groups.school": "School", "groups.municipality": "Musashino City / Board of Education", "groups.afterSchool": "After-school care", "filters.change": "Change school / grade", "filters.school": "School", "filters.allSchools": "All schools", "filters.group": "Source", "filters.allGroups": "All sources", "filters.level": "School type", "filters.all": "All", "filters.ward": "Area", "filters.allAreas": "All areas", "filters.grade": "Grade", "filters.nearby": "Find nearby schools", "filters.map": "Open map ↗", "levels.elementary": "Elementary", "levels.middle": "Middle", "levels.high": "High school", "grades.one": "Grade 1", "grades.two": "Grade 2", "grades.three": "Grade 3", "grades.four": "Grade 4", "grades.five": "Grade 5", "grades.six": "Grade 6", "grades.all": "All grades", "status.checking": "Checking school pages.", "status.loading": "Checking school pages…", "empty.title": "No updates to show", "empty.body": "Change a filter or refresh again.", "detail.eyebrow": "Original first", "detail.placeholderTitle": "Select an update to see the original here.", "detail.placeholderBody": "Review categorized items together with the Japanese original and official link.", "detail.original": "Japanese original", "detail.openOriginal": "Open official original ↗", "detail.loading": "Loading the original…", "detail.errorEyebrow": "Detail error", "detail.errorTitle": "Could not load the original.", "card.original": "Original ↗", "common.items": " items", "common.published": "Published", "common.unknownDate": "Date unknown", "common.latest": "LATEST", "archive.past": "Past updates", "archive.none": "No past updates", "summary.notices": "School & daily life", "summary.events": "Events", "summary.noData": "No information to show", "summary.warning": " · source warnings: ", "summary.warningSuffix": "", "summary.all": "All ", "summary.archiveSuffix": ".", "kind.grade": "Grade letter", "kind.school": "School letter", "kind.afterSchool": "After-school care", "kind.city": "City / board", "kind.related": "Related", "category.supplies": "What to bring", "category.submission": "Submissions & deadlines", "category.events": "Events & schedule", "category.parent": "For parents", "category.school": "School-wide notice", "category.study": "Study schedule",
  },
  zh: {
    "detail.attachments": "官方附件原文", "detail.attachmentsNote": "附件正文不在自动确认范围内，请查看原文中的内容及变更。",
    "status.refreshing": "正在确认最新资料…", "status.refreshTimeout": "确认耗时较长，请稍后再次刷新。", "status.refreshError": "无法再次确认最新信息，请查看当前信息和原文。",
    "extraction.unverified": "正文未确认", "coverage.readable": "正文", "coverage.documents": "资料",
    "coverage.stale": "更新延迟", "coverage.extraction": "正文未确认", "coverage.pending": "等待首次确认", "coverage.refreshing": "正在检查更新", "coverage.details": "详情", "coverage.close": "收起", "coverage.refreshTimeout": "确认延迟", "coverage.refreshError": "再次确认失败",
    "coverage.collection": "收集问题", "coverage.reason.collection": "无法获取部分公开页面或资料，请查看官方页面。",
    "coverage.reason.stale": "尚未确认最新变更，当前显示此前收集的信息。", "coverage.reason.extraction": "部分资料的正文无法读取，请查看官方原文。", "coverage.reason.unavailable": "无法获取公开页面，请查看官方页面。", "coverage.reason.limit": "由于收集上限，部分历史资料不在收集范围内。", "coverage.reason.refreshing": "正在确认最新资料。", "coverage.reason.pending": "正在等待首次收集结果。", "coverage.reason.unknown": "无法确认上次检查的状态。", "coverage.reason.partial": "部分资料尚未确认，请查看下方详情及官方原文。",
    "common.event": "举办", "common.deadline": "截止", "events.upcoming": "按举办·截止日期由近到远", "events.past": "已结束的活动", "reference.title": "设施介绍（非家校通知）",
    "coverage.title": "收集范围·确认状态", "coverage.official": "官方页面 ↗", "coverage.checked": "已检查公开范围", "coverage.partial": "仅确认部分", "coverage.reference": "设施介绍", "coverage.unavailable": "无法获取", "coverage.unknown": "确认状态未知", "coverage.collected": "已获取", "coverage.discovered": "候选", "coverage.limit": "已达收集上限", "coverage.checkedAt": "确认时间", "coverage.attention": "来源提醒", "coverage.sourceUnknown": "来源未确认",
    "page.title": "おたより desk — 学校通知测试版", "brand.subtitle": "东京学校通知 / 测试版", "status.public": "正在检查公开页面", "status.errorPrefix": "无法确认：", "language.label": "显示语言", "theme.toggle": "切换主题", "detail.view": "查看详情", "hero.eyebrow": "家长测试版 · 公开来源", "hero.title": "学校通知，<br><em>集中在一处</em>。", "hero.lede": "无需逐个寻找学校网页，即可集中查看学校通知、年级通知和活动信息。", "hero.note": "选择孩子的学校和年级，只显示需要的信息。", "metrics.schools": "已登记学校", "metrics.schoolsFoot": "小学·初中·高中", "metrics.notices": "当前显示", "metrics.noticesFoot": "以公开原文为准", "metrics.wards": "覆盖地区", "metrics.wardsFoot": "可扩展东京地区", "metrics.scanned": "最后检查", "metrics.scannedFoot": "5分钟缓存·可手动更新", "workspace.eyebrow": "孩子的学校桌面", "workspace.title": "今天要确认的通知", "actions.refresh": "立即更新", "actions.notifications": "接收通知", "feeds.notices": "学校·日常", "feeds.events": "活动", "groups.school": "学校", "groups.municipality": "武藏野市·教育委员会／市政府", "groups.afterSchool": "课后托管", "filters.change": "更改学校·年级", "filters.school": "学校", "filters.allSchools": "所有学校", "filters.group": "来源", "filters.allGroups": "所有来源", "filters.level": "学校类型", "filters.all": "全部", "filters.ward": "地区", "filters.allAreas": "所有地区", "filters.grade": "年级", "filters.nearby": "查找附近学校", "filters.map": "在地图中查看 ↗", "levels.elementary": "小学", "levels.middle": "初中", "levels.high": "高中", "grades.one": "一年级", "grades.two": "二年级", "grades.three": "三年级", "grades.four": "四年级", "grades.five": "五年级", "grades.six": "六年级", "grades.all": "全年级", "status.checking": "正在检查学校页面。", "status.loading": "正在检查学校页面…", "empty.title": "没有可显示的通知", "empty.body": "请更改筛选条件或再次更新。", "detail.eyebrow": "优先查看原文", "detail.placeholderTitle": "选择通知后将在这里显示原文。", "detail.placeholderBody": "可同时查看分类内容、日文原文和官方链接。", "detail.original": "日文原文", "detail.openOriginal": "打开官方原文 ↗", "detail.loading": "正在加载原文…", "detail.errorEyebrow": "详情错误", "detail.errorTitle": "无法加载原文。", "card.original": "原文 ↗", "common.items": "条", "common.published": "发布", "common.unknownDate": "日期未知", "common.latest": "最新", "archive.past": "过去的通知", "archive.none": "没有过去的通知", "summary.notices": "学校·日常通知", "summary.events": "活动", "summary.noData": "没有可显示的信息", "summary.warning": " · 部分来源有警告 ", "summary.warningSuffix": "条", "summary.all": "共", "summary.archiveSuffix": "。", "kind.grade": "年级通知", "kind.school": "学校通知", "kind.afterSchool": "课后托管", "kind.city": "市政府·教育委员会", "kind.related": "相关资料", "category.supplies": "携带物品·准备", "category.submission": "提交物·截止日期", "category.events": "活动·日程", "category.parent": "给家长的通知", "category.school": "全校通知", "category.study": "学习安排",
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
  updatePushScopeLabels();
}

function applyLanguage(language = state.language, persist = true) {
  state.language = I18N[language] ? language : "ja";
  if (persist) localStorage.setItem("school-news-language", state.language);
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
  applyPilotLanguage(state.language);
  updatePushControls();
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

function officialLink(url, label, className = "") {
  try {
    const parsed = new URL(url);
    if (!["https:", "http:"].includes(parsed.protocol) || parsed.username || parsed.password) return "";
    return `<a class="${className}" href="${escapeHtml(parsed.href)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`;
  } catch (_) { return ""; }
}

function sourceConfig(item) {
  return state.config?.sources?.find((source) => source.id === item.source_id) || {};
}

function isReference(notice) {
  const source = sourceConfig(notice);
  const coverage = state.payload?.coverage?.find((item) => item.source_id === notice.source_id);
  return notice.coverage_kind === "reference" || source.coverage_kind === "reference" || coverage?.coverage_kind === "reference"
    || notice.mode === "static" || source.mode === "static";
}

function dateKey(value) {
  const match = String(value || "").match(/^(\d{4})\/(\d{2})\/(\d{2})$/);
  if (!match) return "";
  const key = `${match[1]}-${match[2]}-${match[3]}`;
  const date = new Date(`${key}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === key ? key : "";
}

function isEvent(notice) {
  return notice.feed_group === "events" || notice.date_kind === "event" || Boolean(notice.event_date);
}

function eventDate(notice) {
  return dateKey(notice.event_date) ? notice.event_date : notice.date_kind === "event" && dateKey(notice.date_label) ? notice.date_label : "";
}

function eventSortKey(notice) {
  // Publication dates cannot tell us whether an event is upcoming or over.
  return dateKey(eventDate(notice)) || dateKey(notice.deadline_date);
}

function noticeDateText(notice) {
  const labels = [];
  if (isEvent(notice)) labels.push(`${t("common.event")} ${localizeDateLabel(eventDate(notice))}`);
  if (dateKey(notice.deadline_date)) labels.push(`${t("common.deadline")} ${localizeDateLabel(notice.deadline_date)}`);
  const issue = notice.date_kind === "issue" || (!notice.date_kind && /月号$/.test(notice.date_label || ""));
  if (issue) labels.push(localizeDateLabel(notice.date_label));
  const published = notice.date_kind === "unknown" ? "" : notice.published_label || (notice.date_kind === "published" ? notice.date_label : "");
  if (dateKey(published)) labels.push(`${t("common.published")} ${localizeDateLabel(published)}`);
  return labels.length ? labels.join(" · ") : t("common.unknownDate");
}

function japanToday() {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  return ["year", "month", "day"].map((type) => parts.find((part) => part.type === type).value).join("-");
}

function selectedValue(id) {
  return $(id).value || "all";
}

function queryString() {
  const params = new URLSearchParams();
  ["source-filter", "level-filter", "ward-filter", "grade-filter", "group-filter"].forEach((id) => {
    const value = selectedValue(id);
    const key = id.replace("-filter", "");
    if (value && (value !== "all" || key === "source")) params.set(key === "source" ? "source_id" : key === "group" ? "group" : key, value);
  });
  params.set("feed", state.feed);
  return params.toString();
}

async function api(path, options = {}) {
  return pilotApi(path, options);
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
    $("coverage-details").hidden = true;
    $("coverage-alert").hidden = true;
  }
}

function formatScanTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
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

function coverageIssues(source) {
  const known = ["stale", "unavailable", "extraction", "limit", "refreshing", "collection", "pending", "unknown"];
  const issues = new Set((source.issue_codes || []).map((code) => known.includes(code) ? code : "unknown"));
  if (["stale", "pending", "unknown"].includes(source.freshness_status)) issues.add(source.freshness_status);
  if (source.status === "unavailable" && source.freshness_status !== "pending") issues.add("unavailable");
  if (Number.isInteger(source.readable_count) && source.readable_count >= 0 && source.readable_count < source.notice_count) issues.add("extraction");
  if (source.limit_reached) issues.add("limit");
  if (source.refreshing) issues.add("refreshing");
  if (source.status === "partial" && (!issues.size || (issues.size === 1 && issues.has("limit") && !source.issue_codes?.length))) issues.add("collection");
  if (!issues.size && !["checked", "reference"].includes(source.status) && !isReference(source) && source.freshness_status !== "fresh") issues.add("unknown");
  return [...issues];
}

function coverageStatus(source) {
  const issues = coverageIssues(source);
  const status = ["unavailable", "extraction", "collection", "stale", "pending", "refreshing", "unknown", "limit"].find((code) => issues.includes(code));
  if (status) return status;
  if (isReference(source) || source.status === "reference") return "reference";
  return source.status === "checked" || source.freshness_status === "fresh" ? "checked" : "unknown";
}

function coverageIssueClass(issue) {
  return ["extraction", "collection", "unavailable", "refreshError"].includes(issue) ? "status-unavailable" : `status-${issue}`;
}

// Old responses only have Japanese warnings; keep unrecognized warnings visible.
function legacyCoverageIssue(message) {
  if (/本文.*(?:読み取れ|読み取り.*でき)|OCR.*(?:失敗|エラー)/.test(message)) return "extraction";
  if (/更新確認中です。前回取得した情報を表示しています。/.test(message)) return "refreshing";
  if (/更新.*遅れ|最新.*未確認/.test(message)) return "stale";
  if (/^(?:公開ページの確認|資料の収集|収集)上限(?:に達|あり)/.test(message)) return "limit";
  return "collection";
}

function renderCoverage(payload) {
  const sourceName = (source) => source.source_name || source.name || source.source_id || t("coverage.sourceUnknown");
  const rows = (payload.coverage || []).map((item) => ({ ...sourceConfig(item), ...item }));
  const warnings = [...(payload.warnings || []).map((warning) => ({ warning, isError: false })), ...(payload.errors || []).map((warning) => ({ warning, isError: true }))].map(({ warning, isError }) => {
    const message = typeof warning === "string" ? warning : `${sourceName({ ...sourceConfig(warning), ...warning })}：${warning.message || warning.error || ""}`;
    const source = rows.find((row) => (typeof warning === "object" && warning.source_id && warning.source_id === row.source_id)
      || message.startsWith(`${sourceName(row)}: `) || message.startsWith(`${sourceName(row)}：`));
    const reason = typeof warning === "object" ? warning.message || warning.error || "" : source ? message.slice(sourceName(source).length + 1).trimStart() : message;
    const typedReason = source && (source.issue_codes?.length || ["stale", "pending", "unknown"].includes(source.freshness_status));
    const issues = isError ? ["collection"] : typedReason ? coverageIssues(source) : [legacyCoverageIssue(reason)];
    return { message, source, issues, isError };
  });
  // Attach legacy warning reasons before interpreting a generic partial status.
  for (const source of rows) {
    const related = warnings.filter((warning) => warning.source === source);
    source.issue_codes = [...(source.issue_codes || []), ...related.filter((warning) => warning.isError || !source.issue_codes?.length).flatMap((warning) => warning.issues)];
  }
  const counts = new Map();
  const addIssue = (issue) => counts.set(issue, (counts.get(issue) || 0) + 1);
  rows.forEach((source) => coverageIssues(source).forEach(addIssue));
  warnings.filter((warning) => !warning.source).forEach((warning) => warning.issues.forEach(addIssue));
  if ((payloadRefreshing(payload) || state.refreshStatus === "refreshing") && !counts.has("refreshing")) counts.set("refreshing", 0);
  if (!counts.size && payload.complete === false) counts.set("unknown", 0);
  if (["refreshTimeout", "refreshError"].includes(state.refreshStatus)) {
    counts.delete("refreshing");
    counts.set(state.refreshStatus, 0);
  }
  const summary = [...counts].filter(([issue]) => issue !== "limit");
  const alert = $("coverage-alert");
  const details = $("coverage-details");
  alert.className = "coverage-note coverage-status";
  alert.innerHTML = summary.map(([issue, count]) => `<span class="coverage-status ${coverageIssueClass(issue)}">${escapeHtml(t(`coverage.${issue}`))}${count ? ` ${count}` : ""}</span>`).join(" · ")
    + (summary.length ? ` <a id="coverage-toggle" class="card-source-link" href="#coverage-details" aria-controls="coverage-details" aria-expanded="${Boolean(details.open)}">${escapeHtml(t(details.open ? "coverage.close" : "coverage.details"))}</a>` : "");
  alert.hidden = !summary.length;
  const toggle = alert.querySelector("#coverage-toggle");
  if (toggle) {
    toggle.onclick = (event) => { event.preventDefault(); details.open = !details.open; };
    details.ontoggle = () => {
      const current = alert.querySelector("#coverage-toggle");
      current?.setAttribute("aria-expanded", String(details.open));
      if (current) current.textContent = t(details.open ? "coverage.close" : "coverage.details");
    };
  }
  details.hidden = false;
  $("coverage-count").textContent = String(rows.length);
  $("coverage-list").innerHTML = rows.map((source) => {
    const status = coverageStatus(source);
    const issues = coverageIssues(source);
    const count = (value) => Number.isInteger(value) && value >= 0 ? formatCount(value) : "—";
    const countsDiffer = Number.isInteger(source.readable_count) && source.readable_count >= 0 && Number.isInteger(source.notice_count) && source.notice_count >= 0 && source.readable_count !== source.notice_count;
    const collected = countsDiffer ? `${t("coverage.readable")} ${source.readable_count} / ${t("coverage.documents")} ${source.notice_count}` : `${t("coverage.collected")} ${count(source.notice_count)}`;
    const checked = new Date(source.checked_at || "");
    const checkedAt = Number.isNaN(checked.getTime()) ? "—" : checked.toLocaleString({ ja: "ja-JP", ko: "ko-KR", en: "en-US", zh: "zh-CN" }[state.language] || "ja-JP", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) + " JST";
    return `<li class="coverage-source"><div class="coverage-source-heading"><strong>${escapeHtml(sourceName(source))}</strong><span class="coverage-status ${coverageIssueClass(status)}">${escapeHtml(t(`coverage.${status}`))}</span>${officialLink(source.page_url, t("coverage.official"))}</div>
      <p>${escapeHtml(collected)} · ${escapeHtml(t("coverage.discovered"))} ${escapeHtml(count(source.discovered_count))}${issues.includes("limit") ? ` · ${escapeHtml(t("coverage.limit"))}` : ""}</p>
      ${issues.map((issue) => `<p><span class="coverage-status ${coverageIssueClass(issue)}">${escapeHtml(t(`coverage.reason.${issue}`))}</span></p>`).join("")}
      ${source.coverage_note ? `<p lang="ja">${escapeHtml(source.coverage_note)}</p>` : ""}
      ${isReference(source) || source.status === "reference" ? '<p lang="ja">施設の基本情報です。日々の連絡・新着通知の確認対象ではありません。</p>' : ""}
      <small>${escapeHtml(t("coverage.checkedAt"))} ${escapeHtml(checkedAt)}</small></li>`;
  }).join("") || `<li>${escapeHtml(t("coverage.unknown"))}</li>`;
  $("coverage-warnings").className = "coverage-note coverage-status";
  const refreshMessage = ["refreshTimeout", "refreshError"].includes(state.refreshStatus) ? `<li>${escapeHtml(t(`status.${state.refreshStatus}`))}</li>` : "";
  $("coverage-warnings").innerHTML = warnings.map(({ message, issues }) => `<li lang="ja"><span class="coverage-status ${coverageIssueClass(issues.find((issue) => ["unavailable", "extraction", "collection"].includes(issue)) || issues[0])}">${escapeHtml(message)}</span></li>`).join("") + refreshMessage;
  $("coverage-warnings").hidden = !warnings.length && !refreshMessage;
}

function renderNoticeCard(notice) {
  const originalOnly = notice.extraction_status === "original_only";
  const categories = (originalOnly ? [] : notice.category_names || []).slice(0, 3).map((category) => `<span>${escapeHtml(localizeLabel(category))}</span>`).join("");
  const levelClass = notice.level === "高等学校" ? "coral" : notice.level === "中学校" ? "mint" : "";
  const sourceGroup = ["school", "municipality", "after_school"].includes(notice.source_group) ? notice.source_group : "school";
  const sourceGroupLabel = localizeLabel(notice.source_group_label || "学校");
  return `<article class="notice-card group-${escapeHtml(sourceGroup)}" data-notice-id="${escapeHtml(notice.id)}">
    <button type="button" aria-expanded="false" aria-label="${escapeHtml(notice.source_name)} ${escapeHtml(notice.title)}${originalOnly ? ` ${escapeHtml(t("extraction.unverified"))}` : ""} ${escapeHtml(t("detail.view"))}">
      <div class="notice-meta">
        <span class="pill source-pill">${escapeHtml(notice.source_name)}</span>
        <span class="pill group-pill">${escapeHtml(sourceGroupLabel)}</span>
        ${(notice.source_group || "school") === "school" ? `<span class="pill ${levelClass}">${escapeHtml(localizeLabel(notice.level))}</span>` : ""}
        <span class="pill soft">${escapeHtml(localizeLabel(notice.kind_label))}</span>
        ${originalOnly ? `<span class="pill extraction-badge">${escapeHtml(t("extraction.unverified"))}</span>` : ""}
      </div>
      <h3 class="notice-title" lang="ja">${escapeHtml(notice.title)}</h3>
      <p class="notice-excerpt" lang="ja">${escapeHtml(notice.excerpt || t("detail.openOriginal"))}</p>
    </button>
    <div class="notice-footer"><span class="source-line notice-dates">${escapeHtml([notice.ward, noticeDateText(notice)].filter(Boolean).join(" · "))}</span><span class="category-list">${categories}</span>${officialLink(notice.url, t("card.original"), "card-source-link")}</div>
    <div class="inline-detail" aria-live="polite"></div>
  </article>`;
}

function noticeMonthKey(notice) {
  if (notice.date_kind === "unknown") return "unknown";
  const value = notice.date_kind === "event" ? eventDate(notice) : notice.date_label || notice.published_label;
  const match = String(value || "").match(/^(\d{4})\/(\d{1,2})(?:月号|\/\d{2})$/);
  return match && Number(match[2]) >= 1 && Number(match[2]) <= 12 ? `${match[1]}-${match[2].padStart(2, "0")}` : "unknown";
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

function noticeSections(notices, feed = state.feed, today = japanToday()) {
  const references = notices.filter(isReference);
  const updates = notices.filter((notice) => !isReference(notice));
  if (feed === "events") {
    const dated = updates.filter((notice) => eventSortKey(notice));
    const upcoming = dated.filter((notice) => eventSortKey(notice) >= today).sort((a, b) => eventSortKey(a).localeCompare(eventSortKey(b)));
    const past = dated.filter((notice) => eventSortKey(notice) < today).sort((a, b) => eventSortKey(b).localeCompare(eventSortKey(a)));
    return {
      active: upcoming.length ? [{ key: "upcoming", label: t("events.upcoming"), items: upcoming }] : [],
      archive: past.length ? [{ key: "past-events", label: t("events.past"), items: past }] : [],
      undated: updates.filter((notice) => !eventSortKey(notice)), references, total: updates.length,
    };
  }
  const groups = groupedNotices(updates);
  const dated = groups.filter((group) => group.key !== "unknown");
  return { active: dated.slice(0, 1), archive: dated.slice(1), undated: groups.find((group) => group.key === "unknown")?.items || [], references, total: updates.length };
}

function renderNotices(payload) {
  state.payload = payload;
  state.notices = payload.notices || [];
  const list = $("notice-list");
  const sections = noticeSections(state.notices);
  const latest = sections.active[0];
  const activeHtml = sections.active.map((group) => `<section class="latest-section"><div class="feed-section-head"><div>${state.feed === "events" ? "" : `<p class="eyebrow">${escapeHtml(t("common.latest"))}</p>`}<h3>${escapeHtml(group.label)}</h3></div><span>${escapeHtml(formatCount(group.items.length))}</span></div>${renderNoticeGroup(group)}</section>`).join("");
  const undatedHtml = sections.undated.length ? `<section class="undated-section"><div class="feed-section-head compact-section-head"><h3>${escapeHtml(t("common.unknownDate"))}</h3><span>${escapeHtml(formatCount(sections.undated.length))}</span></div>${renderNoticeGroup({ items: sections.undated })}</section>` : "";
  const archiveHtml = sections.archive.map((group) => `<details class="archive-group"><summary><span><strong>${escapeHtml(group.label)}</strong>${state.feed === "events" ? "" : `<small>${escapeHtml(t("archive.past"))}</small>`}</span><b>${escapeHtml(formatCount(group.items.length))}</b></summary>${renderNoticeGroup(group)}</details>`).join("");
  const referenceHtml = sections.references.length ? `<details class="archive-group reference-group"><summary><span><strong>${escapeHtml(t("reference.title"))}</strong></span><b>${escapeHtml(formatCount(sections.references.length))}</b></summary><p class="reference-note" lang="ja">施設の基本情報です。日々の連絡・新着通知の確認対象ではありません。</p>${renderNoticeGroup({ items: sections.references })}</details>` : "";
  list.innerHTML = activeHtml + undatedHtml + archiveHtml + referenceHtml;
  $("empty-state").hidden = state.notices.length !== 0;
  $("metric-notices").textContent = sections.total;
  $("metric-scanned").textContent = formatScanTime(payload.scanned_at);
  const summaryGroup = latest || (sections.undated.length ? { label: t("common.unknownDate"), items: sections.undated } : null);
  const summary = state.feed === "events"
    ? `${t("summary.events")}：${formatCount(latest?.items.length || 0)} · ${t("events.past")} ${formatCount(sections.archive[0]?.items.length || 0)}`
    : formatFilterSummary(summaryGroup, sections.total, 0, sections.archive.length);
  $("filter-summary").textContent = summary + (sections.undated.length && (latest || state.feed === "events") ? ` · ${t("common.unknownDate")} ${formatCount(sections.undated.length)}` : "");
  renderCoverage(payload);
  list.querySelectorAll(".notice-card").forEach((card) => {
    card.querySelector("button")?.addEventListener("click", () => selectNotice(card.dataset.noticeId));
  });
  const firstVisible = latest?.items[0] || sections.undated[0];
  const selectedStillVisible = state.notices.some((notice) => notice.id === state.selectedId);
  if (!selectedStillVisible && !firstVisible) {
    state.selectedId = null;
    renderPlaceholder();
    return;
  }
  selectNotice(selectedStillVisible ? state.selectedId : firstVisible.id, { showInline: false });
}

function renderPlaceholder() {
  $("detail-panel").innerHTML = `<div class="detail-placeholder"><div class="placeholder-mark" aria-hidden="true">お</div><p class="eyebrow">${escapeHtml(t("detail.eyebrow"))}</p><h3>${t("detail.placeholderTitle")}</h3><p>${escapeHtml(t("empty.body"))}</p></div>`;
}

function detailMarkup(notice) {
  const originalOnly = notice.extraction_status === "original_only";
  const attachmentHtml = (notice.attachments || []).slice(0, 80).map((item) => officialLink(item.url, item.title, "detail-link")).filter(Boolean).map((link) => `<li>${link}</li>`).join("");
  const categoryHtml = Object.entries(originalOnly ? {} : notice.categories || {}).map(([name, items]) => {
    const list = items.slice(0, 8).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    return `<section class="detail-section"><h4>${escapeHtml(localizeLabel(name))}</h4><ul>${list}</ul></section>`;
  }).join("");
  return `<div class="detail-content">
    <div class="notice-meta"><span class="pill">${escapeHtml(notice.source_name)}</span><span class="pill group-pill">${escapeHtml(localizeLabel(notice.source_group_label || "学校"))}</span><span class="pill soft">${escapeHtml(localizeLabel(notice.kind_label))}</span>${originalOnly ? `<span class="pill extraction-badge">${escapeHtml(t("extraction.unverified"))}</span>` : ""}</div>
    <h3 lang="ja">${escapeHtml(notice.title)}</h3>
    <p class="source-line notice-dates">${escapeHtml([notice.ward, ...((notice.source_group || "school") === "school" ? [localizeLabel(notice.level), localizeLabel(notice.grade)] : []), noticeDateText(notice)].filter(Boolean).join(" · "))}</p>
    ${isReference(notice) ? `<p class="reference-note">${escapeHtml(t("reference.title"))}</p>` : ""}
    ${officialLink(notice.url, t("detail.openOriginal"), "detail-link")}
    ${attachmentHtml ? `<details class="detail-section attachment-links"><summary>${escapeHtml(t("detail.attachments"))}</summary><p class="extraction-note">${escapeHtml(t("detail.attachmentsNote"))}</p><ul>${attachmentHtml}</ul></details>` : ""}
    <p class="extraction-note" lang="ja">${originalOnly ? "本文は確認できていません。公式の原文を開いてご確認ください。自動抽出（OCRを含む）には読み違い・抜けが生じる場合があります。" : "表示本文は機械による抽出結果です（画像資料ではOCRを使う場合があります）。読み違い・抜けが生じる場合があるため、日付や持ち物は公式の原文でご確認ください。"}</p>
    ${categoryHtml}
    <section class="detail-section"><h4>${escapeHtml(t(originalOnly ? "extraction.unverified" : "detail.original"))}</h4><div class="original-copy" lang="ja">${escapeHtml(notice.text)}</div></section>
  </div>`;
}

function renderDetail(notice, card = null, showInline = true) {
  $("detail-panel").innerHTML = detailMarkup(notice);
  document.querySelectorAll(".notice-card.expanded").forEach((otherCard) => {
    if (otherCard !== card || !showInline) {
      otherCard.classList.remove("expanded");
      otherCard.querySelector("button")?.setAttribute("aria-expanded", "false");
      const inlineDetail = otherCard.querySelector(".inline-detail");
      if (inlineDetail) inlineDetail.replaceChildren();
    }
  });
  if (card && showInline) {
    const inlineDetail = card.querySelector(".inline-detail");
    if (inlineDetail) {
      inlineDetail.innerHTML = detailMarkup(notice);
      card.classList.add("expanded");
      card.querySelector("button")?.setAttribute("aria-expanded", "true");
    }
  }
}

async function selectNotice(id, { showInline = true } = {}) {
  const detailRequestVersion = ++state.detailRequestVersion;
  const requestVersion = state.requestVersion;
  const selectedCard = [...document.querySelectorAll(".notice-card")].find((card) => card.dataset.noticeId === id);
  if (showInline && selectedCard?.classList.contains("expanded") && state.selectedId === id) {
    selectedCard.classList.remove("expanded", "selected");
    selectedCard.querySelector("button")?.setAttribute("aria-expanded", "false");
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
    selectedCard.querySelector("button")?.setAttribute("aria-expanded", "true");
  }
  try {
    const suffix = queryString();
    const detail = await api(`/api/notices/${encodeURIComponent(id)}${suffix ? `?${suffix}` : ""}`);
    if (state.selectedId !== id || requestVersion !== state.requestVersion || detailRequestVersion !== state.detailRequestVersion) return;
    renderDetail(detail, selectedCard, showInline);
  } catch (error) {
    if (state.selectedId !== id || requestVersion !== state.requestVersion || detailRequestVersion !== state.detailRequestVersion) return;
    const message = `<div class="detail-placeholder"><div class="placeholder-mark" aria-hidden="true">!</div><p class="eyebrow">${escapeHtml(t("detail.errorEyebrow"))}</p><h3>${escapeHtml(t("detail.errorTitle"))}</h3><p>${escapeHtml(error.message)}</p></div>`;
    $("detail-panel").innerHTML = message;
    if (selectedCard && showInline) {
      const inlineDetail = selectedCard.querySelector(".inline-detail");
      if (inlineDetail) inlineDetail.innerHTML = message;
    }
  }
}

function payloadRefreshing(payload) {
  return payload.refreshing === true || payload.coverage?.some((source) => source.refreshing === true || source.issue_codes?.includes("refreshing"));
}

function waitForRefreshPoll(signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Aborted", "AbortError")); return; }
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, REFRESH_POLL_INTERVAL_MS);
    function abort() {
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      reject(new DOMException("Aborted", "AbortError"));
    }
    signal.addEventListener("abort", abort, { once: true });
  });
}

async function loadNotices(refresh = false) {
  state.requestVersion += 1;
  const requestVersion = state.requestVersion;
  state.requestController?.abort();
  const controller = new AbortController();
  state.requestController = controller;
  state.refreshStatus = null;
  state.payload = null;
  let pollTimeout = null;
  let polling = false;
  let timedOut = false;
  setLoading(true);
  try {
    const query = queryString();
    const getPath = `/api/notices${query ? `?${query}` : ""}`;
    const path = `/api/${refresh ? "refresh" : "notices"}${query ? `?${query}` : ""}`;
    const options = refresh ? { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}", signal: controller.signal } : { signal: controller.signal };
    let payload = await api(path, options);
    if (requestVersion !== state.requestVersion || controller.signal.aborted) return;
    state.refreshStatus = payloadRefreshing(payload) ? "refreshing" : null;
    renderNotices(payload);
    setLoading(false);
    if (payloadRefreshing(payload)) {
      polling = true;
      // One deadline covers both the delays and any in-flight GET.
      pollTimeout = setTimeout(() => { timedOut = true; controller.abort(); }, REFRESH_POLL_TIMEOUT_MS);
      while (payloadRefreshing(payload)) {
        await waitForRefreshPoll(controller.signal);
        payload = await api(getPath, { signal: controller.signal });
        if (requestVersion !== state.requestVersion || controller.signal.aborted) return;
        state.refreshStatus = payloadRefreshing(payload) ? "refreshing" : null;
        // Unchanged cached responses should not collapse an open card or refetch its detail.
        if (JSON.stringify(payload) !== JSON.stringify(state.payload)) renderNotices(payload);
      }
    }
    if (refresh) {
      $("filter-summary").setAttribute("data-refreshed-at", payload.scanned_at || "");
    }
  } catch (error) {
    if (requestVersion !== state.requestVersion) return;
    if (polling && (timedOut || error?.name !== "AbortError")) {
      state.refreshStatus = timedOut ? "refreshTimeout" : "refreshError";
      renderCoverage(state.payload);
      return;
    }
    if (error?.name === "AbortError") return;
    $("notice-list").replaceChildren();
    $("empty-state").hidden = false;
    $("filter-summary").textContent = `${t("status.errorPrefix")}${error.message}`;
    renderPlaceholder();
  } finally {
    clearTimeout(pollTimeout);
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
      updatePushScopeLabels();
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
  state.push.statusKey = key;
  pilotStatus("notification-status", key);
  updatePushControls();
}

function updatePushControls() {
  const button = $("notification-button");
  if (button) {
    button.title = pilotText(state.push.statusKey);
    const label = button.querySelector("span:last-child");
    if (label) label.textContent = state.push.subscribed ? pilotText(state.push.ready ? "enabled" : "pausedLabel") : t("actions.notifications");
  }
  const enable = $("notification-enable");
  if (enable) enable.disabled = state.push.busy || !state.push.ready || !state.config || !$("notification-consent")?.checked;
  ["notification-unsubscribe", "privacy-delete", "privacy-export"].forEach((id) => {
    if ($(id)) $(id).disabled = state.push.busy;
  });
  if ($("notification-consent")) $("notification-consent").disabled = state.push.busy;
  updatePushScopeLabels();
}

function updatePushScopeLabels() {
  const field = $("notification-scopes");
  if (!field || !$("source-filter")) return;
  const scopeLabel = (scope) => {
    const value = (key) => typeof scope?.[key] === "string" ? scope[key].slice(0, 200) : "";
    const sourceId = value("source_id");
    const source = state.config?.sources.find((item) => item.id === sourceId);
    return [source?.name || (sourceId === "all" ? t("filters.allSchools") : sourceId || "—"), localizeLabel(value("grade") || "全学年"), t(value("feed") === "events" ? "feeds.events" : "feeds.notices"), value("group") === "all" ? t("filters.allGroups") : localizeLabel(({ school: "学校", municipality: "武蔵野市・教育委員会／市役所", after_school: "学童" })[value("group")] || value("group") || "—")].join(" · ");
  };
  const saved = state.push.scopesKnown ? (state.push.scopes.length ? state.push.scopes.map(scopeLabel).join(" / ") : pilotText("noScopes")) : pilotText("scopesUnknown");
  field.textContent = `${pilotText("displayedScope")}: ${scopeLabel(currentPushScope())}\n${pilotText("storedScope")}: ${saved}`;
}

function openNotificationSettings() {
  const opening = $("notification-settings").hidden;
  $("notification-settings").hidden = !opening;
  $("notification-button").setAttribute("aria-expanded", String(opening));
  if (opening) $("notification-consent").focus();
}

async function appPushRegistration() {
  if (!("serviceWorker" in navigator)) return null;
  const registration = state.push.registration || await navigator.serviceWorker.getRegistration("/");
  const worker = registration?.active || registration?.waiting || registration?.installing;
  if (!worker) return null;
  const url = new URL(worker.scriptURL, location.origin);
  return url.origin === location.origin && url.pathname === "/sw.js" ? registration : null;
}

async function removeBrowserPush() {
  const registration = await appPushRegistration();
  const subscription = await registration?.pushManager?.getSubscription();
  if (subscription && !await subscription.unsubscribe()) throw new Error("browser unsubscribe failed");
  return registration;
}

async function enablePushNotifications() {
  if (state.push.busy) return;
  if (!state.push.ready || !state.config) {
    setNotificationStatus("unavailable");
    return;
  }
  if (!$("notification-consent").checked) {
    setNotificationStatus("consentRequired");
    return;
  }
  state.push.busy = true;
  updatePushControls();
  let createdSubscription = null;
  try {
    const permission = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
    if (permission !== "granted") {
      setNotificationStatus("permission");
      return;
    }
    await navigator.serviceWorker.register("/sw.js");
    const registration = await navigator.serviceWorker.ready;
    state.push.registration = registration;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(state.push.config.public_key) });
      createdSubscription = subscription;
    }
    await api("/api/push/subscribe", { method: "POST", body: JSON.stringify({ subscription: subscription.toJSON(), scope: currentPushScope(), consent: true, consent_version: PILOT_POLICY_VERSION }) });
    state.push.subscribed = true;
    try {
      const status = await api("/api/push/status");
      state.push.scopes = Array.isArray(status.scopes) ? status.scopes : [];
      state.push.scopesKnown = true;
    } catch (_) { state.push.scopes = []; state.push.scopesKnown = false; }
    $("notification-consent").checked = false;
    setNotificationStatus("ready");
  } catch (_) {
    if (createdSubscription) {
      try { await createdSubscription.unsubscribe(); } catch (_) { /* Report that a browser subscription may remain. */ }
    }
    setNotificationStatus("error");
  } finally {
    state.push.busy = false;
    updatePushControls();
  }
}

async function setupPushNotifications() {
  $("notification-button").addEventListener("click", openNotificationSettings);
  $("notification-consent").addEventListener("change", updatePushControls);
  $("notification-enable").addEventListener("click", enablePushNotifications);
  $("notification-unsubscribe").addEventListener("click", unsubscribePushNotifications);
  $("privacy-export").addEventListener("click", exportDeviceData);
  $("privacy-delete").addEventListener("click", deleteDeviceData);
  state.push.busy = true;
  updatePushControls();
  try {
    const supported = "serviceWorker" in navigator && "Notification" in window && "PushManager" in window;
    const [pilot, config, status, data, registration] = await Promise.all([
      loadPilotConfig(), api("/api/push/config"), api("/api/push/status"), api("/api/privacy/data"),
      supported ? navigator.serviceWorker.register("/sw.js") : null,
    ]);
    state.push.config = config;
    state.push.registration = registration;
    const subscription = await registration?.pushManager.getSubscription();
    const recordedConsent = data.subscriptions?.some((item) => item.consent_version === PILOT_POLICY_VERSION);
    state.push.scopes = Array.isArray(status.scopes) ? status.scopes : [];
    state.push.scopesKnown = true;
    state.push.ready = supported && config.enabled && config.sending_enabled === true && Boolean(config.public_key) && config.consent_version === pilot.policy_version;
    state.push.subscribed = Boolean(status.subscribed && recordedConsent && subscription && Notification.permission === "granted");
    if (subscription && (!recordedConsent || !status.subscribed)) setNotificationStatus("reconsent");
    else if (status.subscribed && !state.push.subscribed) setNotificationStatus("serverOnly");
    else setNotificationStatus(config.sending_enabled !== true ? "paused" : state.push.subscribed ? "ready" : state.push.ready ? "consentRequired" : "unavailable");
    // Never POST or silently re-subscribe on load, filter changes or language changes.
  } catch (_) {
    state.push.ready = false;
    setNotificationStatus("statusError");
  } finally {
    state.push.busy = false;
    updatePushControls();
  }
}

async function unsubscribePushNotifications() {
  if (state.push.busy) return;
  state.push.busy = true;
  updatePushControls();
  let serverRemoved = false;
  try {
    await api("/api/push/unsubscribe", { method: "POST", body: "{}" });
    serverRemoved = true;
    state.push.subscribed = false;
    state.push.scopes = []; state.push.scopesKnown = true;
    $("notification-consent").checked = false;
    await removeBrowserPush();
    setNotificationStatus("off");
  } catch (_) {
    setNotificationStatus(serverRemoved ? "browserError" : "unsubscribeError");
  } finally {
    state.push.busy = false;
    updatePushControls();
  }
}

async function exportDeviceData() {
  if (state.push.busy) return;
  state.push.busy = true;
  updatePushControls();
  try {
    const data = safePilotExport(await api("/api/privacy/data"), localStorage);
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = `otayori-device-${PILOT_POLICY_VERSION}.json`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    pilotStatus("privacy-status", "exported");
  } catch (_) {
    pilotStatus("privacy-status", "exportError");
  } finally {
    state.push.busy = false;
    updatePushControls();
  }
}

async function deleteDeviceData() {
  if (state.push.busy || !window.confirm(pilotText("confirmDelete"))) return;
  state.push.busy = true;
  updatePushControls();
  let serverRemoved = false;
  try {
    await api("/api/privacy/delete", { method: "POST", body: "{}" });
    serverRemoved = true; // Successful server response also expires the HttpOnly cookie.
    state.push.subscribed = false;
    state.push.scopes = []; state.push.scopesKnown = true;
    state.requestVersion += 1;
    state.requestController?.abort();
    state.refreshStatus = null;
    setLoading(false);
    const results = await Promise.allSettled([
      (async () => { await removeBrowserPush(); const registration = await appPushRegistration(); if (registration && !await registration.unregister()) throw new Error("unregister failed"); state.push.registration = null; })(),
      (async () => { PILOT_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key)); })(),
      (async () => { if ("caches" in window) { const keys = await caches.keys(); await Promise.all(keys.filter((key) => key.startsWith(PILOT_CACHE_PREFIX)).map(async (key) => { if (!await caches.delete(key)) throw new Error("cache deletion failed"); })); } })(),
    ]);
    $("notification-consent").checked = false;
    state.nearbyDistances = new Map();
    renderSourceOptions("all");
    $("grade-filter").value = "全学年";
    $("group-filter").value = "all";
    $("ward-filter").value = "all";
    $("level-filter").value = "all";
    state.selectedId = null; state.notices = []; state.payload = null;
    $("notice-list").replaceChildren();
    $("coverage-details").hidden = true;
    $("coverage-alert").hidden = true;
    $("filter-summary").textContent = t("summary.noData");
    $("feedback-issue").value = ""; $("feedback-template").value = "";
    $("feedback-fallback").hidden = true;
    $("feedback-status").textContent = ""; delete $("feedback-status").dataset.pilotStatus;
    document.body.classList.remove("dark");
    applyLanguage("ja", false);
    renderPlaceholder();
    setNotificationStatus(results[0].status === "rejected" ? "browserError" : "off");
    pilotStatus("privacy-status", results.some((result) => result.status === "rejected") ? "deletePartial" : "deleted");
  } catch (_) {
    pilotStatus("privacy-status", serverRemoved ? "deletePartial" : "deleteError");
  } finally {
    state.push.busy = false;
    updatePushControls();
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
    updatePushControls();
    ["source-filter", "level-filter", "ward-filter", "grade-filter", "group-filter"].forEach((id) => $(id).addEventListener("change", () => { savePreferences(); updateFilterContext(); loadNotices(false); }));
    $("refresh-button").addEventListener("click", () => loadNotices(true));
    await loadNotices(false);
  } catch (error) {
    $("filter-summary").textContent = `${t("status.errorPrefix")}${error.message}`;
    $("empty-state").hidden = false;
  }
}

document.addEventListener("DOMContentLoaded", boot);
