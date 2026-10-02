const PILOT_POLICY_VERSION = "2026-10-01";
const PILOT_STORAGE_KEYS = ["school-news-source", "school-news-grade", "school-news-group", "school-news-language", "school-news-theme"];
const PILOT_CACHE_PREFIX = "otayori-desk-shell-";
const PILOT_TEXT = {
  ja: {
    free: "無料ベータ · 課金なし", pilotError: "無料ベータの設定を確認できません。通知の新規設定は停止中です。",
    consentScope: "選択中の学校・学年などの条件で通知します。通知先・暗号鍵・選択条件をサーバーに保存し、ランダムな端末Cookie（HttpOnly）で管理します。",
    consent: "通知用データの保存・利用に同意します（任意）。", consentPolicy: "プライバシー・利用条件を確認（日本語）", enable: "同意して通知を設定", unsubscribe: "この端末の通知を解除",
    deviceSettings: "この端末のデータ・通知管理", deviceNote: "端末Cookieで識別できる登録のみが対象です。別端末やCookieを失った登録はここでは削除できません。通知を最後に登録・更新してから180日で、サーバーの登録は削除されます。閲覧だけでは延長されません。",
    export: "データをJSONで保存", delete: "この端末のデータを削除", policiesJapanese: "ポリシーは日本語",
    feedback: "不具合・ご意見", feedbackNote: "コピーした内容を、このベータに招待してくれた方へお送りください。この画面から送信・保存はしません。お子さまの名前や非公開のお知らせは書かないでください。", issue: "困ったこと・ご意見", copy: "共有用テンプレートをコピー", manualCopy: "下の内容を選択してコピーしてください。", select: "内容を選択", copied: "コピーしました。招待してくれた方へお送りください。", issueRequired: "困ったこと・ご意見を入力してください。", choose: "未選択",
    unavailable: "この環境では通知を設定できません。", permission: "ブラウザの通知が許可されていません。", ready: "選択した条件で登録しました。通知の到達は保証されません。", enabled: "通知設定済み", consentRequired: "チェックを入れて同意してから通知を設定してください。", reconsent: "以前の購読が残っています。現在の方針への同意を確認できないため、再同意して設定してください。", serverOnly: "サーバー登録はありますが、ブラウザ購読を確認できません。再設定または解除してください。", error: "通知登録を完了できませんでした。ブラウザの購読が残っている場合は解除して再試行してください。", statusError: "端末の通知・同意状況を確認できませんでした。再読み込みしてください。", off: "この端末の通知を解除しました。", unsubscribeError: "サーバーの通知解除を確認できませんでした。ブラウザ購読は変更していません。再試行してください。", browserError: "サーバー登録は解除しましたが、ブラウザ購読を解除できませんでした。ブラウザの通知設定を確認し、再試行してください。",
    confirmDelete: "この端末Cookieで識別できるサーバー登録・Cookieと、このアプリの設定・キャッシュ・Push購読を削除しますか？ 別端末やCookieを失った登録は削除できません。",
    deleted: "この端末のサーバー登録・Cookieと、このアプリの設定・キャッシュ・Push購読を削除しました。", deleteError: "サーバー削除を確認できませんでした。端末内のデータは変更していません。再試行してください。", deletePartial: "サーバー登録・Cookieは削除しましたが、端末内の一部の削除に失敗しました。再試行し、ブラウザの設定も確認してください。", exported: "送信先・暗号鍵・Cookie値を除いたJSONを保存しました。", exportError: "データを取得・保存できませんでした。再試行してください。", partial: "一部の情報源は確認が不完全です。公式の原文も確認してください。",
  },
  ko: {
    free: "무료 베타 · 결제 없음", pilotError: "무료 베타 설정을 확인하지 못했습니다. 새 알림 설정이 중지되었습니다.", consentScope: "선택한 학교·학년 등의 조건으로 알립니다. 알림 주소·암호화 키·선택 조건을 서버에 저장하고 무작위 기기 쿠키(HttpOnly)로 관리합니다.", consent: "알림용 데이터 저장·이용에 동의합니다(선택).", consentPolicy: "개인정보·이용 조건 확인(일본어)", enable: "동의하고 알림 설정", unsubscribe: "이 기기 알림 해제", deviceSettings: "이 기기의 데이터·알림 관리", deviceNote: "기기 쿠키로 확인되는 등록만 대상입니다. 다른 기기나 쿠키를 잃은 등록은 여기서 삭제할 수 없습니다. 알림을 마지막으로 등록·갱신한 뒤 180일 후 서버 등록이 삭제됩니다. 열람만으로는 연장되지 않습니다.", export: "데이터 JSON 저장", delete: "이 기기 데이터 삭제", policiesJapanese: "정책은 일본어", feedback: "오류·의견", feedbackNote: "복사한 내용을 베타에 초대한 분에게 보내 주세요. 이 화면에서는 전송·저장하지 않습니다. 아이 이름이나 비공개 안내는 쓰지 마세요.", issue: "문제·의견", copy: "공유 템플릿 복사", manualCopy: "아래 내용을 선택해 복사해 주세요.", select: "내용 선택", copied: "복사했습니다. 초대한 분에게 보내 주세요.", issueRequired: "문제·의견을 입력해 주세요.", choose: "미선택", unavailable: "이 환경에서는 알림을 설정할 수 없습니다.", permission: "브라우저 알림이 허용되지 않았습니다.", ready: "선택 조건으로 등록했습니다. 알림 도착은 보장되지 않습니다.", enabled: "알림 설정됨", consentRequired: "동의 체크 후 알림을 설정해 주세요.", reconsent: "이전 구독이 남아 있습니다. 현재 정책 동의를 확인할 수 없어 다시 동의해 설정해야 합니다.", serverOnly: "서버 등록은 있으나 브라우저 구독을 확인할 수 없습니다. 재설정하거나 해제해 주세요.", error: "알림 등록을 완료하지 못했습니다. 브라우저 구독이 남아 있으면 해제 후 다시 시도해 주세요.", statusError: "기기의 알림·동의 상태를 확인하지 못했습니다. 새로고침해 주세요.", off: "이 기기의 알림을 해제했습니다.", unsubscribeError: "서버 해제를 확인하지 못했습니다. 브라우저 구독은 변경하지 않았습니다. 다시 시도해 주세요.", browserError: "서버 등록은 해제했으나 브라우저 구독 해제에 실패했습니다. 브라우저 알림 설정을 확인하고 다시 시도해 주세요.", confirmDelete: "이 기기 쿠키로 확인되는 서버 등록·쿠키와 이 앱의 설정·캐시·Push 구독을 삭제할까요? 다른 기기나 쿠키를 잃은 등록은 삭제할 수 없습니다.", deleted: "이 기기의 서버 등록·쿠키와 이 앱의 설정·캐시·Push 구독을 삭제했습니다.", deleteError: "서버 삭제를 확인하지 못했습니다. 기기 내 데이터는 변경하지 않았습니다. 다시 시도해 주세요.", deletePartial: "서버 등록·쿠키는 삭제했으나 기기 내 일부 삭제에 실패했습니다. 다시 시도하고 브라우저 설정도 확인해 주세요.", exported: "알림 주소·암호화 키·쿠키 값을 제외한 JSON을 저장했습니다.", exportError: "데이터를 가져오거나 저장하지 못했습니다. 다시 시도해 주세요.", partial: "일부 정보원 확인이 불완전합니다. 공식 원문도 확인해 주세요.",
  },
  en: {
    free: "Free beta · no billing", pilotError: "Could not verify free beta settings. New notification setup is paused.", consentScope: "Notifications use your selected school, grade and filters. The server stores the push endpoint, encryption keys and filters, managed by a random device cookie (HttpOnly).", consent: "I agree to storage and use of notification data (optional).", consentPolicy: "Read privacy and terms (Japanese)", enable: "Agree and set up notifications", unsubscribe: "Turn off this device's notifications", deviceSettings: "This device's data & notifications", deviceNote: "Only records identified by this device cookie are included. Other devices and records with a lost cookie cannot be deleted here. Server records are deleted 180 days after the last notification registration or update. Viewing alone does not extend retention.", export: "Save data as JSON", delete: "Delete this device's data", policiesJapanese: "Policies in Japanese", feedback: "Bugs & feedback", feedbackNote: "Send the copied template to the person who invited you. This screen does not send or store feedback. Do not include children's names or private notices.", issue: "Problem or feedback", copy: "Copy sharing template", manualCopy: "Select and copy the text below.", select: "Select text", copied: "Copied. Send it to the person who invited you.", issueRequired: "Enter your problem or feedback.", choose: "Not selected", unavailable: "Notifications cannot be configured in this environment.", permission: "Browser notifications are not allowed.", ready: "Registered for your selected filters. Notification delivery is not guaranteed.", enabled: "Notifications set up", consentRequired: "Check the consent box before setting up notifications.", reconsent: "An older subscription remains. Current policy consent could not be verified; agree again to set up notifications.", serverOnly: "A server record exists, but no browser subscription was confirmed. Set it up again or turn it off.", error: "Notification registration did not finish. If a browser subscription remains, turn it off and retry.", statusError: "Could not check this device's notification and consent status. Reload the page.", off: "This device's notifications were turned off.", unsubscribeError: "Server removal could not be confirmed. The browser subscription was not changed. Retry.", browserError: "Server records were removed, but browser unsubscription failed. Check browser notification settings and retry.", confirmDelete: "Delete server records and cookie identified by this device cookie, plus this app's preferences, cache and push subscription? Other devices and records with a lost cookie cannot be deleted.", deleted: "Deleted this device's server records and cookie, and this app's preferences, cache and push subscription.", deleteError: "Server deletion could not be confirmed. Local data was not changed. Retry.", deletePartial: "Server records and cookie were deleted, but some local cleanup failed. Retry and check browser settings.", exported: "Saved JSON without push endpoints, encryption keys or cookie values.", exportError: "Could not retrieve or save data. Retry.", partial: "Some sources could not be fully checked. Check the official originals too.",
  },
  zh: {
    free: "免费测试版 · 不收费", pilotError: "无法确认免费测试设置。已暂停新的通知设置。", consentScope: "按所选学校、年级等条件通知。服务器保存通知地址、加密密钥和筛选条件，并用随机设备Cookie（HttpOnly）管理。", consent: "我同意存储和使用通知数据（可选）。", consentPolicy: "查看隐私与使用条件（日语）", enable: "同意并设置通知", unsubscribe: "关闭本设备通知", deviceSettings: "本设备数据与通知管理", deviceNote: "仅处理本设备Cookie可识别的记录。无法在此删除其他设备或丢失Cookie的记录。通知最后登记或更新180天后，服务器记录会删除。仅浏览不会延长保存期限。", export: "保存JSON数据", delete: "删除本设备数据", policiesJapanese: "政策为日语", feedback: "问题与意见", feedbackNote: "请将复制的内容发给邀请您参加测试的人。此页面不发送或保存反馈。请勿填写孩子姓名或非公开通知。", issue: "问题或意见", copy: "复制分享模板", manualCopy: "请选择并复制下方内容。", select: "选择内容", copied: "已复制。请发给邀请您的人。", issueRequired: "请输入问题或意见。", choose: "未选择", unavailable: "此环境无法设置通知。", permission: "浏览器未允许通知。", ready: "已按所选条件登记，不保证通知送达。", enabled: "通知已设置", consentRequired: "请先勾选同意再设置通知。", reconsent: "仍有旧订阅。无法确认当前政策同意，请重新同意并设置。", serverOnly: "有服务器记录，但未确认浏览器订阅。请重新设置或关闭。", error: "通知登记未完成。若浏览器仍有订阅，请关闭后重试。", statusError: "无法确认本设备通知及同意状态，请重新加载。", off: "已关闭本设备通知。", unsubscribeError: "无法确认服务器解除，未更改浏览器订阅。请重试。", browserError: "服务器记录已解除，但浏览器解除失败。请检查浏览器通知设置并重试。", confirmDelete: "删除本设备Cookie可识别的服务器记录、Cookie，以及此应用的设置、缓存和Push订阅？无法删除其他设备或丢失Cookie的记录。", deleted: "已删除本设备服务器记录、Cookie及此应用设置、缓存和Push订阅。", deleteError: "无法确认服务器删除，未更改本地数据。请重试。", deletePartial: "服务器记录和Cookie已删除，但部分本地清除失败。请重试并检查浏览器设置。", exported: "已保存不含通知地址、加密密钥及Cookie值的JSON。", exportError: "无法获取或保存数据，请重试。", partial: "部分信息来源未能完整确认。请同时查看官方原文。",
  },
};
let pilotLanguage = "ja";
let pilotConfigPromise;

