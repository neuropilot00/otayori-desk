# おたより desk — 학교 공지 집계 베타

## 현재 출시 단계: 주변 학부모 무료 테스트

현재는 무료 베타이며 결제·구독 과금·유료 자동 전환 기능은 없습니다. 사업자 표시와 결제 도입은 실제 테스트 후 별도로 검토합니다. 학교 공식 서비스나 비공개 보호자 앱의 대체재가 아닙니다. 공개 사이트이므로 링크를 받은 지인만 접속하도록 인증으로 제한된 상태는 아닙니다.

- 일본어 [이용 안내·개인정보·출처 정책](web/policies.html)을 제공합니다. 실제 운영자 정보는 임의로 만들지 않았습니다.
- 알림은 이용자가 안내에 동의하고 브라우저 권한을 허용한 때만 등록합니다. 기기별 무작위 HttpOnly 쿠키의 해시로 구독 소유권을 구분하며, 아이 이름·생년월일·가족 계정은 받지 않습니다.
- `通知・データ設定`에서 이 브라우저의 구독 해지, 설정 내보내기, 데이터 삭제를 제공합니다. 쿠키를 먼저 지우면 서버의 이전 구독을 본인 것으로 증명할 수 없습니다. 구독은 마지막 등록/갱신으로부터 180일 후 정리됩니다.
- 오류·누락은 개인 이름이나 비공개 공지를 넣지 않고 화면의 피드백 문안을 복사해 초대해 준 사람에게 전달합니다. 자동 제출하거나 외부 분석 서비스로 전송하지 않습니다.
- 최신 확인 실패 시 이전 자료와 경고를 표시합니다. 안내에 표시된 날짜와 `原文`을 확인해야 하며 긴급 연락은 학교의 공식 수단을 사용합니다.

테스트 운영·중단·복구 및 상용화 전 남은 확인은 [운영 가이드](docs/PILOT_OPERATIONS.md), 취약점 처리 기준은 [SECURITY.md](SECURITY.md)를 참조하세요. iPhone/Android의 실제 잠금화면 수신, 학교별 누락률, PostgreSQL 복구·장애전환과 법률 검토는 단위 테스트 통과와 구분합니다.

이 저장소에는 두 가지 경로가 함께 있습니다.

- `web`: 도쿄 학교 홈페이지의 공개 공지를 학교·학교급·지역별로 한 화면에서 보는 보호자용 빠른 베타
- `run` / `prepare` / `deliver`: 기존 桜野小学校 공지를 학년별로 추출해 LINE Messaging API로 중복 없이 보내는 자동화

웹 베타는 학교가 새 시스템에 가입해야 하는 서비스가 아닙니다. 공개된 학교 홈페이지의 PDF/HTML만 읽고, 일본어 원문과 공식 링크를 함께 표시합니다. 결석 연락, 비공개 학교 앱, 보호자 인증 영역은 범위에 포함하지 않습니다.

## 바쁜 보호자를 위한 첫 화면 원칙

### 2026-10-02 공개자료 범위 확장

등록 수집원은 75개이며, 무사시노 12개 초등학교의 공개 あそべえ 소식지와 학교별 보건·급식·입학·보호자 안내, 시청 식육·스포츠·학교생활 안내를 포함합니다. 학교·학동 선택에 맞는 자료만 연결하며, 행사는 이벤트 탭에 표시합니다. [전체 검증 결과와 한계](docs/COVERAGE_EXPANSION_AUDIT.md)를 참조하세요.

