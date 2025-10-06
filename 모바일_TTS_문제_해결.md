# 모바일 TTS 문제 해결 가이드

## 🔍 문제 상황

모바일 웹페이지에서 TTS(Text-to-Speech) 음성이 잘 나오다가 어느 순간부터 갑자기 작동하지 않는 현상이 발생했습니다. 이로 인해 대화 완료 후 피드백 페이지로 이동하는 로직도 제대로 작동하지 않았습니다.

## 🎯 주요 원인

### 1. **AudioContext Suspend 문제** ⚠️

모바일 브라우저(특히 iOS Safari)는 다음 상황에서 AudioContext를 자동으로 중단(`suspended` 상태)합니다:

- 📱 화면이 꺼질 때
- 🔄 앱이 백그라운드로 전환될 때
- ⏰ 일정 시간 비활성 상태일 때

기존 코드는 AudioContext가 `suspended` 상태인지 확인하지 않고 재생을 시도했습니다.

### 2. **모바일 자동재생 정책 위반** 🚫

모바일 브라우저는 사용자 상호작용(터치, 클릭 등) 없이는 오디오를 재생할 수 없습니다.

- 초기 메시지 TTS가 WebSocket 연결 후 자동으로 재생되어 차단됨
- AudioContext 생성만으로는 충분하지 않고, 사용자 제스처가 필요함

### 3. **에러 처리 미흡** ❌

TTS 재생이 실패하면 `source.onended` 콜백이 호출되지 않아:

- 세션 완료 모달이 표시되지 않음
- 피드백 페이지로 이동하지 못함

### 4. **메모리 제한** 💾

모바일 기기는 메모리가 제한적이어서 장시간 세션 후 AudioContext가 실패할 수 있습니다.

## ✅ 구현된 해결책

### 1. **AudioContext 상태 관리 강화**

```typescript
const ensureAudioContext = async () => {
  if (!audioContextRef.current) {
    // 모바일 호환성을 위해 webkitAudioContext도 지원
    const AudioContextClass =
      window.AudioContext || (window as any).webkitAudioContext;
    audioContextRef.current = new AudioContextClass();
    console.log("🎵 AudioContext 생성됨");
  }

  // AudioContext가 suspended 상태인 경우 재개 (모바일에서 중요!)
  if (audioContextRef.current.state === "suspended") {
    try {
      await audioContextRef.current.resume();
      console.log("🎵 AudioContext 재개됨 (suspended → running)");
    } catch (error) {
      console.error("❌ AudioContext 재개 실패:", error);
      throw error;
    }
  }

  return audioContextRef.current;
};
```

**핵심 개선사항:**

- ✅ AudioContext 상태를 재생 전에 항상 확인
- ✅ `suspended` 상태면 자동으로 `resume()` 호출
- ✅ 웹킷 기반 브라우저 지원

### 2. **사용자 제스처로 오디오 초기화**

```typescript
const startRecording = async () => {
  // 🎵 사용자 제스처로 AudioContext 초기화 (모바일 자동재생 정책 대응)
  if (!audioInitialized) {
    try {
      await ensureAudioContext();
      setAudioInitialized(true);
      console.log("✅ 사용자 제스처로 AudioContext 초기화됨");
    } catch (error) {
      console.warn("⚠️ AudioContext 초기화 실패 (계속 진행):", error);
    }
  }

  // ... 녹음 시작 로직
};
```

**핵심 개선사항:**

- ✅ 녹음 버튼 클릭 시 AudioContext 초기화 (사용자 제스처)
- ✅ 초기화 상태를 state로 관리하여 UI 업데이트
- ✅ 초기화 실패해도 녹음은 계속 진행

### 3. **페이지 가시성 변경 감지**

```typescript
useEffect(() => {
  const handleVisibilityChange = async () => {
    if (!document.hidden && audioContextRef.current) {
      // 사용자가 페이지로 돌아왔을 때 AudioContext 재개
      if (audioContextRef.current.state === "suspended") {
        try {
          await audioContextRef.current.resume();
          console.log("🎵 페이지 복귀 - AudioContext 재개됨");
        } catch (error) {
          console.error("❌ AudioContext 재개 실패:", error);
        }
      }
    }
  };

  document.addEventListener("visibilitychange", handleVisibilityChange);

  return () => {
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  };
}, []);
```

**핵심 개선사항:**

- ✅ 사용자가 다른 탭/앱에서 돌아왔을 때 자동 재개
- ✅ 화면이 꺼졌다 켜졌을 때 오디오 복구
- ✅ 백그라운드 전환 후에도 정상 작동

### 4. **강력한 에러 처리 및 Fallback**

```typescript
const playAudioStream = async () => {
  // 🔔 TTS 타임아웃 설정 (30초)
  audioTimeoutRef.current = setTimeout(() => {
    console.warn("⏰ TTS 재생 타임아웃 (30초)");
    isPlayingRef.current = false;

    if (isSessionCompletedRef.current) {
      console.log("✅ 세션 완료! 모달 표시 (타임아웃)");
      setShowCompletionModal(true);
    }
  }, 30000);

  try {
    // ... 재생 로직
  } catch (error) {
    console.error("❌ 오디오 재생 오류:", error);

    // 재생 실패해도 세션 완료 시 모달 표시 (중요!)
    if (isSessionCompletedRef.current) {
      console.log("✅ 세션 완료! 모달 표시 (재생 오류 발생)");
      setShowCompletionModal(true);
    }

    // 사용자에게 알림
    alert("음성 재생에 실패했습니다. 화면을 터치하여 오디오를 활성화해주세요.");
  }
};
```

