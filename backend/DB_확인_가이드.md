# 📊 데이터베이스 확인 가이드

## 데이터베이스 정보

- **종류**: SQLite
- **파일명**: `aivoice_beta.db`
- **위치**: `/Users/daehanlim/AIvoicelearning/aivoice/backend/aivoice_beta.db`

## 🔍 DB 확인 방법

### 방법 1: Python 스크립트 (가장 쉬움) ⭐️ 추천

```bash
cd /Users/daehanlim/AIvoicelearning/aivoice/backend
python check_db.py
```

이 명령어로 다음을 확인할 수 있습니다:

- 최근 세션 목록 (최근 10개)
- 사전 등록자 목록
- 간단한 통계

**상세 통계 확인:**

```bash
python view_statistics.py
```

**사전 등록자 CSV 내보내기:**

```bash
python export_registrations.py
```

### 방법 2: DB Browser for SQLite (GUI) 🖥️

1. **프로그램 다운로드**

   ```bash
   # Mac (Homebrew 사용)
   brew install --cask db-browser-for-sqlite

   # 또는 직접 다운로드
   # https://sqlitebrowser.org/
   ```

2. **DB 파일 열기**

   - DB Browser 실행
   - `Open Database` 클릭
   - `aivoice_beta.db` 파일 선택

3. **테이블 확인**
   - `Browse Data` 탭에서 데이터 조회
   - `sessions`, `pre_registrations`, `activity_logs` 테이블 확인

### 방법 3: SQLite 명령어 (터미널) 💻

```bash
# 데이터베이스 접속
cd /Users/daehanlim/AIvoicelearning/aivoice/backend
sqlite3 aivoice_beta.db

# SQLite 프롬프트에서 실행할 명령어들:

# 테이블 목록 보기
.tables

# 테이블 구조 확인
.schema sessions
.schema pre_registrations
.schema activity_logs

# 세션 전체 조회
SELECT * FROM sessions;

# 완료된 세션만 조회
SELECT session_id, character_id, turn_count, is_completed
FROM sessions
WHERE is_completed = 1;

# 사전 등록자 조회
SELECT * FROM pre_registrations;

# 캐릭터별 인기도
SELECT character_id, COUNT(*) as count
FROM sessions
GROUP BY character_id
ORDER BY count DESC;

# 종료
.quit
```

### 방법 4: Python 코드로 직접 조회 🐍

```python
import sqlite3
from pathlib import Path

# DB 연결
db_path = Path("/Users/daehanlim/AIvoicelearning/aivoice/backend/aivoice_beta.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 최근 세션 5개 조회
cursor.execute("""
    SELECT session_id, character_id, turn_count, is_completed
    FROM sessions
    ORDER BY start_time DESC
    LIMIT 5
""")

for row in cursor.fetchall():
    print(dict(row))

# 연결 종료
conn.close()
```

## 📋 테이블 구조

### 1. `sessions` 테이블

```sql
session_id TEXT PRIMARY KEY          -- 고유 세션 ID
character_id TEXT NOT NULL           -- 선택한 캐릭터
start_time TIMESTAMP                 -- 시작 시간
end_time TIMESTAMP                   -- 종료 시간
turn_count INTEGER                   -- 대화 횟수 (최대 10)
is_completed BOOLEAN                 -- 완료 여부
is_blocked BOOLEAN                   -- 차단 여부 ⚠️ 중요!
conversation_history TEXT            -- 대화 내역 (JSON)
feedback_data TEXT                   -- 피드백 데이터 (JSON)
user_ip TEXT                         -- 사용자 IP
user_agent TEXT                      -- User Agent
created_at TIMESTAMP                 -- 생성 시간
```