- 일반 링크뿐 아니라 공식 페이지에 `embed`·`object`·`iframe`으로 삽입된 PDF도 발견합니다. 다른 학년의 링크는 수집 개수 제한을 적용하기 전에 제외합니다.
- HTML 상세의 `添付資料（公式原文）`에는 허용 출처의 PDF·이미지·신청서 링크를 접어서 제공합니다. 첨부 링크 제공은 첨부 본문을 읽었다는 뜻이 아니며 화면에도 구분합니다.
- PDF 일부 페이지라도 읽지 못하면 `original_only`와 경고를 유지합니다. OCR 품질·페이지·용량 제한을 통과했다고 글자와 날짜가 완전히 정확하다는 뜻은 아닙니다.
- `related_collections`로 해당 학교의 あそべえ 소식지를 같은 학구의 학동 선택에도 연결합니다. 다른 학교 전체에 공유하지 않습니다.
- 기존 출처의 범위를 넓힐 때는 `notification_revision`을 새 값으로 올립니다. 새로 편입된 과거 자료는 첫 조회에서 조용히 기준 상태로 저장하고 기존 실패 알림의 재시도 상태는 유지합니다. 신규 출처 ID도 동일하게 과거 자료를 일괄 발송하지 않습니다.
- 월·연도는 원문 근거로만 표시하며, 특정 연도의 파일명 필터로 다음 해 자료를 막지 않습니다. 여러 회차가 나열된 행사는 첫 회차만으로 종료 처리하거나 임의로 캘린더에 넣지 않습니다.

퇴근 후 긴 목록을 다시 읽지 않아도 되도록 첫 화면은 다음 순서로 동작합니다.

- 가장 최근 월의 정보만 바로 펼쳐 보여주고, 지난 달 자료는 접힌 상태로 둡니다.
- `学校・生活`과 `イベント`를 탭으로 나눠, 오늘 준비해야 하는 공지와 지역 행사 목록을 섞지 않습니다.
- 카드 색과 라벨로 `学校`·`武蔵野市・教育委員会／市役所`·`学童`의 발신처를 구분합니다.
- `発信元` 필터로 학교·시청/교육위원회·학동을 따로 볼 수 있고, 학동은 학교 선택과 같은 흐름에서 함께 확인합니다.
- 모든 카드와 상세 화면에 `原文` 링크를 남깁니다. 요약은 판단을 돕는 화면이고, 최종 확인은 학교·시청의 공식 원문에서 하도록 합니다.
- `10月号` 같은 호수와 확인 가능한 발행·게시일을 따로 표시합니다. PDF 파일명·URL의 업로드 시각을 게시일로 표시하지 않습니다. 명시된 월호에 연도가 없으면 CMS 업로드 연도를 월호의 연도 문맥으로만 이용하며, 발행일은 미확인 상태로 둡니다. 본문에 언급된 다음 호 때문에 학교소식의 월호가 바뀌지 않습니다.

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

웹 베타는 5분 메모리 캐시와 영속 SQLite 공개자료 캐시(`WEB_CATALOG_CACHE_PATH`)를 함께 사용합니다. Railway에서는 `/data/catalog_cache.sqlite3`를 지정해 재배포 뒤에도 마지막으로 확인한 공개 공지를 먼저 보여줍니다. `collection_driver: server` 자료는 서버가 `WEB_CATALOG_REFRESH_INTERVAL_SECONDS`(기본 15분)마다 확인하며 `今すぐ更新`으로 다시 조회할 수 있습니다. `scheduled` 시청 자료는 아래 Actions 수집기가 약 30분마다 갱신하고, 버튼은 마지막 수집 결과를 읽습니다. 여러 학교 조회는 `WEB_CATALOG_MAX_WAIT_SECONDS`(기본 12초) 안에 완료된 소스부터 부분 응답하며 늦은 소스는 공유 작업으로 캐시에 반영합니다. 같은 PDF 수집을 요청마다 중복 실행하지 않습니다.

### 시청 공개자료 정기 동기화

Railway 실행 환경에서는 무사시노시 공식 도메인이 HTTP 403을 반환하지만 GitHub-hosted runner에서는 공개 페이지가 정상 응답하는 것을 확인했습니다. 인증 우회 없이, 접근 가능한 수집 환경에서 공개 자료만 읽어 웹 서버에 전달합니다.

