import os
from openai import AsyncOpenAI

# --- 환경 변수 로드 ---
# .env 파일에서 LLM 관련 설정을 불러옵니다.
OPENROUTER_API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "x-ai/grok-4-fast")


if not OPENROUTER_API_KEY:
    raise ValueError("LLM_API_KEY 환경 변수가 설정되지 않았습니다. (OpenRouter API Key)")

# --- OpenAI 클라이언트 초기화 ---
# OpenRouter API를 사용하기 위해 base_url을 지정하여 클라이언트를 생성합니다.
client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

def get_grok_client() -> AsyncOpenAI:
    """
    Grok LLM 클라이언트 반환
    피드백 서비스 등 다른 서비스에서 사용할 수 있도록 클라이언트를 제공합니다.
    """
    return client

async def refine_stt_text(raw_stt_text: str) -> str:
    """
    STT 결과를 정제합니다.
    - 괄호 안 내용 제거 (음향 효과, 배경음 등)
    - 반복된 단어/구문 정리
    - 불필요한 공백 제거
    - 간단한 문법 보정 (대소문자 등)
    
    Args:
        raw_stt_text: STT 원본 텍스트
    
    Returns:
        정제된 텍스트
    """
    import re
    
    # 1. 기본 정제 (빠른 규칙 기반)
    text = raw_stt_text.strip()
    
    # 괄호 안 내용 제거 (예: "[음악]", "(배경음)", "[웃음]" 등)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # 2. LLM을 사용한 고급 정제 (반복 제거, 문맥상 불필요한 부분 정리)
    try:
        refine_prompt = f"""Clean up this speech-to-text transcription. Remove:
- Repeated words or phrases (e.g., "I I think" → "I think")
- Filler words that don't add meaning (um, uh, like) ONLY if excessive
- Any remaining transcription artifacts

Keep the natural conversational tone. Don't change the meaning.

Original: "{text}"

Return ONLY the cleaned text, nothing else."""

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a text cleanup assistant. Return only the cleaned text, no explanations."
                },
                {
                    "role": "user",
                    "content": refine_prompt
                }
            ],
            max_tokens=300,
            temperature=0.3  # 낮은 온도로 일관성 유지
        )
        
        refined = response.choices[0].message.content.strip()
        
        # 따옴표로 감싸진 경우 제거
        if refined.startswith('"') and refined.endswith('"'):
            refined = refined[1:-1]
        
        print(f"🔧 STT Refined: '{raw_stt_text}' → '{refined}'")
        return refined if refined else text
        
    except Exception as e:
        print(f"⚠️ STT 정제 중 오류 (원본 반환): {e}")
        return text

async def get_llm_response(user_text: str, system_prompt: str, conversation_history: list = None) -> str:
    """
    OpenRouter를 통해 gpt-5-chat 모델을 호출하여 AI 응답을 생성합니다.
    대화 히스토리를 함께 전달하여 맥락을 유지합니다.
    
    Args:
        user_text: 현재 사용자 메시지
        system_prompt: 시스템 프롬프트 (캐릭터 설정)
        conversation_history: 이전 대화 히스토리 [{"speaker": "user", "text": "..."}, ...]
    
    Returns:
        AI 응답 텍스트
    """
    try:
        # 메시지 배열 구성
        messages = [{"role": "system", "content": system_prompt}]
        
        # 대화 히스토리가 있으면 추가 (맥락 유지)
        if conversation_history:
            for msg in conversation_history:
                role = "user" if msg["speaker"] == "user" else "assistant"
                messages.append({"role": role, "content": msg["text"]})
        
        # 현재 사용자 메시지 추가
        messages.append({"role": "user", "content": user_text})
        
        print(f"\n{'🤖'*30}")
        print(f"[LLM 전체 메시지 확인]")
        print(f"  모델: {MODEL_NAME}")
        print(f"  총 메시지 수: {len(messages)}개")
        for i, msg in enumerate(messages, 1):
            content_preview = msg['content'][:80] + "..." if len(msg['content']) > 80 else msg['content']
            print(f"  {i}. [{msg['role'].upper()}]: {content_preview}")
        print(f"{'🤖'*30}\n")
        
        completion = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=100,
            temperature=0.7,
            extra_body={
                "reasoning": {
                    "enabled": True
                }
            }
        )
        ai_message = completion.choices[0].message.content
        return ai_message.strip() if ai_message else ""
    
    except Exception as e:
        # openai 라이브러리에서 발생하는 모든 예외를 처리합니다.
        print(f"OpenRouter API 호출 중 에러 발생: {e}")
        # 클라이언트에게 전달될 최종 예외 메시지를 일관되게 관리합니다.
        raise Exception("AI 응답 생성 중 오류가 발생했습니다.")
