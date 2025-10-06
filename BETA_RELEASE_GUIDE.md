# 베타 릴리스 가이드 - 인스타그램 광고용 제한 버전

## 🎯 개요

이 프로젝트는 인스타그램 광고를 통해 접속한 사용자들에게 **10번의 대화 체험**을 제공하고, 피드백 후 **사전 등록**을 유도하는 시스템입니다.

## 🚀 주요 기능

### 1. **10번 대화 제한**

- 각 세션마다 정확히 10번의 대화만 가능
- 10번 대화 완료 시 자동으로 세션 종료
- 피드백 페이지로 자동 리디렉션

### 2. **세션 추적 및 차단**

- SQLite 데이터베이스에 모든 세션 기록
- 완료된 세션은 `is_blocked` 플래그로 차단
- 재접속 시 추가 대화 불가능

### 3. **사전 등록 시스템**

- 피드백 완료 후 사전 등록 페이지로 이동
- 이름, 이메일, 전화번호(선택) 수집
- 이메일/SMS 알림 수신 동의 옵션
- 로컬 DB에 영구 저장

### 4. **통계 및 관리자 대시보드**

- 전체 세션 통계 조회 가능
- 사전 등록자 목록 확인
- 캐릭터별 인기도 분석

## 📦 데이터베이스 구조

### `sessions` 테이블

```sql
session_id TEXT PRIMARY KEY          -- 고유 세션 ID
character_id TEXT NOT NULL           -- 선택한 캐릭터
start_time TIMESTAMP                 -- 시작 시간
end_time TIMESTAMP                   -- 종료 시간
turn_count INTEGER                   -- 대화 횟수 (최대 10)
is_completed BOOLEAN                 -- 완료 여부
is_blocked BOOLEAN                   -- 차단 여부 (피드백 후 True)
conversation_history TEXT            -- 대화 내역 (JSON)
feedback_data TEXT                   -- 피드백 데이터 (JSON)
user_ip TEXT                         -- 사용자 IP (선택)
user_agent TEXT                      -- User Agent (선택)
created_at TIMESTAMP                 -- 생성 시간
```

### `pre_registrations` 테이블

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
session_id TEXT                      -- 연결된 세션 ID
name TEXT NOT NULL                   -- 이름
email TEXT NOT NULL                  -- 이메일
phone TEXT                           -- 전화번호 (선택)
notify_email BOOLEAN                 -- 이메일 알림 수신 동의
notify_sms BOOLEAN                   -- SMS 알림 수신 동의
created_at TIMESTAMP                 -- 등록 시간
```

### `activity_logs` 테이블

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
session_id TEXT NOT NULL             -- 세션 ID
activity_type TEXT NOT NULL          -- 활동 유형 (start, turn, complete, pre_registration 등)
activity_data TEXT                   -- 활동 데이터 (JSON)
timestamp TIMESTAMP                  -- 발생 시간
```

## 🔧 설치 및 실행

### 백엔드 (FastAPI)

1. **가상 환경 생성 및 활성화**

```bash
cd /Users/daehanlim/AIvoicelearning/aivoice/backend
python -m venv venv
source venv/bin/activate  # Mac/Linux
# 또는
venv\Scripts\activate  # Windows
```

2. **필요한 패키지 설치**

```bash
pip install -r requirements.txt
```

3. **환경 변수 설정 (.env 파일)**

```env
OPENAI_API_KEY=your_openai_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
```

4. **서버 실행**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

데이터베이스는 서버 시작 시 자동으로 생성됩니다 (`aivoice_beta.db`).

### 프론트엔드 (Next.js)

1. **패키지 설치**

```bash
cd /Users/daehanlim/AIvoicelearning/aivoice/frontend
npm install
```

2. **개발 서버 실행**

```bash
npm run dev
```

3. **브라우저에서 접속**

```
http://localhost:3000
```

## 📊 API 엔드포인트

### 기존 엔드포인트

- `GET /api/characters` - 캐릭터 목록 조회
- `POST /api/chat` - 일반 채팅 (HTTP)
- `WS /ws/chat/{character_id}` - WebSocket 기반 실시간 대화
- `GET /api/feedback/{session_id}` - 피드백 조회

### 새로운 엔드포인트

- `POST /api/pre-registration` - 사전 등록 정보 저장
- `GET /api/statistics` - 통계 조회 (관리자용)

## 🎨 사용자 플로우

1. **홈 페이지 접속** (`/`)

   - 캐릭터 목록 보기
   - 원하는 캐릭터 선택

2. **대화 시작** (`/conversation-ws/[characterId]`)

   - WebSocket 연결
   - 초기 인사말 자동 재생
   - 음성으로 대화 진행

3. **10번 대화 완료**

   - 자동으로 세션 종료
   - 데이터베이스에 완료 기록 및 차단
   - 피드백 페이지로 리디렉션