- `.github/workflows/catalog-sync.yml`: 매시 7분·37분(UTC), 수동 실행 지원. Actions 사정으로 지연될 수 있으며 정확히 30분 간격을 보장하지 않습니다.
- GitHub Secrets: `CATALOG_SYNC_URL` = `https://otayori-web-production.up.railway.app/api/internal/catalog`, `CATALOG_SYNC_TOKEN` = 무작위 32자 이상 비밀키.
- Railway: 동일한 `CATALOG_SYNC_TOKEN`, `WEB_SCHEDULED_COLLECTION=true`, 영속 `WEB_CATALOG_CACHE_PATH` 설정. 비밀키는 클라이언트 코드·로그·저장소에 넣지 않습니다.
- 레지스트리에서 `collection_driver: scheduled`인 21개 시청 소스만 전송합니다. 출처 설정 지문·허용 HTTPS 호스트·학년·개수·최대 2MB·본문 읽기 성공·최근 확인 시각을 검사합니다. 실패한 소스는 업로드하지 않고 다른 정상 소스는 계속 처리합니다.
- 수신 API는 서버 간 Bearer 인증이 필수이고 브라우저 Origin 요청은 거부합니다. 확인 시각이 같거나 이전인 재전송은 덮어쓰지 않습니다. 디스크 저장을 확인한 뒤에만 성공 응답합니다.
- 마지막 확인 후 90분 이상이면 지연 경고와 실제 확인 시각을 유지합니다. 최초 자료가 없으면 ‘자료 대기’ 경고를 표시합니다. 과거 캐시를 방금 수집한 정보처럼 표시하지 않습니다.
- 수집 토큰은 공개 공지 캐시 쓰기에만 사용하며 학부모 쿠키·알림 구독 DB를 읽거나 수정하지 않습니다. 키 교체 시 양쪽 Secrets를 함께 교체하고 Railway를 재배포합니다.

#### 예약 지연 복구 감시 (선택 설정)

GitHub 예약은 실행 시각을 보장하지 않으며 실제로 수 시간 지연된 사례가 있습니다. [GitHub 공식 안내](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows)를 참고하세요. Railway의 백그라운드 갱신 루프에는 저장된 시청 자료가 45분 이상 오래되거나 없을 때 동일한 수집 workflow를 수동 이벤트로 요청하는 감시 기능이 있습니다. **아래 최소 권한 토큰을 등록해야 활성화되며, 미설정 상태에서는 기존 GitHub 예약만 동작합니다.**

1. GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens에서 만료일을 지정하고 `otayori-desk` 저장소 **하나만** 선택합니다.
2. Repository permissions의 **Actions: Read and write**만 추가합니다(Metadata read는 기본 권한). Contents write, 계정 전체 repo 권한은 주지 않습니다. [워크플로 실행 권한](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
3. 토큰은 채팅·파일·명령행에 붙이지 말고 Railway `otayori-web`의 Variables에 `CATALOG_DISPATCH_TOKEN`으로 직접 등록하고 재배포합니다. 기존 `CATALOG_SYNC_TOKEN`과 서로 다른 토큰입니다.
4. **단일 웹 인스턴스에서만** 활성화합니다. 성공·실패 모두 최소 30분 간격, 인증 실패는 6시간 간격으로 제한하고 고정 GitHub API 주소로만 보냅니다. 리다이렉트·환경 프록시는 사용하지 않으며 토큰/응답 본문은 로그에 남기지 않습니다.
5. 실행 요청 성공은 수집 완료가 아닙니다. 검증된 스냅샷이 실제 저장된 경우에만 확인 시각이 바뀝니다. 배포 후 workflow 실행 기록, 21개 출처의 `checked_at`, `freshness_status`를 확인합니다. GitHub 자체 장애나 큐 지연까지 제거하는 기능은 아닙니다.

화면에서는 `freshness_status`와 `issue_codes`로 갱신 지연·본문 판독 실패·조회 실패를 구분합니다. 긴 출처별 설명은 접힌 `収集範囲・確認状況` 안에 표시하며, 과거 자료 건수 한도만 도달한 경우는 오류 경고가 아닙니다. 실제 판독 실패와 원문 링크는 숨기지 않습니다.

### 브라우저 알림과 앱 전환

`通知を受け取る` 버튼은 PWA Service Worker와 Web Push를 사용합니다. 안내 동의 후 브라우저 권한을 허용하면 선택한 학교·학년·피드·발신처 조건이 서버에 저장됩니다. 수신자별 전송 수락 기록을 DB에 남겨 성공한 구독자에게 반복 발송하지 않고, 일부 소스 실패나 초기 등록 때는 과거 자료를 일괄 발송하지 않습니다. 다만 공급자가 전송을 수락한 직후 프로세스가 중단되는 경우 중복 가능성이 남으므로 exactly-once 또는 실제 단말 수신을 보장하지 않습니다. 잠금화면에는 학교·학년·공지 제목을 노출하지 않습니다. 앱 전환 시 `scope` 계약은 재사용하되 별도 사용자 인증·네이티브 토큰 보안 검증이 필요합니다.

학동 12곳의 시설 안내는 실제 공식 페이지를 확인하는 참고자료로 분리하며 새 공지 건수·알림에서 제외합니다. 별도로 시의 학동 입회·제도 공지 목록에서 새 링크를 자동 탐색합니다. 시설별 비공개 연락장은 수집하지 않습니다. 공식 시설 페이지와 최신 시청 종합 안내의 주소·전화가 다를 수 있으므로 이전·운영 정보는 최신 공식 종합 안내도 확인해야 합니다.

### 수집 범위와 원문 검증

`mixed`는 등록 페이지의 HTML 본문과 PDF를 함께 읽고, `link_index`는 검토된 `link_patterns`에 맞는 새 기사 링크를 찾습니다. 탐색은 등록 도메인·명시적 `allowed_hosts`와 제한된 깊이 안에서만 수행합니다. `shared_with_ward`인 시 공지는 같은 시의 학교·학동 선택에 함께 표시합니다. 학교별 실제 범위·원문·제한은 [SOURCE_COVERAGE.md](docs/SOURCE_COVERAGE.md)에 기록했습니다.

- API `coverage`는 출처별 확인 시각·실패·발견 수·건수 제한을 반환합니다. `complete`는 이번에 선택한 등록 소스의 수집 오류 여부이며, 학교의 모든 공지를 수집했다는 뜻이 아닙니다.
- 개최일·신청 마감일·게시일·대상 월을 분리합니다. 게시일을 확인하지 못한 자료는 임의의 행사 날짜를 게시일로 쓰지 않습니다. 날짜 미확인 자료와 앞으로의 행사도 과거 자료 속에 숨기지 않습니다.
- 읽지 못한 PDF도 발견한 원문 링크를 유지하되 `original_only`로 표시하고 부분 수집 경고를 남깁니다. 실패를 정상으로 처리하거나 내용을 만들어 채우지 않습니다.
- 재시작 뒤에도 원문을 바로 열 수 있도록 원문 링크·실패 경고·본문 판독 상태·오래된 본문 여부를 공개자료 캐시에 함께 보존합니다. 이는 OCR 성공 캐시나 알림 발송 성공 기록이 아닙니다. 시작 시 기본 학교와 관련 학동 자료를 다른 학교의 PDF보다 먼저 조회하며, 경고가 있는 소스는 여전히 알림 기준선으로 쓰지 않습니다.
- `coverage_kind: reference`는 시설 참고자료입니다. 신규 수집처의 기존 자료는 조용히 기준선만 저장하며, 기록 형식 이전 시에도 이미 대기 중이던 미전송 알림은 보존합니다. 실패한 출처는 알림 기준선을 갱신하지 않고 정상 출처의 알림과 분리합니다.

등록 소스의 실제 수집을 알림 발송 없이 점검할 수 있습니다:

```bash
python -m sakurano_line_notifier.source_audit
python -m sakurano_line_notifier.source_audit --only sakurano --only musashino_dai4_es --output state/source-audit.json
```

실패·0건은 종료 코드 1로 표시됩니다. GitHub Actions `Public source coverage`도 매일 일본시간 06:23에 실행하며 별도 Secrets는 필요 없습니다. 이 검사는 공개 목록의 링크·본문 읽기를 확인할 뿐, 비공개 연락이나 전체 자료의 의미상 정확성을 보증하지 않습니다.

Railway에서는 `WEB_PUSH_DATABASE_PATH`를 영속 볼륨 경로로 지정하면 SQLite DB에 구독과 전송 상태가 저장되어 재배포 뒤에도 유지됩니다. 베타는 단일 인스턴스로 운영합니다. PostgreSQL 어댑터와 스캐너 잠금은 마련되어 있으나 실제 DB 이관·부하·장애전환 검증 전에는 URL 설정만으로 다중 인스턴스 운영이 검증됐다고 보지 않습니다. `WEB_PUSH_STATE_PATH`는 로컬 호환용 JSON fallback입니다. `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY`, `WEB_PUSH_CONTACT`를 설정하지 않으면 발송이 불가능합니다. 기존 소유권·동의 기록이 없는 구독은 재동의할 때까지 발송하지 않습니다.

필수 운영 변수:

| 이름 | 내용 |
| --- | --- |
| `WEB_PUBLIC_ORIGIN` | 실제 HTTPS 공개 주소. 예: `https://otayori-web-production.up.railway.app`. POST 출처 검증·Secure 쿠키에 사용 |
| `WEB_PUSH_PUBLIC_KEY` | VAPID 공개키 |
| `WEB_PUSH_PRIVATE_KEY` | VAPID 개인키. 저장소에 커밋하지 않음 |
| `WEB_PUSH_CONTACT` | VAPID 주체의 실제 `mailto:` 또는 HTTPS 연락 경로. 가짜 이메일 사용 금지 |
| `WEB_PUSH_DATABASE_PATH` | 단일 인스턴스용 SQLite 예: `/data/push_subscriptions.sqlite3` |
| `WEB_PUSH_DATABASE_URL` | PostgreSQL 어댑터 연결 URL. 비밀값으로만 설정; 실제 이관 검증 별도 |
| `WEB_PUSH_STATE_PATH` | JSON fallback 예: `state/push_subscriptions.json` |
| `WEB_PUSH_SCAN_INTERVAL_SECONDS` | 새 소식 확인 주기. 기본 900초 |
| `WEB_CATALOG_REFRESH_INTERVAL_SECONDS` | 백그라운드 공개 소스 갱신 주기. 기본 900초 |
| `WEB_CATALOG_MAX_WAIT_SECONDS` | 한 API 응답이 기다리는 최대 소스 확인 시간. 기본 12초 |
| `WEB_CATALOG_CACHE_PATH` | 공개 공지 캐시 SQLite 경로. Railway 예: `/data/catalog_cache.sqlite3` |

### 장기 확장과 보안 경계

- `sources.json`은 코드에서 분리된 검토 가능한 공개 소스 레지스트리입니다. 학교·학동·시청 그룹, 학교급, 지역, 좌표, 공식 원문 링크를 같은 계약으로 저장하므로 모바일 앱이 HTML을 직접 긁지 않고 API를 사용할 수 있습니다.
- 보호자별로 변하는 구독과 중복 발송 기준선은 DB에만 저장합니다. 구독 endpoint·키는 SQLite 파일 권한을 제한하고, PostgreSQL 전환 시에도 파라미터 바인딩으로만 저장합니다.
- Push scope는 등록된 `source_id`, 학년, 피드, 발신처 그룹만 허용합니다. 승인된 브라우저 푸시 제공자만 대상으로 하며 HTTPS URL·P-256 공개키·인증키 길이를 검증합니다. 임의 URL 및 리다이렉트로 내부 네트워크에 접근하지 못하도록 제한합니다. 비공개 `保護者連絡帳` 자료는 수집하지 않습니다.
- 공개 API는 비밀키를 반환하지 않으며 `Cache-Control: no-store`, CSP, `X-Content-Type-Options`, 제한된 Referrer 정책을 사용합니다. 새 학교 등록은 코드 수정 없이 레지스트리 검증 후 추가할 수 있습니다.
- 비용이 큰 갱신과 구독 등록에는 IP별 및 전체 요청 제한을 두고, HTTP 연결 수·본문 크기·읽기 시간·수집 worker를 제한합니다. 임의 쿠키로 요청 제한을 초기화할 수 없고 프록시의 임의 전달 헤더도 신뢰하지 않습니다. 프록시/NAT 환경에서는 이용자가 IP 제한을 공유할 수 있습니다. 갱신은 동일 출처 JSON POST만 허용하고 GET `refresh=true` 우회는 차단합니다. 상용 다중 레플리카 단계에는 검증된 edge 요청 제한·별도 수집 작업·queue가 필요합니다.
- 웹앱은 PWA로 먼저 제공하고, 나중에 iOS/Android 앱은 같은 `/api/config`, `/api/notices`, `/api/push` 계약과 좌표·소스 ID를 사용합니다. 네이티브 알림 토큰만 별도 어댑터로 추가하면 됩니다.

## LINE 자동화

桜野小学校の[学校／学年だよりページ](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage34/)を定期確認し、学校だより・学年だよりの新しいリンク、または既存 PDF の内容変更を検知して、指定学年に関係する日本語原文中心の通知を LINE Messaging API へ送ります。

初期対象は `1年生` です。学年はコードを書き換えずに `2年生`、`6`、`全学年` などへ変更できます。

## 動作

1. LINE設定を有効にした場合、GitHub Actions の30分間隔の予約で学校ページを取得します（GitHub側の実行遅延はあり得ます）。
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

`Settings → Secrets and variables → Actions → Variables`에서 `SCHOOL_GRADE`를 설정하면 다음 예약 실행부터 적용됩니다. LINE을 실제 사용할 때만 두 LINE Secrets를 먼저 등록하고 Repository Variable `LINE_NOTIFICATIONS_ENABLED=true`를 설정합니다. 미설정 상태에서는 예약 LINE 작업을 건너뛰며 웹앱 알림에는 영향이 없습니다. 수동 `dry_run`은 기본 true이고 LINE 토큰 없이 사용할 수 있습니다. PDF 판독 실패는 미리보기에서도 실패로 보고하며 전송하지 않습니다.

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

이미지 스캔 PDF는 서버 내부의 Poppler·Tesseract 일본어 OCR로 읽습니다. Railway의 실제 빌더인 Railpack에 맞춰 `railpack.json`의 `deploy.aptPackages`로 `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-jpn`을 런타임에 설치합니다([공식 설정](https://railpack.com/guides/installing-packages/)). 배포 후 `tesseract --list-langs`에 `jpn`이 있는지와 실제 PDF 수집을 확인합니다. 외부 번역/OCR 서비스로 문서를 전송하지 않습니다. OCR은 페이지·이미지·CPU·시간 제한과 품질 검사를 적용하며, 지원 한계나 낮은 인식 품질은 실패로 남깁니다. OCR도 오독할 수 있으므로 날짜·준비물·금액은 원문 링크를 확인해야 합니다. 로컬 환경에서 일본어 언어팩이 없으면 경고가 표시되며 성공으로 가장하지 않습니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

테스트는 HTML 링크 필터, 전각 숫자를 포함한 학년 섹션 추출, 항목 분류/LINE 길이 제한, 상태 원자적 저장, retry key 안정성을 확인합니다. 실제 LINE 호출은 하지 않습니다.
