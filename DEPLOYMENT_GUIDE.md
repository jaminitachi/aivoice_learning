# 🚀 Vercel 배포 가이드

## 📋 배포 전 체크리스트

### ✅ 완료된 작업

- [x] WebSocket URL 환경 변수화
- [x] API URL 환경 변수화
- [x] 백엔드 CORS 동적 설정
- [x] Fingerprint 기반 차단 시스템

---

## 1️⃣ 백엔드 배포 (FastAPI)

### 옵션 A: Railway (추천 ✨)

**장점:** 무료, 쉬움, PostgreSQL 지원, WebSocket 지원

1. **Railway 가입**

   ```bash
   # https://railway.app 접속 후 GitHub 로그인
   ```

2. **프로젝트 생성**

   - `New Project` → `Deploy from GitHub repo`
   - `aivoice/backend` 폴더 선택

3. **환경 변수 설정**

   ```
   ALLOWED_ORIGINS=https://your-frontend.vercel.app
   OPENAI_API_KEY=your_openai_key
   ELEVENLABS_API_KEY=your_elevenlabs_key
   ```

4. **배포 URL 복사**
   - 예: `https://aivoice-backend.up.railway.app`

### 옵션 B: Render

1. **Render 가입**

   ```bash
   # https://render.com 접속
   ```

2. **Web Service 생성**

   - Root Directory: `aivoice/backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **환경 변수 설정** (위와 동일)

### 옵션 C: 본인 컴퓨터 (개발/테스트용)

**ngrok 사용:**

```bash
# 1. ngrok 설치 (Mac)
brew install ngrok

# 2. 백엔드 실행
cd aivoice/backend
uvicorn main:app --host 0.0.0.0 --port 8000

# 3. 다른 터미널에서
ngrok http 8000

# 4. ngrok URL 복사 (예: https://abc123.ngrok.io)
```

**⚠️ 주의:** ngrok 무료 버전은 8시간마다 URL이 바뀝니다!

---

## 2️⃣ 프론트엔드 배포 (Vercel)

### Step 1: Vercel 프로젝트 생성

```bash
# Vercel CLI 설치 (선택)
npm i -g vercel

# 또는 웹에서 직접 배포
# https://vercel.com
```

### Step 2: 환경 변수 설정

**Vercel Dashboard → Settings → Environment Variables**

```bash
# 백엔드 URL (Railway/Render에서 복사한 URL)
NEXT_PUBLIC_API_URL=https://your-backend.railway.app

# WebSocket URL (선택, 자동 변환됨)
NEXT_PUBLIC_WS_URL=wss://your-backend.railway.app
```

### Step 3: 배포

**방법 1: Vercel Dashboard**

1. `Import Project` 클릭
2. GitHub repo 선택
3. Root Directory: `aivoice/frontend`
4. Deploy 클릭

**방법 2: CLI**

```bash
cd aivoice/frontend
vercel --prod
```

### Step 4: 백엔드 CORS 업데이트

배포 후 Vercel URL을 백엔드 환경 변수에 추가:

**Railway/Render Dashboard → Environment Variables**

```bash
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
```

---

## 3️⃣ 데이터베이스 마이그레이션 (중요!)

### 현재 문제

- SQLite는 로컬 파일 DB → 배포 시 매번 초기화됨
- 영구 저장 필요 시 **PostgreSQL** 또는 **MongoDB** 필요

### 해결 방법

#### 옵션 A: PostgreSQL로 마이그레이션 (추천)

**Railway에서 PostgreSQL 추가:**

1. Railway 프로젝트 → `New` → `Database` → `PostgreSQL`
2. 연결 URL 복사 (예: `postgresql://user:pass@host:5432/db`)
3. 백엔드 코드 수정 필요 (SQLAlchemy 사용)

#### 옵션 B: SQLite 유지 (임시 데이터만)

현재 상태 유지. 단, 배포 시마다 데이터 초기화됨.

#### 옵션 C: Supabase (무료 PostgreSQL)

1. https://supabase.com 가입
2. 프로젝트 생성 → DB URL 복사
3. 백엔드 환경 변수에 추가

