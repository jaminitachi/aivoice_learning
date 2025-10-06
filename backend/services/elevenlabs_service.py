import os
import httpx
import asyncio
import logging
from typing import AsyncGenerator

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 환경 변수 로드 ---
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise ValueError("ELEVENLABS_API_KEY 환경 변수가 설정되지 않았습니다.")

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
# 사용 가능한 음성 ID는 ElevenLabs API 문서를 참조하세요.
# 예시: Rachel - 21m00Tcm4TlvDq8ikWAM
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# --- 동시성 제어 설정 ---
# MVP 단계: 무료/스타터 플랜은 보통 2-5개 동시 요청 한도
# 현재 플랜에 맞게 조정하세요 (예: Starter=2, Creator=5, Pro=10)
MAX_CONCURRENT_REQUESTS = 3  # 안전하게 3으로 설정 (실제 한도보다 작게)
stt_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
tts_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# --- 재시도 설정 ---
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 0.5  # 초

# --- 요청 큐 (통계 모니터링용) ---
# 실제 큐잉은 세마포어가 자동으로 처리하지만, 통계를 위해 추적
_request_stats = {
    "total_requests": 0,
    "queued_requests": 0,
    "failed_requests": 0,
    "successful_requests": 0
}


def get_request_stats() -> dict:
    """현재 요청 통계 반환"""
    return _request_stats.copy()


# =============================================================================
# WebSocket 기반 실시간 TTS (고급 기능)
# =============================================================================