**핵심 개선사항:**

- ✅ 30초 타임아웃으로 무한 대기 방지
- ✅ 재생 실패 시에도 피드백 페이지로 이동
- ✅ 사용자에게 명확한 오류 메시지 제공
- ✅ 빈 버퍼 상황도 처리

### 5. **사용자 안내 메시지**

```typescript
{
  !audioInitialized && turnCount === 0 && (
    <p className="text-xs text-yellow-400/80 mt-2">
      💡 모바일에서는 첫 번째 녹음 시 오디오가 활성화됩니다
    </p>
  );
}
```

**핵심 개선사항:**

- ✅ 모바일 사용자에게 오디오 활성화 필요성 안내
- ✅ 첫 대화 시작 전에만 표시

## 📊 개선 효과

### Before (문제 상황)

- ❌ 화면 꺼졌다 켜지면 TTS 작동 안 함
- ❌ 백그라운드 전환 후 오디오 재생 실패
- ❌ 초기 메시지 재생 차단
- ❌ TTS 실패 시 피드백 페이지 이동 불가
- ❌ 사용자에게 원인 불명

### After (개선 후)

- ✅ AudioContext 자동 재개로 안정적 재생
- ✅ 사용자 제스처로 오디오 초기화
- ✅ 페이지 복귀 시 자동 복구
- ✅ TTS 실패해도 피드백 페이지 이동
- ✅ 명확한 에러 메시지 제공

## 🔧 디버깅 방법

### Chrome DevTools (모바일)

1. Chrome에서 `chrome://inspect` 접속
2. 모바일 기기 연결 후 페이지 검사
3. Console에서 다음 로그 확인:
   - `🎵 AudioContext 생성됨`
   - `✅ 사용자 제스처로 AudioContext 초기화됨`
   - `🎵 AudioContext 재개됨 (suspended → running)`
   - `🎵 오디오 재생 시작`

### Safari Web Inspector (iOS)

1. iPhone 설정 → Safari → 고급 → 웹 속성 검사기 활성화
2. Mac Safari → 개발 메뉴 → iPhone 선택
3. Console에서 AudioContext 상태 모니터링

### AudioContext 상태 확인

```javascript
// Console에서 실행
if (audioContextRef.current) {
  console.log("AudioContext State:", audioContextRef.current.state);
  // "running" = 정상, "suspended" = 중단됨, "closed" = 종료됨
}
```

## 🎓 모바일 웹 오디오 모범 사례

### ✅ DO (해야 할 것)

1. **항상 사용자 제스처로 오디오 초기화**

   - 버튼 클릭, 터치 이벤트 등에서 AudioContext 생성/재개

2. **AudioContext 상태 확인**

   - 재생 전 `state` 속성 체크 (`running`인지 확인)
   - `suspended`면 `resume()` 호출

3. **Visibility API 사용**

   - 페이지 포커스 복귀 시 AudioContext 재개

4. **에러 처리 철저히**

   - try-catch로 모든 오디오 작업 감싸기
   - 실패 시 사용자 친화적 메시지 표시

5. **타임아웃 설정**
   - 무한 대기 방지를 위한 적절한 타임아웃

### ❌ DON'T (하지 말아야 할 것)

1. **페이지 로드 시 자동 재생**

   - 모바일 브라우저에서 차단됨

2. **AudioContext 상태 무시**

   - `suspended` 상태에서 재생 시도하면 실패

3. **단일 AudioContext 재생성**

   - 메모리 누수 및 성능 저하 유발

4. **에러 무시**
   - 재생 실패를 처리하지 않으면 UX 저하

## 🚀 추가 개선 방안 (선택사항)

### 1. Wake Lock API 사용

화면이 꺼지는 것을 방지하여 AudioContext 중단 최소화:

```typescript
let wakeLock: any = null;

const requestWakeLock = async () => {
  try {
    wakeLock = await (navigator as any).wakeLock.request("screen");
    console.log("Wake Lock 활성화");
  } catch (err) {
    console.log("Wake Lock 실패:", err);
  }
};
```

### 2. Service Worker로 백그라운드 오디오

Progressive Web App (PWA)으로 전환하여 백그라운드 오디오 지원

### 3. 오디오 재생 상태 UI 표시

사용자에게 오디오 재생 중임을 시각적으로 표시:

- 스피커 아이콘 애니메이션
- 파형 시각화
- "재생 중..." 텍스트

## 📝 참고 자료

- [MDN - AudioContext](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext)
- [MDN - Autoplay Policy](https://developer.mozilla.org/en-US/docs/Web/Media/Autoplay_guide)
- [MDN - Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)
- [Web Audio API 모범 사례](https://developers.google.com/web/updates/2017/09/autoplay-policy-changes)

## 💡 요약

모바일 웹에서 TTS가 갑자기 작동하지 않는 문제는 **AudioContext의 자동 중단**과 **모바일 자동재생 정책** 때문입니다.

핵심 해결책은:

1. ✅ **사용자 제스처로 AudioContext 초기화**
2. ✅ **재생 전 항상 AudioContext 상태 확인 및 재개**
3. ✅ **페이지 가시성 변경 감지하여 자동 복구**
4. ✅ **강력한 에러 처리 및 타임아웃**

이제 모바일에서도 안정적으로 TTS가 작동하며, 실패 시에도 피드백 페이지로 정상적으로 이동합니다! 🎉
