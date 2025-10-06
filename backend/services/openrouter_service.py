"""
OpenRouter API를 사용하여 캐릭터 이미지를 생성하는 서비스 모듈입니다.
캐릭터의 기존 이미지와 텍스트 프롬프트를 기반으로 새로운 이미지를 생성합니다.
"""

import os
import base64
import httpx
from datetime import datetime
from pathlib import Path

# 생성된 이미지 저장 디렉토리
GENERATED_IMAGES_DIR = Path(__file__).parent.parent / "generated_images"
GENERATED_IMAGES_DIR.mkdir(exist_ok=True)

# OpenRouter API 키
OPENROUTER_API_KEY = os.getenv("LLM_API_KEY")


async def generate_character_image(
    character_image_base64: str,
    emotion_or_situation: str,
    character_name: str
) -> str:
    """
    캐릭터 이미지와 감정/상황을 기반으로 새로운 이미지를 생성합니다.
    
    Args:
        character_image_base64: 캐릭터의 기존 이미지 (data URL 형식)
        emotion_or_situation: 생성할 감정이나 상황 (예: "happy and smiling", "surprised and amazed")
        character_name: 캐릭터 이름
        
    Returns:
        생성된 이미지의 로컬 파일 경로 또는 None
    """
    try:
        # 감정/상황에 맞는 프롬프트 생성
        prompt = f"""Generate a portrait image of {character_name} showing a {emotion_or_situation} expression. 
        
Reference the character's appearance from the provided image, but create a new image with:
- A {emotion_or_situation} facial expression
- Body language that matches the {emotion_or_situation} emotion
- Same art style and character design as the reference
- High quality, detailed portrait

Keep the character recognizable but change only the expression and pose to convey the {emotion_or_situation} emotion."""
        
        print(f"[generate_character_image] 이미지 생성 시작: {character_name}, {emotion_or_situation}")
        
        # OpenRouter API 호출
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://aivoicelearning.app",
                    "X-Title": "AI Voice Learning"
                },
                json={
                    "model": "google/gemini-2.5-flash-image-preview",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": character_image_base64
                                    }
                                }
                            ]
                        }
                    ],
                    "stream": False
                }
            )
        
        response.raise_for_status()
        data = response.json()
        
        print("[generate_character_image] API 응답 받음")
        print(f"[DEBUG] Full API Response: {data}")
        
        # 응답에서 이미지 데이터 추출
        message = data.get('choices', [{}])[0].get('message', {})
        
        # 응답 형식 확인 (이미지가 어떤 형식으로 오는지)
        if message.get('images'):
            # images 필드가 있는 경우
            image_url_data = message['images'][0].get('image_url', {}).get('url', '')
        elif message.get('content'):
            # content에 이미지가 포함된 경우
            content = message['content']
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'image_url':
                        image_url_data = item.get('image_url', {}).get('url', '')
                        break
                else:
                    image_url_data = None
            else:
                image_url_data = content
        else:
            print("[generate_character_image] 응답에서 이미지 데이터를 찾을 수 없음")
            return None
        
        if not image_url_data:
            print("[generate_character_image] image_url_data가 비어있음")
            return None
        
        # base64 데이터 추출
        if "base64," in image_url_data:
            image_base64 = image_url_data.split('base64,')[1]
            print("[generate_character_image] BASE64 데이터 추출 완료")
            
            # BASE64 패딩 보정
            missing_padding = len(image_base64) % 4
            if missing_padding != 0:
                print(f"[generate_character_image] BASE64 패딩 오류 감지. '=' {4 - missing_padding}개 추가")
                image_base64 += '=' * (4 - missing_padding)
            
            # 이미지 디코딩
            image_data = base64.b64decode(image_base64)
            
            # 파일명 생성 (타임스탬프 포함) - 백업용으로 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{character_name}_{emotion_or_situation.replace(' ', '_')}_{timestamp}.png"
            filepath = GENERATED_IMAGES_DIR / filename
            
            # 로컬에 백업 저장
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            print(f"[generate_character_image] 이미지 저장 완료: {filepath}")
            
            # base64 data URL 반환 (프론트엔드에서 바로 사용 가능)
            data_url = f"data:image/png;base64,{image_base64}"
            return data_url
        else:
            print("[generate_character_image] 응답 URL에서 'base64,' 구분자를 찾지 못함")
            return None
        
    except httpx.HTTPStatusError as e:
        print(f"[generate_character_image] API 오류: {e.response.status_code}")
        print(f"[generate_character_image] 오류 내용: {e.response.text}")
        return None
    except Exception as e:
        print(f"[generate_character_image] 이미지 생성 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_emotion_from_text(text: str) -> str:
    """
    AI 응답 텍스트에서 감정/상황을 분석합니다.
    
    Args:
        text: AI 응답 텍스트
        
    Returns:
        감정 또는 상황을 나타내는 문자열
    """
    # 간단한 키워드 기반 감정 분석
    text_lower = text.lower()
    
    # 감정 키워드 매핑
    if any(word in text_lower for word in ["happy", "great", "wonderful", "excellent", "glad", "pleased", "delighted", "joy"]):
        return "happy and smiling"
    elif any(word in text_lower for word in ["sad", "sorry", "unfortunate", "disappointed", "unhappy"]):
        return "sad and sympathetic"
    elif any(word in text_lower for word in ["surprised", "wow", "amazing", "unbelievable", "shocking"]):
        return "surprised and amazed"
    elif any(word in text_lower for word in ["angry", "upset", "furious", "annoyed", "irritated"]):
        return "angry and frustrated"
    elif any(word in text_lower for word in ["confused", "puzzled", "unclear", "don't understand"]):
        return "confused and thinking"
    elif any(word in text_lower for word in ["excited", "thrilled", "enthusiastic", "can't wait"]):
        return "excited and energetic"
    elif any(word in text_lower for word in ["tired", "exhausted", "sleepy", "weary"]):
        return "tired and exhausted"
    elif any(word in text_lower for word in ["thinking", "hmm", "let me", "consider"]):
        return "thoughtful and contemplative"
    else:
        # 기본값: 자연스러운 대화 표정
        return "friendly and conversational"


async def get_character_image_with_emotion(
    character_image_base64: str,
    ai_response_text: str,
    character_name: str
) -> str:
    """
    AI 응답 텍스트를 분석하여 적절한 감정의 캐릭터 이미지를 생성합니다.
    
    Args:
        character_image_base64: 캐릭터의 기존 이미지 (data URL 형식)
        ai_response_text: AI의 응답 텍스트
        character_name: 캐릭터 이름
        
    Returns:
        생성된 이미지의 로컬 파일 경로 또는 None
    """
    emotion = analyze_emotion_from_text(ai_response_text)
    return await generate_character_image(character_image_base64, emotion, character_name)
