# おたより desk — 학교 공지 집계 베타

이 저장소에는 두 가지 경로가 함께 있습니다.

- `web`: 도쿄 학교 홈페이지의 공개 공지를 학교·학교급·지역별로 한 화면에서 보는 보호자용 빠른 베타
- `run` / `prepare` / `deliver`: 기존 桜野小学校 공지를 학년별로 추출해 LINE Messaging API로 중복 없이 보내는 자동화

웹 베타는 학교가 새 시스템에 가입해야 하는 서비스가 아닙니다. 공개된 학교 홈페이지의 PDF/HTML만 읽고, 일본어 원문과 공식 링크를 함께 표시합니다. 결석 연락, 비공개 학교 앱, 보호자 인증 영역은 범위에 포함하지 않습니다.

## 바쁜 보호자를 위한 첫 화면 원칙

퇴근 후 긴 목록을 다시 읽지 않아도 되도록 첫 화면은 다음 순서로 동작합니다.

- 가장 최근 월의 정보만 바로 펼쳐 보여주고, 지난 달 자료는 접힌 상태로 둡니다.
- `学校・生活`과 `イベント`를 탭으로 나눠, 오늘 준비해야 하는 공지와 지역 행사 목록을 섞지 않습니다.
- 카드 색과 라벨로 `学校`·`武蔵野市・教育委員会／市役所`·`学童`의 발신처를 구분합니다.
- `発信元` 필터로 학교·시청/교육위원회·학동을 따로 볼 수 있고, 학동은 학교 선택과 같은 흐름에서 함께 확인합니다.
- 모든 카드와 상세 화면에 `原文` 링크를 남깁니다. 요약은 판단을 돕는 화면이고, 최종 확인은 학교·시청의 공식 원문에서 하도록 합니다.
- `10月号` 같은 호수와 실제 게시일을 따로 표시합니다. 예를 들어 10월호를 9월 18일에 게시했다면 `10月号 · 掲載 2026/09/18`로 보이며, 본문에 언급된 다음 호 때문에 게시월이 바뀌지 않습니다.

화면의 기본 언어는 일본어이며 한국어·영어·중국어를 선택할 수 있습니다. 문서 본문은 원문인 일본어를 보존하고, 메뉴·필터·분류 라벨만 선택 언어로 바꿉니다.

학교 선택은 앱 전환을 고려해 소스 레지스트리의 좌표와 공식 URL을 별도 필드로 유지합니다. 웹에서는 위치 권한을 직접 누른 경우에만 가까운 학교 순으로 정렬하고 `地図で見る` 링크를 제공합니다. 나중에 iOS/Android 앱을 만들 때 같은 `/api/config`, `/api/notices`, `/api/push`를 사용해 네이티브 지도 SDK와 연결할 수 있도록, 화면에 지도 타일을 강제로 넣지 않았습니다.

## 학부모 문제 검증

개발 전에 “정보가 여러 곳에 흩어져 있고 종이 공지를 놓친다”는 가설을 도쿄 공식 자료와 기존 서비스 자료로 확인했습니다. 조사 결과와 출처는 [RESEARCH.md](RESEARCH.md)에 기록했습니다.

- 도쿄 미나토구 공식 의견에는 학교를 옮긴 보호자가 학교마다 도구가 달라 불편하고 종이 서류가 너무 많다고 제안한 사례가 있습니다.
- 학부모 조사에서는 학교 서류를 잃어버리거나 버린 경험, 디지털 관리의 낮은 이용이 확인됐습니다. 다만 2019년 조사이므로 현재 수치로 과장하지 않습니다.
- CoDMON, tetoru, 楽メ, スクリレ, マチコミ 같은 기존 제품은 학교·지자체가 도입하는 전달 시스템이 중심입니다. 이 베타의 차별점은 공개 홈페이지를 보호자 관점에서 여러 학교·학교급으로 가로로 모으는 것입니다.