Object.assign(PILOT_TEXT.ja, { displayedScope: "表示中の条件", storedScope: "サーバーに登録済みの通知条件", noScopes: "登録なし", scopesUnknown: "未確認", scopeNote: "表示条件を変えても通知条件は変わりません。変更するには、同意して選択中の条件を保存してください。", paused: "通知配信は停止中です。新規登録・条件の保存はできません。", pausedLabel: "登録済み・配信停止中" });
Object.assign(PILOT_TEXT.ko, { displayedScope: "표시 중인 조건", storedScope: "서버에 저장된 알림 조건", noScopes: "등록 없음", scopesUnknown: "미확인", scopeNote: "표시 필터를 바꿔도 알림 조건은 바뀌지 않습니다. 동의 후 선택 조건을 저장해 주세요.", paused: "알림 전송이 중지되었습니다. 새 등록·조건 저장을 할 수 없습니다.", pausedLabel: "등록됨·전송 중지" });
Object.assign(PILOT_TEXT.en, { displayedScope: "Displayed filters", storedScope: "Notification filters stored on the server", noScopes: "None registered", scopesUnknown: "Not verified", scopeNote: "Changing displayed filters does not change notifications. Agree again to save the selected filters.", paused: "Notification delivery is paused. New registration and filter saving are disabled.", pausedLabel: "Registered · delivery paused" });
Object.assign(PILOT_TEXT.zh, { displayedScope: "当前显示条件", storedScope: "服务器保存的通知条件", noScopes: "没有登记", scopesUnknown: "未确认", scopeNote: "更改显示条件不会更改通知条件。请重新同意并保存所选条件。", paused: "通知发送已暂停，无法新登记或保存条件。", pausedLabel: "已登记·发送暂停" });