4. **피드백 페이지** (`/feedback/[sessionId]`)

   - 대화 세션 정보 표시
   - 문법 및 유창성 점수
   - 문장별 피드백
   - **"정식 오픈 알림 받기"** 버튼

5. **사전 등록 페이지** (`/pre-registration/[sessionId]`)

   - 이름, 이메일 입력 (필수)
   - 전화번호 입력 (선택)
   - 알림 수신 동의
   - 정보 제출 → 데이터베이스 저장

6. **등록 완료**
   - 성공 메시지 표시
   - 3초 후 홈으로 자동 이동

## 🔒 보안 및 제한 메커니즘

### 1. **세션 차단 로직**

```python
# main.py - WebSocket 메시지 수신 시 매번 확인
if db.is_session_blocked(session.session_id):
    await websocket.send_json({
        "type": "error",
        "message": "이 세션은 이미 완료되었습니다. 더 이상 대화할 수 없습니다."
    })
    await websocket.close()
    break
```

### 2. **10번 제한 강제**

```python
MAX_TURNS = 10  # main.py Line 315

# 10번째 대화 후 자동 완료
if session.turn_count >= MAX_TURNS:
    session.complete_session()
    db.complete_session(
        session_id=session.session_id,
        conversation_history=session.conversation_history,
        feedback_data={...}
    )
```

### 3. **사전 등록 검증**

- 세션 존재 여부 확인
- 세션 완료 여부 확인
- 중복 등록 방지 가능 (필요 시 추가 구현)

## 📈 통계 확인

### 관리자용 통계 API

```bash
curl http://localhost:8000/api/statistics
```

**응답 예시:**

```json
{
  "statistics": {
    "total_sessions": 150,
    "completed_sessions": 145,
    "completion_rate": 96.67,
    "total_registrations": 120,
    "character_stats": {
      "elena": 45,
      "jeongsu": 30,
      "Hyemi": 35,
      ...
    }
  },
  "total_pre_registrations": 120,
  "recent_registrations": [
    {
      "id": 1,
      "session_id": "abc-123",
      "name": "홍길동",
      "email": "hong@example.com",
      "phone": "010-1234-5678",
      "notify_email": true,
      "created_at": "2025-10-06T12:34:56"
    },
    ...
  ]
}
```

## 💾 데이터베이스 백업

```bash
# 데이터베이스 파일 위치
/Users/daehanlim/AIvoicelearning/aivoice/backend/aivoice_beta.db

# 백업 명령
cp aivoice_beta.db aivoice_beta_backup_$(date +%Y%m%d).db
```

## 🚀 배포 시 체크리스트

- [ ] 환경 변수 (.env) 설정 확인
- [ ] MAX_TURNS = 10 확인
- [ ] CORS 설정 (프로덕션 도메인 추가)
- [ ] 데이터베이스 자동 백업 설정
- [ ] 통계 대시보드 접근 권한 설정
- [ ] 에러 로깅 및 모니터링 설정
- [ ] SSL/HTTPS 설정
- [ ] 사전 등록자 이메일 수집 확인

## 📧 사전 등록자 연락하기

사전 등록자 목록은 `pre_registrations` 테이블에 저장됩니다.

### CSV로 내보내기 (Python 스크립트 예시)

```python
import sqlite3
import csv

conn = sqlite3.connect('aivoice_beta.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT name, email, phone, notify_email, notify_sms, created_at
    FROM pre_registrations
    WHERE notify_email = 1
    ORDER BY created_at DESC
""")

with open('pre_registrations.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['이름', '이메일', '전화번호', '이메일알림', 'SMS알림', '등록일시'])
    writer.writerows(cursor.fetchall())

conn.close()
print("✅ 사전 등록자 목록이 pre_registrations.csv로 저장되었습니다!")
```

## 🎯 인스타그램 광고 링크 예시

```
https://yourdomain.com/?utm_source=instagram&utm_medium=ad&utm_campaign=beta_launch
```

프론트엔드에서 UTM 파라미터를 읽어 데이터베이스에 저장할 수 있습니다 (필요 시 추가 구현).

## 📝 추가 구현 아이디어

1. **쿠키/로컬스토리지 기반 제한**

   - 같은 브라우저에서 여러 세션 방지
   - 세션 ID를 쿠키에 저장

2. **IP 기반 제한**

   - 같은 IP에서 일정 횟수 이상 접속 방지
   - VPN 우회 고려

3. **이메일 인증**

   - 사전 등록 시 이메일 인증 링크 발송
   - 봇 방지

4. **관리자 대시보드**

   - 실시간 통계 시각화
   - 사전 등록자 관리
   - 세션 모니터링

5. **A/B 테스팅**
   - 다양한 MAX_TURNS 값 테스트 (5, 10, 15)
   - 사전 등록 전환율 측정

## 📞 문의

추가 기능이나 문제 발생 시 개발자에게 문의하세요.

---

**✨ 베타 테스트를 통해 수집된 데이터를 바탕으로 정식 서비스를 준비하세요!**