### 2. `pre_registrations` 테이블

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
session_id TEXT                      -- 연결된 세션 ID
name TEXT NOT NULL                   -- 이름
email TEXT NOT NULL                  -- 이메일 ⭐️
phone TEXT                           -- 전화번호
notify_email BOOLEAN                 -- 이메일 알림 수신 동의
notify_sms BOOLEAN                   -- SMS 알림 수신 동의
created_at TIMESTAMP                 -- 등록 시간
```

### 3. `activity_logs` 테이블

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
session_id TEXT NOT NULL             -- 세션 ID
activity_type TEXT NOT NULL          -- 활동 유형
activity_data TEXT                   -- 활동 데이터 (JSON)
timestamp TIMESTAMP                  -- 발생 시간
```

## 🔧 유용한 SQL 쿼리

### 통계 쿼리

```sql
-- 전체 통계
SELECT
    COUNT(*) as total_sessions,
    SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN is_blocked = 1 THEN 1 ELSE 0 END) as blocked
FROM sessions;

-- 등록 전환율
SELECT
    (SELECT COUNT(*) FROM pre_registrations) * 100.0 /
    (SELECT COUNT(*) FROM sessions WHERE is_completed = 1) as conversion_rate;

-- 캐릭터별 완료율
SELECT
    character_id,
    COUNT(*) as total,
    SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as completed,
    ROUND(SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as completion_rate
FROM sessions
GROUP BY character_id;

-- 평균 대화 시간 (분 단위)
SELECT
    AVG(CAST((julianday(end_time) - julianday(start_time)) * 24 * 60 AS INTEGER)) as avg_minutes
FROM sessions
WHERE end_time IS NOT NULL;
```

### 사전 등록자 관리

```sql
-- 이메일 알림 수신 동의자만
SELECT name, email
FROM pre_registrations
WHERE notify_email = 1
ORDER BY created_at DESC;

-- 전화번호 입력한 사용자
SELECT name, email, phone
FROM pre_registrations
WHERE phone IS NOT NULL AND phone != '';

-- 세션 정보와 함께 조회
SELECT
    pr.name,
    pr.email,
    pr.created_at,
    s.character_id,
    s.turn_count
FROM pre_registrations pr
LEFT JOIN sessions s ON pr.session_id = s.session_id
ORDER BY pr.created_at DESC;
```

## 💾 백업 방법

### 자동 백업 스크립트

```bash
#!/bin/bash
# backup_db.sh

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_PATH="/Users/daehanlim/AIvoicelearning/aivoice/backend/aivoice_beta.db"
BACKUP_PATH="/Users/daehanlim/AIvoicelearning/aivoice/backend/backups"

mkdir -p $BACKUP_PATH
cp $DB_PATH "$BACKUP_PATH/aivoice_beta_$TIMESTAMP.db"

echo "✅ 백업 완료: aivoice_beta_$TIMESTAMP.db"
```

### 수동 백업

```bash
# 단순 복사
cp aivoice_beta.db aivoice_beta_backup_$(date +%Y%m%d).db

# SQLite dump
sqlite3 aivoice_beta.db .dump > backup.sql
```

## 🚨 주의사항

1. **절대 직접 수정하지 마세요!**

   - DB 파일을 직접 수정하면 데이터 손상 위험
   - Python API나 SQL을 통해서만 수정

2. **백업 필수**

   - 중요한 데이터이므로 정기적으로 백업
   - 배포 전 반드시 백업

3. **개인정보 보호**

   - 사전 등록자 이메일/전화번호 주의
   - 외부에 공유하지 않기

4. **차단된 세션 복구 불가**
   - `is_blocked = 1`인 세션은 영구 차단
   - 복구하려면 DB를 직접 수정해야 함

## 📞 문제 발생 시

DB가 손상되었거나 문제가 생긴 경우:

```bash
# DB 무결성 검사
sqlite3 aivoice_beta.db "PRAGMA integrity_check;"

# DB 복구 시도
sqlite3 aivoice_beta.db ".recover" | sqlite3 recovered.db

# 백업에서 복원
cp aivoice_beta_backup_YYYYMMDD.db aivoice_beta.db
```