Object.assign(PILOT_TEXT.ja, { testNotification: "この端末にテスト通知", testSending: "テスト通知を送信中…", testAccepted: "配信サービスが受け付けました。到着はまだ未確認です。この端末の通知欄をご確認ください。届かない場合は端末・ブラウザの通知設定も確認してください。", testError: "送信できませんでした。通知設定を確認し、1分以上待って再試行してください。" });
Object.assign(PILOT_TEXT.ko, { testNotification: "이 기기로 테스트 알림", testSending: "테스트 알림 전송 중…", testAccepted: "전송 서비스가 접수했습니다. 실제 도착은 아직 확인되지 않았습니다. 이 기기의 알림함을 확인하세요. 없으면 기기·브라우저의 알림 설정도 확인하세요.", testError: "전송하지 못했습니다. 알림 설정을 확인하고 1분 이상 기다린 후 다시 시도하세요." });
Object.assign(PILOT_TEXT.en, { testNotification: "Test notification on this device", testSending: "Sending a test notification…", testAccepted: "Accepted by the push service; arrival is not yet verified. Check this device's notifications. If nothing arrives, check device and browser notification settings.", testError: "Could not send. Check notification settings and wait at least one minute before retrying." });
Object.assign(PILOT_TEXT.zh, { testNotification: "向本设备发送测试通知", testSending: "正在发送测试通知…", testAccepted: "推送服务已接受，尚未确认实际送达。请查看本设备通知栏。如未收到，请检查设备和浏览器的通知设置。", testError: "无法发送。请检查通知设置，至少等待一分钟后重试。" });