## 웹 베타 실행

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# sources.json의 검증된 공개 소스를 읽어 로컬 웹앱을 시작합니다.
python -m sakurano_line_notifier web --port 8765
```

브라우저에서 [http://127.0.0.1:8765](http://127.0.0.1:8765)을 엽니다. 화면의 기본 언어는 일본어이며, 첫 화면은 보호자의 실제 사용 흐름에 맞춰 `桜野小学校・1年生`을 먼저 보여줍니다. 학교·학년을 바꾸면 브라우저에 마지막 선택을 기억합니다. `すべての学校`을 선택하면 등록된 베타 소스를 가로로 비교할 수 있습니다.

### Railway 공개 배포

Railway에서는 `Procfile`과 `railway.toml`의 명령으로 `0.0.0.0:$PORT`에 웹앱을 띄웁니다. 웹 베타는 공개 학교 페이지를 읽는 서비스라 LINE 토큰 없이도 실행되며, LINE 토큰은 GitHub Actions Secrets에만 둡니다.

```bash
railway login
railway init --name otayori-desk
railway up
railway domain
```

`railway domain`이 발급한 `*.up.railway.app` 주소가 보호자용 공개 링크입니다. 배포 후 `/api/health`가 `{"ok":true}`를 반환하는지 확인합니다. Railway 프로젝트 연결 정보는 로컬 `.railway` 파일이나 비밀키를 저장소에 커밋하지 않습니다.

첫 베타의 해결 대상은 “도쿄 전체 학교를 검색하는 재미”가 아니라, 보호자가 자기 아이 학교의 공지를 매번 여러 페이지와 PDF에서 찾아야 하는 불편입니다. 학교·학년을 기본값으로 고정하고, 최신 공지를 먼저 보여주며, `持ち物・準備`·`提出物・締切`·`行事・予定`·`保護者への連絡`으로 나눠 확인 동작을 줄입니다. 공개된 공식 링크를 모으는 서비스이므로, 보호자 전용 앱인 `保護者連絡帳` 안의 비공개 배포문까지 임의로 가져오지는 않습니다. 해당 화면에서 연결되는 공개 시청·행사 페이지는 별도 이벤트 피드에 등록할 수 있습니다.

기본 레지스트리 [sources.json](sources.json)에는 다음 샘플이 들어 있습니다.

| 지역 | 학교급 | 학교 | 수집 방식 |
| --- | --- | --- | --- |
| 武蔵野市 | 小学校 | 桜野小学校 | PDF / 학년 추출 |
| 武蔵野市 | 小学校 | 桜野・第一・第二・第三・第四・第五・大野田・境南・本宿・千川・井之頭・関前南小学校 | PDF |
| 武蔵野市 | 学童 | 市立12校区のこどもクラブ | 公式施設情報 |
| 港区 | 小学校 | 芝浦小学校 | PDF |
| 文京区 | 小学校 | 誠之小学校 | PDF |
| 世田谷区 | 小学校 | 桜町小学校 | PDF |
| 渋谷区 | 小学校 | 神南小学校 | PDF |
| 世田谷区 | 中学校 | 瀬田中学校 | PDF |
| 渋谷区 | 高等学校 | 青山高等学校 | HTML 뉴스 |

도쿄 23구 전체를 한 번에 다 긁는 것으로 가장하지 않았습니다. 학교마다 CMS와 링크 형식이 달라, 실제 페이지·링크를 확인한 학교만 베타에 넣고 `sources.json`에 소스별 수집 방식을 명시합니다. 현재는 지인이 많은 무사시노시를 우선해 시립 초등학교 12곳과 학동 12개 학구를 등록했습니다. 새 학교를 추가할 때는 `id`, `name`, `ward`, `level`, `page_url` 또는 여러 페이지를 묶는 `page_urls`, `mode`를 넣고, 필요하면 `include_patterns`와 `exclude_patterns`를 조정합니다. HTML 뉴스형 학교는 `mode: "html_news"`를 사용합니다. 한 학교의 학교 홈페이지·学年だより·행사 페이지가 서로 분리되어 있다면 `page_urls`에 함께 넣어 같은 학교 피드로 합칩니다. 장기적으로는 동일한 스키마를 자치체 단위의 전국 소스 등록·검증 파이프라인으로 확장합니다.

웹 베타는 5분 메모리 캐시와 영속 SQLite 공개자료 캐시(`WEB_CATALOG_CACHE_PATH`)를 함께 사용합니다. Railway에서는 `/data/catalog_cache.sqlite3`를 지정해 재배포 뒤에도 마지막으로 확인한 공개 공지를 먼저 보여주고, 서버는 `WEB_CATALOG_REFRESH_INTERVAL_SECONDS`(기본 15분)마다 실제 페이지를 백그라운드에서 갱신합니다. `今すぐ更新`은 캐시를 기다리지 않고 실제 공개 페이지를 다시 확인하며, 여러 학교를 한 번에 조회할 때는 `WEB_CATALOG_MAX_WAIT_SECONDS`(기본 12초) 안에 완료된 소스부터 부분 응답하고 늦은 소스는 공유 수집 작업으로 계속 캐시에 반영합니다. 요청마다 같은 PDF 수집 작업을 중복 생성하지 않으며, 부모 화면이 한 학교의 느린 PDF 때문에 멈추지 않게 하는 운영 경계입니다. 소스별 좌표는 지도/앱 전환용 메타데이터이며 위치 권한 없이는 읽지 않습니다.

### 브라우저 알림과 앱 전환

`通知を受け取る` 버튼은 PWA Service Worker와 Web Push를 사용합니다. 브라우저 권한을 허용하면 현재 선택한 학교·학년·피드·발신처 조건이 서버에 구독으로 저장되고, 서버가 새 공개 문서 또는 내용 변경을 감지했을 때 같은 공지를 한 번만 보냅니다. 이 방식은 앱을 만들 때도 웹뷰 알림이 아니라 네이티브 푸시 토큰/구독 어댑터로 교체할 수 있도록 알림 조건을 API의 `scope`로 분리합니다.

학동 시설은 학교 공지처럼 매달 PDF가 올라오는 피드가 아니라 시설명·주소·운영 주체를 확인하는 정보입니다. 배포 서버의 공공 사이트 봇 차단으로 원문을 매 요청마다 읽을 수 없는 경우에도, 공식 원문 URL을 카드에 남기면서 마지막으로 확인한 공개 정보를 레지스트리에 보존해 선택과 기본 안내가 끊기지 않도록 했습니다. 이용시간·모집·휴일처럼 바뀔 수 있는 내용은 카드의 공식 링크에서 최종 확인합니다.

Railway에서는 `WEB_PUSH_DATABASE_PATH`를 영속 볼륨 경로로 지정하면 SQLite DB에 구독과 중복 발송 상태가 저장되어 재배포 뒤에도 유지됩니다. 다중 레플리카가 필요한 단계에서는 `WEB_PUSH_DATABASE_URL`에 관리형 PostgreSQL URL을 넣으면 같은 저장소 계약으로 전환됩니다. `WEB_PUSH_STATE_PATH`는 로컬 호환용 JSON fallback입니다. `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY`, `WEB_PUSH_CONTACT`를 설정하지 않으면 버튼은 준비중 상태로 표시되며, 원문 집계 자체는 계속 동작합니다.

필수 운영 변수:

| 이름 | 내용 |
| --- | --- |
| `WEB_PUSH_PUBLIC_KEY` | VAPID 공개키 |
| `WEB_PUSH_PRIVATE_KEY` | VAPID 개인키. 저장소에 커밋하지 않음 |
| `WEB_PUSH_CONTACT` | `mailto:owner@example.com` 형식의 운영 연락처 |
| `WEB_PUSH_DATABASE_PATH` | 단일 인스턴스용 SQLite 예: `/data/push_subscriptions.sqlite3` |
| `WEB_PUSH_DATABASE_URL` | 다중 인스턴스용 PostgreSQL URL. 비밀값으로만 설정 |
| `WEB_PUSH_STATE_PATH` | JSON fallback 예: `state/push_subscriptions.json` |
| `WEB_PUSH_SCAN_INTERVAL_SECONDS` | 새 소식 확인 주기. 기본 900초 |
| `WEB_CATALOG_REFRESH_INTERVAL_SECONDS` | 백그라운드 공개 소스 갱신 주기. 기본 900초 |
| `WEB_CATALOG_MAX_WAIT_SECONDS` | 한 API 응답이 기다리는 최대 소스 확인 시간. 기본 12초 |
| `WEB_CATALOG_CACHE_PATH` | 공개 공지 캐시 SQLite 경로. Railway 예: `/data/catalog_cache.sqlite3` |

### 장기 확장과 보안 경계

- `sources.json`은 코드에서 분리된 검토 가능한 공개 소스 레지스트리입니다. 학교·학동·시청 그룹, 학교급, 지역, 좌표, 공식 원문 링크를 같은 계약으로 저장하므로 모바일 앱이 HTML을 직접 긁지 않고 API를 사용할 수 있습니다.
- 보호자별로 변하는 구독과 중복 발송 기준선은 DB에만 저장합니다. 구독 endpoint·키는 SQLite 파일 권한을 제한하고, PostgreSQL 전환 시에도 파라미터 바인딩으로만 저장합니다.
- Push scope는 등록된 `source_id`, 학년, 피드, 발신처 그룹만 허용합니다. HTTPS endpoint, 본문 크기, 키 길이를 검증하고 공개 원문 페이지 외의 비공개 `保護者連絡帳` 자료는 수집하지 않습니다.
- 공개 API는 비밀키를 반환하지 않으며 `Cache-Control: no-store`, CSP, `X-Content-Type-Options`, 제한된 Referrer 정책을 사용합니다. 새 학교 등록은 코드 수정 없이 레지스트리 검증 후 추가할 수 있습니다.
- 비용이 큰 `今すぐ更新`과 브라우저 구독 등록에는 IP별 요청 제한을 두고, 다중학교 PDF 수집은 서버 내부의 고정 worker와 in-flight 중복 제거로 제한합니다. 상용 다중 레플리카 단계에서는 이 worker를 별도 수집 작업으로 분리하고 공유 PostgreSQL/queue를 연결합니다.
- 웹앱은 PWA로 먼저 제공하고, 나중에 iOS/Android 앱은 같은 `/api/config`, `/api/notices`, `/api/push` 계약과 좌표·소스 ID를 사용합니다. 네이티브 알림 토큰만 별도 어댑터로 추가하면 됩니다.

## LINE 자동화

桜野小学校の[学校／学年だよりページ](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage34/)を定期確認し、学校だより・学年だよりの新しいリンク、または既存 PDF の内容変更を検知して、指定学年に関係する日本語原文中心の通知を LINE Messaging API へ送ります。

初期対象は `1年生` です。学年はコードを書き換えずに `2年生`、`6`、`全学年` などへ変更できます。

## 動作

1. GitHub Actions が30分ごとに学校ページを取得します。
2. ページ内の学校だより・学年だよりの PDF/リンクを抽出します。
3. ETag / Last-Modified が使える場合は条件付き取得を行い、取得した文書の SHA-256 も比較します。
4. 学年だよりは指定学年の見出しから次の学年見出しの直前までだけを抽出します。学校だよりは全校共通の連絡として保持します。
5. `持ち物・準備`、`提出物・締切`、`行事・予定`、`保護者への連絡`、`学習予定` などの見出しで日本語原文を分類します。翻訳や生成による言い換えは行いません。
6. 複数の新着文書が同じ実行で見つかった場合も、LINE の Push API を1回だけ呼び、1つのテキスト通知にまとめます。

送信は次の2段階です。

`prepare` → GitHub に pending 状態をコミット → `deliver` → 送信済み状態をコミット

LINE の `X-Line-Retry-Key` は通知内容から決定的に作ります。LINE が受け付けた後に GitHub の最終コミットだけ失敗しても、次回は同じ retry key を使うため、同じ Push が二重に受け付けられません。LINE の retry key の保持期間を超えた pending は安全のため自動送信せず、Actions を失敗させます。

## GitHub 設定

### 1. LINE 側

LINE Official Account を作成し、Messaging API を有効化します。Channel access token を発行し、通知先の `LINE_TO` を準備します。通知先は LINE の表示名ではなく、Messaging API が扱う user ID または bot が参加した group ID です。

공식 안내:

- [Messaging API 시작하기](https://developers.line.biz/en/docs/messaging-api/getting-started/)
- [Push 메시지 보내기](https://developers.line.biz/en/docs/messaging-api/sending-messages/)
- [Messaging API reference](https://developers.line.biz/en/reference/messaging-api/nojs/)
- [실패 요청 재시도와 X-Line-Retry-Key](https://developers.line.biz/en/docs/messaging-api/retrying-api-request/)

### 2. Repository Secrets

Repository의 `Settings → Secrets and variables → Actions`에서 다음을 설정합니다.

| 이름 | 필수 | 내용 |
| --- | --- | --- |
| `LINE_CHANNEL_ACCESS_TOKEN` | 알림 전송 시 필수 | LINE Messaging API Channel access token |
| `LINE_TO` | 알림 전송 시 필수 | LINE user ID 또는 봇이 들어가 있는 group ID |

토큰은 소스 코드, `config.json`, 로그에 넣지 않습니다. GitHub Actions workflow가 Secret을 환경변수로 주입합니다.

`LINE_TO`는 LINE 앱에 보이는 이름이 아닙니다. Official Account에 친구 추가한 뒤 webhook event에서 받은 user ID를 사용하거나, 봇을 그룹에 초대한 뒤 webhook event에서 받은 group ID를 사용합니다. 이 프로젝트는 예약 실행용이라 inbound webhook 서버는 포함하지 않으므로, 이미 운영 중인 webhook 또는 LINE의 테스트용 수신 환경에서 ID를 확인합니다.

### 3. Repository Variable로 학년 변경

`Settings → Secrets and variables → Actions → Variables`에서 `SCHOOL_GRADE`를 설정하면 다음 예약 실행부터 적용됩니다.

예시:

```text
SCHOOL_GRADE=1年生
```

지원 예시는 다음과 같습니다.

```text
1年生
2
第6学年
全学年
```

Actions의 `Run workflow`에서 `grade`를 입력하면 Repository Variable보다 우선하여 해당 1회 실행에만 적용됩니다. 입력을 비워두면 `SCHOOL_GRADE`, 그 다음 `config.json`의 `grade`를 사용합니다.

### 4. Actions 권한

상태 파일을 repository에 커밋하므로 `Settings → Actions → General → Workflow permissions`에서 `Read and write permissions`를 허용해야 합니다. 기본 브랜치 보호 규칙이 Actions의 push를 막는 경우에는 해당 규칙에 맞는 별도 bot/PR 흐름이 필요합니다.

Workflow 파일은 [.github/workflows/school-news-line.yml](.github/workflows/school-news-line.yml)입니다. GitHub Actions의 예약 실행은 UTC 기준 cron을 사용하므로, 현재 설정 `*/30 * * * *`는 30분마다 실행됩니다.

## 첫 실행 정책

기존 문서를 처음 발견했을 때 과거 자료가 한꺼번에 전송되지 않도록 기본값은 `notify_existing_on_first_run: false`입니다. 첫 실행은 현재 링크/PDF를 상태에 기준선으로 등록하고 LINE을 보내지 않습니다. 이후 새 링크 또는 PDF 내용 변경부터 알립니다.

현재 자료도 즉시 받아보고 싶을 때는 일시적으로 다음 환경변수를 넣어 수동 dry-run 또는 실행을 할 수 있습니다.

```bash
NOTIFY_EXISTING_ON_FIRST_RUN=true python -m sakurano_line_notifier run --dry-run
```

실제 첫 알림을 만들려면 `--dry-run`을 제거하고 LINE Secrets가 설정되어 있어야 합니다. 기준선 등록 후에는 `NOTIFY_EXISTING_ON_FIRST_RUN`를 다시 `false`로 두는 것을 권장합니다.

학년을 새 값으로 변경하면 그 학년은 별도의 기준선으로 관리됩니다. 과거 자료를 그 학년으로 한 번 받아야 하는 경우에만 위 옵션을 사용합니다.

## 로컬 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# 네트워크로 페이지를 확인하지만 LINE 전송과 상태 저장은 하지 않음
python -m sakurano_line_notifier run --dry-run

# 다른 학년의 후보 확인
SCHOOL_GRADE='2年生' NOTIFY_EXISTING_ON_FIRST_RUN=true \
  python -m sakurano_line_notifier run --dry-run
```

