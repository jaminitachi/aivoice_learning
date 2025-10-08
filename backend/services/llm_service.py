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

async def generate_suggested_responses(
    conversation_history: list,
    character_name: str,
    difficulty: str
) -> list:
    """
    대화 맥락을 기반으로 사용자가 사용할 수 있는 3가지 추천 멘트를 생성합니다.
    
    Args:
        conversation_history: 현재까지의 대화 히스토리
        character_name: 대화 상대 캐릭터 이름
        difficulty: 난이도 (beginner, intermediate, advanced)
    
    Returns:
        3개의 추천 멘트 리스트
    """
    try:
        # 대화 히스토리를 텍스트로 변환
        history_text = ""
        for msg in conversation_history[-6:]:  # 최근 6개 메시지만 사용
            speaker = "You" if msg["speaker"] == "user" else character_name
            history_text += f"{speaker}: {msg['text']}\n"
        
        # 난이도별 지시사항
        difficulty_instructions = {
            "beginner": "Use VERY simple words that 10-year-old children understand. NO idioms, NO phrasal verbs.",
            "intermediate": "Use high school level vocabulary. Clear and straightforward language.",
            "advanced": "Use natural, fluent English with college-level vocabulary."
        }
        
        vocab_instruction = difficulty_instructions.get(difficulty, difficulty_instructions["intermediate"])
        
        prompt = f"""Based on this conversation, suggest 3 short, natural responses the user could say next.

Conversation so far:
{history_text}

Requirements:
- Each response should be 5-10 words maximum
- Make them natural and conversational
- Vary the responses (question, statement, follow-up)
- {vocab_instruction}
- Return ONLY a JSON array of 3 strings, nothing else

Example format: ["Response 1", "Response 2", "Response 3"]"""

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates natural conversation suggestions. Return only valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=150,
            temperature=0.8
        )
        
        suggestions_text = response.choices[0].message.content.strip()
        
        # JSON 파싱
        import json
        import re
        
        # JSON 배열만 추출 (혹시 다른 텍스트가 포함되어 있을 경우)
        json_match = re.search(r'\[.*\]', suggestions_text, re.DOTALL)
        if json_match:
            suggestions = json.loads(json_match.group())
        else:
            suggestions = json.loads(suggestions_text)
        
        # 3개가 아니면 조정
        if len(suggestions) < 3:
            suggestions.extend(["Tell me more", "That's interesting", "What about you?"][:3-len(suggestions)])
        
        return suggestions[:3]
        
    except Exception as e:
        print(f"⚠️ 추천 멘트 생성 실패: {e}")
        # 기본 추천 멘트 반환
        default_suggestions = {
            "beginner": ["I like that!", "Tell me more.", "What about you?"],
            "intermediate": ["That's interesting.", "I see what you mean.", "How do you feel about it?"],
            "advanced": ["That's a great point.", "I hadn't thought of it that way.", "What's your take on this?"]
        }
        return default_suggestions.get(difficulty, default_suggestions["intermediate"])


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