function pilotText(key) { return PILOT_TEXT[pilotLanguage]?.[key] || PILOT_TEXT.ja[key] || key; }

function applyPilotLanguage(language) {
  pilotLanguage = PILOT_TEXT[language] ? language : "ja";
  document.querySelectorAll("[data-pilot-i18n]").forEach((element) => { element.textContent = pilotText(element.dataset.pilotI18n); });
  document.querySelectorAll("[data-pilot-status]").forEach((element) => { element.textContent = pilotText(element.dataset.pilotStatus); });
}

function pilotStatus(id, key) {
  const element = document.getElementById(id);
  if (element) { element.dataset.pilotStatus = key; element.textContent = pilotText(key); }
}

async function pilotApi(path, options = {}) {
  const response = await fetch(path, {
    ...options, credentials: "same-origin", cache: "no-store",
    headers: { Accept: "application/json", ...(options.method === "POST" ? { "Content-Type": "application/json" } : {}), ...options.headers },
    ...(options.method === "POST" && options.body == null ? { body: "{}" } : {}),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function loadPilotConfig() {
  if (!pilotConfigPromise) pilotConfigPromise = pilotApi("/api/pilot").then((config) => {
    if (config.mode !== "free_beta" || config.payments_enabled !== false || config.policy_version !== PILOT_POLICY_VERSION || config.retention_days !== 180) throw new Error("pilot settings mismatch");
    pilotStatus("pilot-mode", "free");
    return config;
  }).catch((error) => { pilotStatus("pilot-mode", "pilotError"); throw error; });
  return pilotConfigPromise;
}

function safePilotExport(payload, preferences) {
  // Allowlist every level: future API fields must not expose endpoints, keys or cookies.
  const text = (value) => typeof value === "string" ? value.slice(0, 200) : null;
  return {
    policy_version: PILOT_POLICY_VERSION, device_only: true,
    subscriptions: (Array.isArray(payload.subscriptions) ? payload.subscriptions : []).map((item) => ({
      scope: Object.fromEntries(["source_id", "grade", "feed", "group"].map((key) => [key, text(item.scope?.[key])])),
      created_at: text(item.created_at), updated_at: text(item.updated_at), consent_version: text(item.consent_version),
    })),
    preferences: Object.fromEntries(PILOT_STORAGE_KEYS.map((key) => [key, text(preferences.getItem(key))])),
  };
}

function publicFeedbackUrl(value) {
  try {
    const url = new URL(value, location.origin);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return "";
    // Exclude query/hash values that might contain identifying or secret data.
    return `${url.origin}${url.pathname}`;
  } catch (_) { return ""; }
}

function feedbackTemplate(issue) {
  const school = document.getElementById("source-filter")?.selectedOptions[0]?.textContent || pilotText("choose");
  const grade = document.getElementById("grade-filter")?.selectedOptions[0]?.textContent || pilotText("choose");
  const source = document.querySelector(".notice-card.selected .card-source-link")?.getAttribute("href");
  return `おたより desk · 無料ベータ / feedback\nページ / Page: ${publicFeedbackUrl(location.href)}\n学校 / School: ${school}\n学年 / Grade: ${grade}\n原文 / Source: ${source ? publicFeedbackUrl(source) : pilotText("choose")}\n内容 / Issue:\n${issue}\n\n招待してくれた方へお送りください。子どもの名前・非公開のお知らせは含めないでください。`;
}

function setupPilotFeedback() {
  const panel = document.getElementById("feedback");
  if (!panel) return;
  const openHashPanel = () => {
    if (["#feedback", "#device-settings"].includes(location.hash)) {
      const target = document.getElementById(location.hash.slice(1));
      if (target) { target.open = true; target.scrollIntoView({ block: "start" }); }
    }
  };
  openHashPanel();
  window.addEventListener("hashchange", openHashPanel);
  document.getElementById("feedback-select").addEventListener("click", () => {
    const field = document.getElementById("feedback-template");
    field.focus(); field.select(); field.setSelectionRange(0, field.value.length);
  });
  document.getElementById("feedback-copy").addEventListener("click", async () => {
    const issue = document.getElementById("feedback-issue").value.trim();
    if (!issue) { pilotStatus("feedback-status", "issueRequired"); return; }
    const template = feedbackTemplate(issue);
    const fallback = document.getElementById("feedback-fallback");
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(template);
      fallback.hidden = true;
      pilotStatus("feedback-status", "copied");
    } catch (_) {
      fallback.hidden = false;
      const field = document.getElementById("feedback-template");
      field.value = template; field.focus(); field.select(); field.setSelectionRange(0, template.length);
      pilotStatus("feedback-status", "manualCopy");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadPilotConfig().catch(() => { /* Configuration error is visible; consent stays disabled. */ });
  setupPilotFeedback();
});