실제 전송은 다음처럼 두 단계로 실행합니다. `prepare`가 먼저 상태를 저장하므로, 운영에서는 workflow와 같은 순서를 사용합니다.

```bash
python -m sakurano_line_notifier prepare
python -m sakurano_line_notifier deliver
```

## 상태 파일

`state/state.json`은 삭제하지 말고 repository에 커밋합니다.

- `documents`: 링크별 제목, 종류, ETag/Last-Modified, PDF 해시
- `baseline_grades`: 학년별 최초 기준선 등록 여부
- `notifications`: 기준선/전송 완료/pending 알림 이력
- `pending`: 전송 전 커밋된 메시지, notification ID, retry key

전송이 완료되면 pending 메시지는 제거되고 해시와 전송 이력만 남습니다. 링크가 페이지에서 사라져도 과거 상태를 자동 삭제하지 않으므로, 문서가 다시 올라올 때 중복을 줄일 수 있습니다.

텍스트가 아닌 이미지 스캔 PDF는 정확한 원문 추출을 위해 자동 OCR하지 않고 실행을 실패시킵니다. 해당 실행에서 상태를 진행시키지 않으므로 OCR 또는 별도 추출 규칙을 추가한 뒤 재시도할 수 있습니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

테스트는 HTML 링크 필터, 전각 숫자를 포함한 학년 섹션 추출, 항목 분류/LINE 길이 제한, 상태 원자적 저장, retry key 안정성을 확인합니다. 실제 LINE 호출은 하지 않습니다.