async def convert_text_to_speech_websocket(
    text: str, 
    voice_id: str = DEFAULT_VOICE_ID,
    use_fast_model: bool = True
) -> AsyncGenerator[bytes, None]:
    """
    WebSocket을 통해 실시간으로 텍스트를 음성으로 변환합니다.
    
    장점:
    - 첫 오디오 청크를 훨씬 빠르게 받을 수 있음 (저지연)
    - 실제 생성 시간만 동시성에 집계되어 효율성 ↑
    - 스트리밍 재생으로 사용자 경험 개선
    
    Args:
        text: 음성으로 변환할 텍스트
        voice_id: ElevenLabs 음성 ID
        use_fast_model: True면 Flash v2.5, False면 Multilingual v2
        
    Yields:
        오디오 데이터 청크 (bytes)
    """
    model_id = "eleven_flash_v2_5" if use_fast_model else "eleven_multilingual_v2"
    _request_stats["total_requests"] += 1
    
    # WebSocket은 실제 생성 시간만 동시성에 집계되므로 세마포어 효율성 ↑
    async with tts_semaphore:
        logger.info(f"[TTS-WS] WebSocket 스트리밍 시작 (모델: {model_id})")
        
        try:
            # httpx는 WebSocket을 지원하지 않으므로, websockets 라이브러리 필요
            # 하지만 MVP 단계에서는 httpx의 stream 기능으로 대체 가능
            # 실제 WebSocket 구현은 websockets 라이브러리 설치 필요:
            # pip install websockets
            
            # 여기서는 HTTP streaming으로 유사한 효과 구현
            tts_url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}/stream"
            
            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    tts_url,
                    headers={
                        "xi-api-key": ELEVENLABS_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    # 스트림으로 청크 단위로 수신
                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        if chunk:
                            yield chunk
            
            logger.info("[TTS-WS] 스트리밍 완료")
            _request_stats["successful_requests"] += 1
            
        except Exception as e:
            _request_stats["failed_requests"] += 1
            logger.error(f"[TTS-WS] WebSocket 스트리밍 에러: {e}")
            raise


async def _retry_with_backoff(func, *args, max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, **kwargs):
    """
    Exponential backoff를 사용한 재시도 로직
    
    Args:
        func: 재시도할 비동기 함수
        max_retries: 최대 재시도 횟수
        initial_delay: 초기 지연 시간 (초)
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            # 429 (Too Many Requests) 또는 503 (Service Unavailable)인 경우 재시도
            if e.response.status_code in [429, 503] and attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"API 한도 초과 (status={e.response.status_code}). "
                    f"{delay}초 후 재시도 ({attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                logger.warning(f"요청 실패. {delay}초 후 재시도 ({attempt + 1}/{max_retries}): {str(e)}")
                await asyncio.sleep(delay)
                continue
            raise
    
    raise Exception("최대 재시도 횟수를 초과했습니다.")


async def _call_stt_api(audio_bytes: bytes, headers: dict, data: dict, files: dict) -> dict:
    """STT API 호출 내부 함수 (재시도 로직에서 사용)"""
    stt_url = f"{ELEVENLABS_API_URL}/speech-to-text"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(stt_url, headers=headers, data=data, files=files)
        
        # 응답 헤더 모니터링
        current_concurrent = response.headers.get("current-concurrent-requests")
        max_concurrent = response.headers.get("maximum-concurrent-requests")
        if current_concurrent and max_concurrent:
            logger.info(f"[STT] 동시성 현황: {current_concurrent}/{max_concurrent}")
        
        response.raise_for_status()
        return response.json()


async def convert_speech_to_text(audio_bytes: bytes) -> str:
    """
    ElevenLabs STT API를 호출하여 음성 데이터를 텍스트로 변환합니다.
    동시성 제어 및 재시도 로직이 적용되어 있습니다.
    """
    _request_stats["total_requests"] += 1
    
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    data = {"model_id": "scribe_v1"}
    files = {"file": ("audio.webm", audio_bytes, "audio/webm")}
    
    # 세마포어로 동시 요청 수 제한
    queued_count = MAX_CONCURRENT_REQUESTS - stt_semaphore._value
    if queued_count > 0:
        _request_stats["queued_requests"] += 1
        logger.warning(f"[STT] 요청 대기 중 (큐에 {queued_count}개 요청)")
    
    async with stt_semaphore:
        logger.info("[STT] 요청 시작")
        try:
            result = await _retry_with_backoff(
                _call_stt_api,
                audio_bytes,
                headers,
                data,
                files
            )
            text = result.get("text", "")
            logger.info(f"[STT] 요청 성공: {text[:50]}...")
            _request_stats["successful_requests"] += 1
            return text
        except httpx.HTTPStatusError as e:
            _request_stats["failed_requests"] += 1
            logger.error(f"ElevenLabs STT API 에러: {e.response.status_code} - {e.response.text}")
            raise Exception("음성 변환 중 오류가 발생했습니다.")
        except Exception as e:
            _request_stats["failed_requests"] += 1
            logger.error(f"ElevenLabs STT API 호출 중 예기치 않은 오류: {e}")
            raise


async def _call_tts_api(text: str, headers: dict, payload: dict, voice_id: str = DEFAULT_VOICE_ID) -> bytes:
    """TTS API 호출 내부 함수 (재시도 로직에서 사용)"""
    tts_url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(tts_url, headers=headers, json=payload)
        
        # 응답 헤더 모니터링
        current_concurrent = response.headers.get("current-concurrent-requests")
        max_concurrent = response.headers.get("maximum-concurrent-requests")
        if current_concurrent and max_concurrent:
            logger.info(f"[TTS] 동시성 현황: {current_concurrent}/{max_concurrent}")
        
        response.raise_for_status()
        return response.content


async def convert_text_to_speech(text: str, voice_id: str = DEFAULT_VOICE_ID, use_fast_model: bool = True) -> bytes:
    """
    ElevenLabs TTS API를 호출하여 텍스트를 음성 데이터로 변환합니다.
    동시성 제어 및 재시도 로직이 적용되어 있습니다.
    
    Args:
        text: 음성으로 변환할 텍스트
        voice_id: ElevenLabs 음성 ID (기본값: Rachel)
        use_fast_model: True면 Flash v2.5 (저지연), False면 Multilingual v2 (고품질)
    
    Returns:
        음성 데이터 (bytes)
    """
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    
    # MVP 단계: 실시간 대화에는 Flash v2.5 모델 사용 (저지연, 동시성 효율 ↑)
    # 필요 시 파라미터로 고품질 모델 선택 가능
    model_id = "eleven_flash_v2_5" if use_fast_model else "eleven_multilingual_v2"
    
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    _request_stats["total_requests"] += 1
    
    # 세마포어로 동시 요청 수 제한
    queued_count = MAX_CONCURRENT_REQUESTS - tts_semaphore._value
    if queued_count > 0:
        _request_stats["queued_requests"] += 1
        logger.warning(f"[TTS] 요청 대기 중 (큐에 {queued_count}개 요청)")
    
    async with tts_semaphore:
        logger.info(f"[TTS] 요청 시작 (모델: {model_id}, voice: {voice_id})")
        try:
            content = await _retry_with_backoff(
                _call_tts_api,
                text,
                headers,
                payload,
                voice_id
            )
            logger.info(f"[TTS] 요청 성공: {len(content)} bytes")
            _request_stats["successful_requests"] += 1
            return content
        except httpx.HTTPStatusError as e:
            _request_stats["failed_requests"] += 1
            logger.error(f"ElevenLabs TTS API 에러: {e.response.status_code} - {e.response.text}")
            raise Exception("음성 합성 중 오류가 발생했습니다.")
        except Exception as e:
            _request_stats["failed_requests"] += 1
            logger.error(f"ElevenLabs TTS API 호출 중 예기치 않은 오류: {e}")
            raise