---

## 4️⃣ 최종 테스트

### 체크리스트

```bash
✅ 프론트엔드 접속: https://your-app.vercel.app
✅ 캐릭터 목록 로딩 확인
✅ 캐릭터 클릭 → 차단 체크 작동
✅ WebSocket 연결 성공 (개발자 도구 → Network → WS)
✅ 음성 녹음 및 AI 응답 확인
✅ 10턴 제한 작동
✅ 피드백 페이지 이동
✅ 사전 등록 작동
```

### 디버깅

**프론트엔드 에러:**

```bash
# 개발자 도구 → Console
# CORS 에러 → 백엔드 ALLOWED_ORIGINS 확인
# WebSocket 에러 → WS URL 확인 (wss:// 사용해야 함)
```

**백엔드 에러:**

```bash
# Railway/Render Logs 확인
railway logs
# 또는
render logs
```

---

## 5️⃣ 배포 후 설정

### A. 커스텀 도메인 (선택)

**Vercel:**

1. Settings → Domains
2. 도메인 추가 (예: aivoice.com)
3. DNS 설정 (A 레코드 추가)

**Railway:**

1. Settings → Domains
2. Custom Domain 추가

### B. 환경 변수 최종 확인

**프론트엔드 (.env.production):**

```bash
NEXT_PUBLIC_API_URL=https://aivoice-api.railway.app
NEXT_PUBLIC_WS_URL=wss://aivoice-api.railway.app
```

**백엔드 (.env):**

```bash
ALLOWED_ORIGINS=https://aivoice.vercel.app,http://localhost:3000
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

### C. 보안 체크

```bash
✅ API 키 노출 확인 (GitHub에 .env 업로드 금지!)
✅ CORS 설정 확인 (필요한 도메인만 허용)
✅ 개인정보 보호 (DB 백업)
```

---

## 🚨 자주 발생하는 문제

### 1. CORS 에러

```
Access to fetch at 'https://backend.railway.app' from origin
'https://frontend.vercel.app' has been blocked by CORS policy
```

**해결:**

```bash
# 백엔드 환경 변수에 Vercel URL 추가
ALLOWED_ORIGINS=https://frontend.vercel.app
```

### 2. WebSocket 연결 실패

```
WebSocket connection to 'ws://backend.railway.app' failed
```

**해결:**

```bash
# https 백엔드는 wss:// 사용
NEXT_PUBLIC_WS_URL=wss://backend.railway.app
```

### 3. 환경 변수 적용 안됨

```
Still using localhost:8000
```

**해결:**

```bash
# Vercel 재배포
vercel --prod --force

# 또는 Dashboard에서 Redeploy
```

### 4. DB 데이터 사라짐

```
Sessions not found
```

**해결:**

- PostgreSQL로 마이그레이션 필요
- 또는 Railway Volume 사용

---

## 📊 모니터링

### Vercel Analytics

```bash
# package.json에 추가
npm install @vercel/analytics

# layout.tsx에 추가
import { Analytics } from '@vercel/analytics/react';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

### 로그 확인

```bash
# Railway
railway logs --tail

# Render
render logs --tail

# Vercel
vercel logs
```

---

## ✅ 배포 완료 후 해야 할 일

1. **사전 등록자 관리**

   ```bash
   # DB 백업
   python export_registrations.py
   ```

2. **정기 백업 설정**

   ```bash
   # Cron job 설정
   0 0 * * * python backup_db.py
   ```

3. **성능 모니터링**

   - Vercel Analytics
   - Railway Metrics

4. **사용자 피드백 수집**
   - Google Analytics
   - Hotjar

---

## 🆘 도움이 필요하면?

- **Vercel 문서:** https://vercel.com/docs
- **Railway 문서:** https://docs.railway.app
- **FastAPI 배포:** https://fastapi.tiangolo.com/deployment/

---

## 🎉 축하합니다!

배포가 완료되었습니다! 🚀

**다음 단계:**

- [ ] 테스트 유저 초대
- [ ] 피드백 수집
- [ ] 기능 개선
- [ ] 정식 출시!
