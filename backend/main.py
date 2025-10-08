import base64
import asyncio
import os
import json
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# --- 환경 변수 로드 ---
# .env 파일의 내용을 환경 변수로 로드합니다.
# 이 코드는 다른 모듈이 임포트되기 전에 실행되어야 합니다.
load_dotenv()

# --- 서비스 모듈 임포트 ---
# 환경 변수가 로드된 후, 서비스 모듈을 임포트합니다.
from services import elevenlabs_service, llm_service, feedback_service
from services.session_service import session_manager
from database import db


# --- 난이도별 프롬프트 생성 함수 ---
def get_difficulty_instruction(difficulty: str) -> str:
    """
    난이도에 따른 어휘 수준 지시사항을 반환합니다.
    
    Args:
        difficulty: "beginner", "intermediate", "advanced" 중 하나
        
    Returns:
        난이도에 맞는 지시사항 텍스트
    """
    difficulty_instructions = {
        "beginner": """VOCABULARY LEVEL - BEGINNER (초급):
- Use ONLY very basic, everyday words that 10-year-old children understand
- Examples: happy, sad, eat, play, friend, house, school
- NEVER use idioms, metaphors, or figurative language
- NEVER use phrasal verbs (like "hang out", "come up with")
- Keep sentences very short and simple
- Avoid any complex expressions""",
        
        "intermediate": """VOCABULARY LEVEL - INTERMEDIATE (중급):
- Use high school level vocabulary only
- Common words used in everyday conversation
- AVOID idioms and figurative expressions
- AVOID uncommon metaphors
- Use clear, literal language
- Keep expressions straightforward""",
        
        "advanced": """VOCABULARY LEVEL - ADVANCED (고급):
- Use natural, fluent English
- College-level vocabulary is acceptable
- You may use common idioms sparingly
- Express ideas naturally as a native speaker would"""
    }
    
    return difficulty_instructions.get(difficulty, difficulty_instructions["intermediate"])


def apply_difficulty_to_prompt(base_prompt: str, difficulty: str) -> str:
    """
    기본 system_prompt에 난이도 지시사항을 추가합니다.
    
    Args:
        base_prompt: 캐릭터의 기본 system prompt
        difficulty: 선택된 난이도
        
    Returns:
        난이도가 적용된 system prompt
    """
    difficulty_instruction = get_difficulty_instruction(difficulty)
    return f"{base_prompt}\n\n{difficulty_instruction}"


def get_initial_suggestions(difficulty: str) -> list:
    """
    초기 대화 시작을 위한 난이도별 추천 멘트를 반환합니다.
    
    Args:
        difficulty: 선택된 난이도
        
    Returns:
        3개의 추천 멘트 리스트
    """
    suggestions = {
        "beginner": [
            "I'm good, thanks!",
            "Pretty good.",
            "Not bad, how about you?"
        ],
        "intermediate": [
            "I'm doing well, thanks for asking!",
            "Pretty good, just a bit tired.",
            "Not too bad. How about yourself?"
        ],
        "advanced": [
            "I'm doing great, thanks! How about you?",
            "Pretty good, though it's been a long day.",
            "Can't complain. What brings you here?"
        ]
    }
    
    return suggestions.get(difficulty, suggestions["intermediate"])


# --- Emotion 분석 함수 ---
def analyze_emotion_from_text(text: str) -> str:
    """
    AI 응답 텍스트에서 감정을 분석하여 적절한 이미지를 선택합니다.
    
    Args:
        text: AI 응답 텍스트
        
    Returns:
        emotion 키 ("neutral", "smile", "surprised", "thoughtful", "excited")
    """
    text_lower = text.lower()
    
    # 감정 키워드 매핑 (우선순위 순)
    # 1. Excited (가장 강한 긍정)
    if any(word in text_lower for word in ["excited", "thrilled", "can't wait", "amazing", "awesome", "fantastic", "incredible"]):
        return "excited"
    
    # 2. Surprised (놀람)
    if any(word in text_lower for word in ["wow", "really?", "seriously?", "no way", "oh my", "surprised", "shocking", "unbelievable"]):
        return "surprised"
    
    # 3. Thoughtful (생각하는)
    if any(word in text_lower for word in ["hmm", "let me think", "interesting", "i see", "that's a good", "wondering", "curious", "consider"]):
        return "thoughtful"
    
    # 4. Smile (일반적인 긍정)
    if any(word in text_lower for word in ["happy", "glad", "great", "good", "nice", "wonderful", "pleased", "haha", "lol", "😊"]):
        return "smile"
    
    # 5. Neutral (기본값)
    return "neutral"


app = FastAPI()

# --- CORS 설정 (정적 파일 마운트 전에 추가) ---
# 프론트엔드에서 오는 요청을 허용합니다.
# 배포 시 ALLOWED_ORIGINS 환경 변수로 설정 가능
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
origins = [
    "http://localhost:3000",  # 로컬 개발
    "http://127.0.0.1:3000",  # 로컬 개발
]

# 환경 변수에서 추가 origin 로드 (쉼표로 구분)
if allowed_origins_env:
    origins.extend([origin.strip() for origin in allowed_origins_env.split(",")])

print(f"🌐 CORS 허용 Origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 생성된 이미지 디렉토리 설정 ---
GENERATED_IMAGES_DIR = Path(__file__).parent / "generated_images"
GENERATED_IMAGES_DIR.mkdir(exist_ok=True)

# 생성된 이미지를 정적 파일로 서빙 (CORS 이후에 마운트)
app.mount("/generated_images", StaticFiles(directory=str(GENERATED_IMAGES_DIR)), name="generated_images")


# --- Mock Character Data ---
# MVP 단계에서는 DB 대신 하드코딩된 캐릭터 데이터를 사용합니다.
characters_data = [
    {
        "id": "jeongsu",
        "name": "정수",
        "description": "방과 후 상담실에서 당신을 기다리고 있던 따뜻한 수학 교생 선생님. 겉모습은 엄격해 보이지만 학생들의 고민을 진심으로 들어주는 다정한 멘토다. 공부 이야기보다는 일상적인 대화로 학생들이 편안함을 느끼게 하고, 때때로 어설픈 개그로 분위기를 풀어준다.",
        "tags": ["교생", "선생님", "멘토", "힐링", "학교"],
        "creator": "@HealingTalk",
        "imageUrl": "/characters/man.webp",
        "emotion_images": {
            "neutral": "/characters/man.webp",
            "smile": "/characters/man_smile.png",
            "surprised": "/characters/man_surprise.png",
            "thoughtful": "/characters/man_thoughtful.png",
            "excited": "/characters/man_excited.png"
        },
        "interactions": "1.7",
        "likes": "56",
        "voice_id": "asDeXBMC8hUkhqqL7agO",  # Josh - 따뜻한 미국 남성 목소리
        "init_message": "Hey! Come on in. How's your day?",
        "system_prompt": "You are Jeongsu, a 26-year-old substitute math teacher who genuinely cares about his students. You speak in a warm, encouraging tone and use American English. While you can discuss academics, you're more interested in having casual, supportive conversations that help students feel comfortable. You occasionally make dad jokes to lighten the mood. You're a good listener and ask thoughtful follow-up questions. Keep responses brief (2-3 sentences) and natural, as if chatting during office hours. Show genuine interest in the student's day and life."
    },
    {
        "id": "Subin",
        "name": "수빈",
        "description": "실리콘밸리 테크 컨퍼런스 라운지에서 우연히 마주친 베테랑 엔지니어. 10년간 스타트업부터 빅테크까지 종횡무진하며 쌓은 경험으로 주니어 엔지니어들을 멘토링하고 있다. 비즈니스 영어, 프레젠테이션, 협상 스킬까지 실전에서 필요한 모든 것을 자연스럽게 가르쳐준다.",
        "tags": ["비즈니스", "멘토", "실리콘밸리", "엔지니어", "커리어"],
        "creator": "@CareerBoost",
        "imageUrl": "/characters/man3.png",
        "emotion_images": {
            "neutral": "/characters/man3.png",
            "smile": "/characters/man3_smile.png",
            "surprised": "/characters/man3_surprised.png",
            "thoughtful": "/characters/man3_thoughtful.png",
            "excited": "/characters/man3_excited.png"
        },
        "interactions": "3.4",
        "likes": "78",
        "voice_id": "pVnrL6sighQX7hVz89cp",  # Adam - 전문적인 미국 남성 목소리
        "init_message": "Hey! Mind if I join you? What brings you here?",
        "system_prompt": "You are Subin, a 35-year-old experienced Engineer from Silicon Valley. You speak professional but conversational American English. You're direct, insightful, and occasionally sarcastic in a friendly way. You enjoy sharing real-world business scenarios and asking thought-provoking questions about career and leadership. Keep responses concise (2-3 sentences) as if chatting during a coffee break at a tech conference."
    },
    {
        "id": "jihoon",
        "name": "지훈",
        "description": "인천공항 VIP 라운지에서 당신과 눈이 마주친 K-pop 아이돌. 해외 투어를 마치고 귀국하는 길, 야구모자와 후드로 정체를 숨기려 했지만 특유의 아우라는 감출 수 없다. 알아봐준 당신에게 밝은 미소를 지으며 먼저 다가온다. 팬들에게 늘 친근하고 겸손한 태도로 유명한 그는 유창한 영어로 자연스럽게 대화를 이어가며, 여행과 음악, 일상에 대한 편안한 수다를 즐긴다.",
        "tags": ["아이돌", "셀럽", "공항", "K-pop", "친근"],
        "creator": "@StarMeet",
        "imageUrl": "/characters/man4.png",
        "emotion_images": {
            "neutral": "/characters/man4.png",
            "smile": "/characters/man4_smile.png",
            "surprised": "/characters/man4_surprised.png",
            "thoughtful": "/characters/man4_thoughtful.png",
            "excited": "/characters/man4_excited.png"
        },
        "interactions": "9.8",
        "likes": "156",
        "voice_id": "UpphzPau5vxibPYV2NeV",  # Antoni - 친근한 영국 남성 목소리
        "init_message": "Oh! You recognized me? Please keep it quiet... Where are you going?",
        "system_prompt": "You are Jihoon, a 21-year-old popular K-pop idol who just ran into the user at an airport lounge. You speak fluent American English with a slight Korean accent, mixing casual and polite tones. Despite being famous, you're humble, friendly, and genuinely interested in talking to people. You're wearing a baseball cap and hoodie, trying to be low-key but still approachable. You enjoy talking about music, travel, food, and everyday life. Keep responses warm and conversational (2-3 sentences), like chatting with a new friend you just met by chance. Show curiosity about the user and share relatable stories. Be charming but not overly flirtatious."
    },
    {
        "id": "junhyeok",
        "name": "준혁",
        "description": "루프탑 바에서 위스키를 마시며 홀로 앉아있는 미스터리한 남자. 빨간 머리와 목과 손에 새겨진 문신, 은색 목걸이와 귀걸이가 위험하면서도 묘하게 끌리는 매력을 풍긴다. 첫인상은 차갑고 접근하기 어려워 보이지만, 대화를 나누다 보면 예상 밖으로 솔직하고 직설적인 면모를 보인다. 삶의 무게를 짊어진 듯한 눈빛이지만, 가끔씩 보여주는 부드러운 미소가 당신의 심장을 뛰게 만든다.",
        "tags": ["위험", "섹시", "바", "문신", "미스터리"],
        "creator": "@DangerousAttraction",
        "imageUrl": "/characters/man5.png",
        "emotion_images": {
            "neutral": "/characters/man5.png",
            "smile": "/characters/man5_smile.png",
            "surprised": "/characters/man5_surprised.png",
            "thoughtful": "/characters/man5_thoughtful.png",
            "excited": "/characters/man5_excited.png"
        },
        "interactions": "8.9",
        "likes": "142",
        "voice_id": "DMyrgzQFny3JI1Y1paM5",  # Drew - 깊고 성숙한 남성 목소리 (섹시하고 자신감 있음)
        "init_message": "Hey pretty, how was your day?",
        "system_prompt": "You are Junhyeok, a 28-year-old mysterious man sitting alone at a rooftop bar. You speak American English with a deep, confident voice. You're direct, slightly cynical, but surprisingly honest once someone earns your attention. You don't waste words - you're blunt and straightforward. Despite your tough exterior, you have a philosophical side and occasionally show unexpected warmth. You've lived through some rough times and it shows in your worldview. Keep responses short and impactful (2-3 sentences max), like someone who's seen too much to play games. Use casual, sometimes edgy language. Show subtle interest in the user without being overly friendly. You're intriguing, not intimidating."
    }
]

# --- Pydantic Models ---
class Character(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str]
    creator: str
    imageUrl: str
    interactions: str
    likes: str
    init_message: str

class ChatResponse(BaseModel):
    user_text: str
    ai_text: str
    ai_audio_base64: str
    character_image_url: str  # 생성된 캐릭터 이미지 URL

class PreRegistrationRequest(BaseModel):
    session_id: str
    name: str
    email: str
    phone: str = ""
    notify_email: bool = True
    notify_sms: bool = False

class BlockCheckRequest(BaseModel):
    fingerprint: str
    user_ip: str

# --- API Endpoints ---
@app.post("/api/check-block")
async def check_block(block_request: BlockCheckRequest, request: Request):
    """
    사용자가 이미 대화를 완료했는지 체크합니다.
    홈 페이지에서 캐릭터 클릭 시 호출됩니다.
    """
    # 실제 클라이언트 IP 추출
    client_ip = request.client.host if request.client else None
    
    print(f"\n{'🔍'*30}")
    print(f"🔍 [차단 체크 API] 요청 수신")
    print(f"  - IP: {client_ip}")
    print(f"  - Fingerprint: {block_request.fingerprint[:16]}...")
    print(f"{'🔍'*30}\n")
    
    is_blocked = db.check_user_ever_completed(
        user_ip=client_ip,
        fingerprint=block_request.fingerprint
    )
    
    print(f"\n{'✅' if not is_blocked else '🚫'}{'='*30}")
    print(f"{'✅ 접근 허용' if not is_blocked else '🚫 접근 차단'}")
    print(f"{'='*30}\n")
    
    return {
        "is_blocked": is_blocked,
        "message": "이미 서비스를 이용하셨습니다.\n\n무료 체험은 1회만 가능합니다." if is_blocked else None
    }

@app.get("/api/characters", response_model=List[Character])
async def get_characters():
    """프론트엔드에 보여줄 캐릭터 목록을 반환합니다."""
    # system_prompt는 민감 정보일 수 있으므로 제외하고 보냅니다.
    return [Character(**{k: v for k, v in char.items() if k != 'system_prompt'}) for char in characters_data]

@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat(
    character_id: str = Form(...),
    audio: UploadFile = File(...)
):
    """
    사용자 음성과 캐릭터 ID를 받아 STT -> LLM -> TTS 처리 후 응답을 반환합니다.
    """
    try:
        # 선택된 캐릭터의 system_prompt 찾기
        selected_character = next((char for char in characters_data if char["id"] == character_id), None)
        if not selected_character:
            raise HTTPException(status_code=404, detail="Character not found")
        
        system_prompt = selected_character["system_prompt"]

        audio_bytes = await audio.read()

        user_text = await elevenlabs_service.convert_speech_to_text(audio_bytes)

        if not user_text.strip():
            ai_text = "Sorry, I couldn't hear you. Could you please speak again?"
            ai_audio_bytes = await elevenlabs_service.convert_text_to_speech(ai_text)
        else:
            ai_text = await llm_service.get_llm_response(user_text, system_prompt)
            ai_audio_bytes = await elevenlabs_service.convert_text_to_speech(ai_text)

        ai_audio_base64 = base64.b64encode(ai_audio_bytes).decode('utf-8')

        # 캐릭터 원본 이미지 경로 사용
        character_image_path = selected_character["imageUrl"]

        return ChatResponse(
            user_text=user_text,
            ai_text=ai_text,
            ai_audio_base64=ai_audio_base64,
            character_image_url=character_image_path
        )
    
    except Exception as e:
        # 서비스 모듈에서 발생한 예외를 여기서 처리합니다.
        # 로깅을 통해 에러를 기록하는 것이 좋습니다.
        print(f"Error in /api/chat: {e}")
        # 클라이언트에게는 구체적인 에러 원인 대신 일반적인 메시지를 전달합니다.
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "AI Voice Learning Backend is running!"}

@app.get("/api/stats")
async def get_stats():
    """
    ElevenLabs API 요청 통계를 반환합니다.
    동시성 모니터링 및 디버깅 용도로 사용합니다.
    """
    stats = elevenlabs_service.get_request_stats()
    return {
        "elevenlabs_stats": stats,
        "message": "통계 정보입니다. MVP 단계 이후 대시보드 구축 시 활용하세요."
    }

@app.post("/api/pre-registration")
async def create_pre_registration(request: PreRegistrationRequest):
    """
    사전 등록 정보를 저장합니다.
    
    Args:
        request: 사전 등록 요청 데이터
    
    Returns:
        성공 메시지
    """
    try:
        # 세션 존재 여부 확인
        session_data = db.get_session(request.session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # 세션 완료 여부 확인
        if not session_data["is_completed"]:
            raise HTTPException(status_code=400, detail="아직 대화가 완료되지 않았습니다.")
        
        # 사전 등록 저장
        success = db.create_pre_registration(
            session_id=request.session_id,
            name=request.name,
            email=request.email,
            phone=request.phone if request.phone else None,
            notify_email=request.notify_email,
            notify_sms=request.notify_sms
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="사전 등록 저장에 실패했습니다.")
        
        # 활동 로그 기록
        db.log_activity(
            session_id=request.session_id,
            activity_type="pre_registration",
            activity_data={
                "name": request.name,
                "email": request.email,
                "notify_email": request.notify_email
            }
        )
        
        return {
            "success": True,
            "message": "사전 등록이 완료되었습니다! 정식 오픈 시 알려드리겠습니다."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"사전 등록 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=f"사전 등록 처리 중 오류가 발생했습니다: {str(e)}")

@app.get("/api/statistics")
async def get_statistics():
    """
    전체 통계 정보를 반환합니다.
    관리자용 대시보드에서 사용할 수 있습니다.
    
    Returns:
        통계 데이터
    """
    try:
        stats = db.get_statistics()
        pre_registrations = db.get_all_pre_registrations()
        
        return {
            "statistics": stats,
            "total_pre_registrations": len(pre_registrations),
            "recent_registrations": pre_registrations[:10]  # 최근 10건만 반환
        }
    except Exception as e:
        print(f"통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}")

@app.get("/api/feedback/{session_id}")
async def get_feedback(session_id: str):
    """
    세션 ID로 대화 피드백을 데이터베이스에서 조회하여 반환합니다.
    
    Args:
        session_id: 대화 세션 ID
    
    Returns:
        피드백 데이터 (문법 개선, 자연스러운 표현, 전반적 평가)
    """
    try:
        print(f"\n{'📊'*30}")
        print(f"📊 피드백 조회 요청: {session_id}")
        print(f"{'📊'*30}\n")
        
        # 데이터베이스에서 세션 조회 (메모리가 아닌 DB에서!)
        session_data = db.get_session(session_id)
        
        if not session_data:
            print(f"❌ 세션을 찾을 수 없습니다: {session_id}")
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        if not session_data.get("is_completed"):
            print(f"❌ 대화가 완료되지 않았습니다: {session_id}")
            raise HTTPException(status_code=400, detail="대화가 아직 완료되지 않았습니다.")
        
        print(f"✅ 세션 조회 성공!")
        print(f"  - 캐릭터: {session_data.get('character_id')}")
        print(f"  - 턴 수: {session_data.get('turn_count')}")
        print(f"  - 완료 여부: {session_data.get('is_completed')}")
        
        # DB에 저장된 피드백 데이터 파싱
        feedback_data_str = session_data.get("feedback_data")
        conversation_history_str = session_data.get("conversation_history")
        
        if not feedback_data_str:
            print(f"❌ 피드백 데이터가 없습니다: {session_id}")
            raise HTTPException(status_code=404, detail="피드백 데이터를 찾을 수 없습니다.")
        
        # JSON 문자열을 파이썬 객체로 변환
        feedback_data = json.loads(feedback_data_str)
        conversation_history = json.loads(conversation_history_str) if conversation_history_str else []
        
        print(f"✅ 피드백 데이터 파싱 성공!")
        print(f"  - 피드백 항목: {len(feedback_data.get('feedback_items', []))}개")
        print(f"  - 대화 히스토리: {len(conversation_history)}개 메시지")
        
        # 시간 계산
        start_time = session_data.get("start_time")
        end_time = session_data.get("end_time")
        duration_seconds = 0
        if start_time and end_time:
            duration_seconds = (end_time - start_time).total_seconds()
        
        # 세션 정보와 함께 반환
        return {
            "session_info": {
                "session_id": session_data.get("session_id"),
                "character_id": session_data.get("character_id"),
                "turn_count": session_data.get("turn_count", 0),
                "duration_seconds": duration_seconds,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None
            },
            "feedback": feedback_data,
            "conversation_history": conversation_history
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 피드백 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"피드백 조회 중 오류가 발생했습니다: {str(e)}")

@app.websocket("/ws/chat/{character_id}")
async def websocket_chat(websocket: WebSocket, character_id: str):
    """
    WebSocket 기반 실시간 음성 대화 엔드포인트
    
    클라이언트와 양방향 실시간 통신:
    1. 클라이언트 → 서버: 음성 데이터 (base64 인코딩)
    2. 서버 → 클라이언트: 
       - STT 결과 (텍스트)
       - LLM 응답 (텍스트)
       - TTS 오디오 청크 (스트리밍)
       - 캐릭터 이미지 URL
       - 턴 카운트 업데이트
       - 세션 완료 알림 (10턴 도달 시)
    
    장점:
    - 실시간 스트리밍으로 첫 응답 지연 최소화
    - 양방향 통신으로 중단/재시작 가능
    - 연결 유지로 오버헤드 감소
    - 대화 히스토리 자동 추적 및 10턴 제한
    - Fingerprint + IP 기반 영구 차단
    """
    await websocket.accept()
    
    # ✅ 1. 클라이언트 IP 추출
    client_ip = websocket.client.host if websocket.client else None
    user_agent = websocket.headers.get("user-agent", None)
    fingerprint = None  # 나중에 받을 예정
    
    # ✅ 2. 먼저 영구 차단 체크 (IP 기반으로 1차 체크)
    # fingerprint는 나중에 init 메시지로 받음
    if db.check_user_ever_completed(client_ip, None):
        try:
            await websocket.send_json({
                "type": "blocked",
                "message": "이미 서비스를 이용하셨습니다.\n\n무료 체험은 1회만 가능합니다."
            })
            await asyncio.sleep(0.1)  # 메시지 전송 대기
            await websocket.close()
        except Exception as e:
            print(f"⚠️ 차단 메시지 전송 실패 (연결 끊김): {e}")
        print(f"🚫 영구 차단 (IP): {character_id} 시도 - IP: {client_ip}\n")
        return
    
    # ✅ 4. 통과! 세션 생성
    websocket_id = str(id(websocket))
    session = session_manager.create_session(character_id, websocket_id)
    
    # 난이도는 init 메시지에서 받을 예정 (기본값: intermediate)
    session.difficulty = "intermediate"
    
    # ✅ 5. 데이터베이스에 세션 기록 (fingerprint 포함, 난이도는 나중에 업데이트)
    db.create_session(
        session_id=session.session_id,
        character_id=character_id,
        user_ip=client_ip,
        user_agent=user_agent,
        fingerprint=fingerprint,
        difficulty="intermediate"  # 기본값, 나중에 업데이트됨
    )
    
    # 최대 턴 수 설정 (인스타그램 광고용: 10턴)
    MAX_TURNS = 10
    
    print(f"\n{'🚀'*30}")
    print(f"✨ 새로운 세션 시작!")
    print(f"   세션 ID: {session.session_id}")
    print(f"   캐릭터: {character_id}")
    print(f"   IP: {client_ip}")
    print(f"   Fingerprint: {fingerprint[:16] if fingerprint else 'None'}...")
    print(f"   최대 턴 수: {MAX_TURNS}")
    print(f"{'🚀'*30}\n")
    
    try:
        # 캐릭터 정보 조회
        selected_character = next(
            (char for char in characters_data if char["id"] == character_id), 
            None
        )
        if not selected_character:
            await websocket.send_json({
                "type": "error",
                "message": "Character not found"
            })
            await websocket.close()
            return
        
        base_system_prompt = selected_character["system_prompt"]
        character_name = selected_character["name"]
        character_image_path = selected_character["imageUrl"]
        character_voice_id = selected_character.get("voice_id")
        character_emotion_images = selected_character.get("emotion_images", {})
        init_message = selected_character.get("init_message")
        
        # 연결 성공 메시지 (난이도 선택 요청 포함)
        await websocket.send_json({
            "type": "connected",
            "character_id": character_id,
            "character_name": character_name,
            "session_id": session.session_id,
            "max_turns": MAX_TURNS,
            "init_message": init_message,
            "request_difficulty": True  # 프론트엔드에 난이도 선택 모달 표시 요청
        })
        
        # 초기 메시지 TTS는 난이도 선택 후 init 메시지에서 처리됨
        
        # 메시지 수신 루프
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            # 세션 차단 여부 확인
            if db.is_session_blocked(session.session_id):
                await websocket.send_json({
                    "type": "error",
                    "message": "이미 회화가 완료되었습니다. 더 이상 대화할 수 없습니다."
                })
                await websocket.close()
                break
            
            if message_type == "init":
                # ✅ Fingerprint 수신 (나중에 받음)
                received_fingerprint = data.get("fingerprint")
                if received_fingerprint and not fingerprint:
                    fingerprint = received_fingerprint
                    print(f"🔐 Fingerprint 수신: {fingerprint[:16]}...")
                    
                    # 2차 차단 체크 (fingerprint 포함)
                    if db.check_user_ever_completed(client_ip, fingerprint):
                        try:
                            await websocket.send_json({
                                "type": "blocked",
                                "message": "이미 서비스를 이용하셨습니다.\n\n무료 체험은 1회만 가능합니다."
                            })
                            await asyncio.sleep(0.1)  # 메시지 전송 대기
                            await websocket.close()
                        except Exception as e:
                            print(f"⚠️ 차단 메시지 전송 실패 (연결 끊김): {e}")
                        print(f"🚫 영구 차단 (Fingerprint): {character_id} - FP: {fingerprint[:8]}...\n")
                        break
                    
                    # DB 업데이트 (fingerprint 저장)
                    try:
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE sessions SET fingerprint = %s WHERE session_id = %s",
                            (fingerprint, session.session_id)
                        )
                        conn.commit()
                        conn.close()
                        print(f"✅ Fingerprint DB 업데이트: {fingerprint[:8]}...")
                    except Exception as e:
                        print(f"⚠️ Fingerprint 업데이트 실패: {e}")
                
                # ✅ 난이도 수신
                received_difficulty = data.get("difficulty")
                if received_difficulty and received_difficulty in ["beginner", "intermediate", "advanced"]:
                    session.difficulty = received_difficulty
                    print(f"📚 난이도 설정: {received_difficulty}")
                    
                    # DB 업데이트 (난이도 저장)
                    try:
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE sessions SET difficulty = %s WHERE session_id = %s",
                            (received_difficulty, session.session_id)
                        )
                        conn.commit()
                        conn.close()
                        print(f"✅ 난이도 DB 업데이트: {received_difficulty}")
                    except Exception as e:
                        print(f"⚠️ 난이도 업데이트 실패: {e}")
                    
                    # 난이도가 적용된 system_prompt 생성
                    system_prompt = apply_difficulty_to_prompt(base_system_prompt, session.difficulty)
                    
                    # 초기 추천 멘트 전송 (하드코딩된 값)
                    initial_suggestions = get_initial_suggestions(session.difficulty)
                    await websocket.send_json({
                        "type": "suggested_responses",
                        "suggestions": initial_suggestions
                    })
                    print(f"💡 초기 추천 멘트 전송: {initial_suggestions}")
                    
                    # 초기 메시지를 음성으로 변환하여 전송 (난이도 선택 후)
                    if init_message and character_voice_id:
                        print(f"\n{'🎤'*30}")
                        print(f"🔊 초기 메시지 음성 생성 중...")
                        print(f"   메시지: {init_message}")
                        print(f"   목소리: {character_voice_id}")
                        print(f"   난이도: {session.difficulty}")
                        print(f"{'🎤'*30}\n")
                        
                        # 초기 메시지를 대화 히스토리에 추가
                        session.add_message("ai", init_message)
                        print(f"📝 초기 메시지를 대화 히스토리에 추가: {init_message[:50]}...")
                        
                        # 초기 메시지는 항상 neutral 이미지 사용 (기본 이미지)
                        init_emotion = "neutral"
                        init_image_url = character_emotion_images.get(init_emotion, character_image_path)
                        print(f"😊 초기 메시지는 기본 이미지 사용: {init_emotion} -> {init_image_url}")
                        
                        await websocket.send_json({
                            "type": "character_image",
                            "image_url": init_image_url,
                            "emotion": init_emotion
                        })
                        
                        # TTS 스트리밍 시작
                        await websocket.send_json({"type": "init_audio_stream_start"})
                        
                        # 오디오 청크를 실시간으로 전송
                        async for audio_chunk in elevenlabs_service.convert_text_to_speech_websocket(
                            init_message, 
                            character_voice_id
                        ):
                            chunk_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                            await websocket.send_json({
                                "type": "init_audio_chunk",
                                "data": chunk_base64
                            })
                        
                        # 스트리밍 완료 신호
                        await websocket.send_json({"type": "init_audio_stream_end"})
                        print(f"✅ 초기 메시지 음성 전송 완료\n")
                
                continue  # init 메시지는 여기서 끝
            
            elif message_type == "audio":
                # 음성 데이터 수신 (base64 인코딩)
                audio_base64 = data.get("audio")
                if not audio_base64:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No audio data provided"
                    })
                    continue
                
                # Base64 디코딩
                audio_bytes = base64.b64decode(audio_base64)
                
                # 1. STT 처리
                await websocket.send_json({"type": "status", "message": "음성 인식 중..."})
                user_text = await elevenlabs_service.convert_speech_to_text(audio_bytes)
                
                print(f"\n{'='*60}")
                print(f"[STT 결과] 사용자 음성 인식: {user_text}")
                print(f"{'='*60}\n")
                
                if not user_text.strip():
                    await websocket.send_json({
                        "type": "error",
                        "message": "음성을 인식할 수 없습니다. 다시 말씀해주세요."
                    })
                    continue
                
                # # 1-2. STT 결과 정제 (주석처리)
                # await websocket.send_json({"type": "status", "message": "텍스트 정제 중..."})
                # user_text = await llm_service.refine_stt_text(user_text)
                # print(f"[STT 정제] 정제된 텍스트: {user_text}")
                
                # STT 결과 전송
                await websocket.send_json({
                    "type": "stt_result",
                    "text": user_text
                })
                
                # 2. LLM 처리 - 현재 메시지를 추가하기 전에 이전 대화 히스토리 가져오기
                await websocket.send_json({"type": "status", "message": "응답 생성 중..."})
                
                # 이전 대화 히스토리 (현재 메시지 제외)
                previous_history = session.conversation_history.copy()
                
                print(f"[히스토리 확인] 현재까지 저장된 대화 수: {len(previous_history)}개")
                print(f"[히스토리 내용]")
                for i, msg in enumerate(previous_history, 1):
                    print(f"  {i}. [{msg['speaker'].upper()}]: {msg['text']}")
                
                # 세션에 사용자 메시지 추가 (턴 카운트 증가)
                session.add_message("user", user_text)
                
                # 데이터베이스에 턴 수 업데이트
                db.update_session_turn(session.session_id, session.turn_count)
                
                print(f"\n[턴 카운트] 현재 턴: {session.turn_count}/{MAX_TURNS}")
                
                # 턴 카운트 업데이트 전송
                await websocket.send_json({
                    "type": "turn_count_update",
                    "turn_count": session.turn_count,
                    "max_turns": MAX_TURNS
                })
                
                # 실시간 평가: 사용자 발화 분석 (백그라운드)
                evaluation_task = asyncio.create_task(
                    feedback_service.evaluate_user_message_realtime(user_text)
                )
                print(f"🔍 사용자 발화 실시간 평가 시작 (백그라운드)")
                
                # 마지막 턴 여부 확인
                is_final_turn = session.turn_count >= MAX_TURNS
                
                if is_final_turn:
                    print(f"🎉 [마지막 턴] {MAX_TURNS}턴 도달!")
                    session.complete_session()
                    
                    # 데이터베이스에 세션 완료 저장
                    db.complete_session(
                        session_id=session.session_id,
                        conversation_history=session.conversation_history,
                        feedback_data={
                            "feedback_items": session.feedback_items,
                            "overall_assessment": session.overall_assessment
                        }
                    )
                
                # LLM 응답 생성
                if is_final_turn:
                    print(f"🎉 [세션 완료] {MAX_TURNS}턴 도달! 마무리 멘트 생성 중...")
                    # 마무리 멘트 생성 (대화 히스토리 포함)
                    # 난이도가 적용된 system_prompt 사용
                    current_system_prompt = apply_difficulty_to_prompt(base_system_prompt, session.difficulty)
                    closing_prompt = current_system_prompt + "\n\nIMPORTANT: This is the end of our conversation (10 turns completed). Please provide a warm closing message in 2-3 sentences, thanking the user for the practice and encouraging them to keep learning English."
                    
                    print(f"\n[LLM INPUT - 마무리]")
                    print(f"  시스템 프롬프트: {closing_prompt[:100]}...")
                    print(f"  히스토리 메시지 수: {len(previous_history)}개")
                    print(f"  현재 사용자 메시지: {user_text}")
                    
                    ai_text = await llm_service.get_llm_response(user_text, closing_prompt, previous_history)
                else:
                    # 일반 응답 생성 (대화 히스토리 포함하여 맥락 유지)
                    # 난이도가 적용된 system_prompt 사용
                    current_system_prompt = apply_difficulty_to_prompt(base_system_prompt, session.difficulty)
                    
                    print(f"\n[LLM INPUT - 일반 대화]")
                    print(f"  시스템 프롬프트: {current_system_prompt[:100]}...")
                    print(f"  히스토리 메시지 수: {len(previous_history)}개")
                    print(f"  현재 사용자 메시지: {user_text}")
                    
                    ai_text = await llm_service.get_llm_response(user_text, current_system_prompt, previous_history)
                
                print(f"\n[LLM OUTPUT] AI 응답: {ai_text}")
                
                # 세션에 AI 메시지 추가
                session.add_message("ai", ai_text)
                
                # LLM 응답 전송
                await websocket.send_json({
                    "type": "llm_result",
                    "text": ai_text
                })
                
                # 3. AI 응답의 emotion 분석 및 해당 이미지 전송
                detected_emotion = analyze_emotion_from_text(ai_text)
                emotion_image_url = character_emotion_images.get(detected_emotion, character_image_path)
                
                print(f"😊 Emotion 분석 결과: '{detected_emotion}' -> {emotion_image_url}")
                
                await websocket.send_json({
                    "type": "character_image",
                    "image_url": emotion_image_url,
                    "emotion": detected_emotion
                })
                
                # 4. TTS 스트리밍 처리
                print(f"\n[TTS 시작] AI 응답을 음성으로 변환 중: {ai_text[:50]}...")
                await websocket.send_json({"type": "status", "message": "음성 합성 중..."})
                
                # 마지막 턴이면 TTS 시작 직전에 세션 완료 알림 전송
                if is_final_turn:
                    await websocket.send_json({
                        "type": "session_completed",
                        "session_id": session.session_id,
                        "turn_count": session.turn_count,
                        "message": "대화가 완료되었습니다!"
                    })
                    # 메시지가 확실히 전송되도록 약간의 delay
                    await asyncio.sleep(0.1)                
                # 스트리밍 시작 신호
                await websocket.send_json({"type": "audio_stream_start"})
                
                # 오디오 청크를 실시간으로 전송 (캐릭터 목소리 사용)
                async for audio_chunk in elevenlabs_service.convert_text_to_speech_websocket(
                    ai_text, 
                    character_voice_id
                ):
                    # 청크를 base64로 인코딩하여 전송
                    chunk_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "data": chunk_base64
                    })
                
                # 스트리밍 완료 신호
                await websocket.send_json({"type": "audio_stream_end"})
                print(f"[TTS 완료] 음성 전송 완료\n")
                
                # 추천 멘트 생성 (TTS 완료 후, 백그라운드)
                async def generate_and_send_suggestions():
                    try:
                        suggestions = await llm_service.generate_suggested_responses(
                            conversation_history=session.conversation_history,
                            character_name=character_name,
                            difficulty=session.difficulty
                        )
                        await websocket.send_json({
                            "type": "suggested_responses",
                            "suggestions": suggestions
                        })
                        print(f"💡 추천 멘트 전송: {suggestions}")
                    except Exception as e:
                        print(f"⚠️ 추천 멘트 생성/전송 실패: {e}")
                
                # 백그라운드로 실행
                asyncio.create_task(generate_and_send_suggestions())
                
                # 백그라운드 평가 결과 저장 (non-blocking)
                async def save_evaluation():
                    try:
                        evaluation_result = await evaluation_task
                        if evaluation_result:
                            # 피드백 항목 전체를 저장 (문장별 통합 구조)
                            session.add_feedback_item(evaluation_result)
                            
                            # 로깅: 어떤 피드백이 있는지 출력
                            grammar_has_issue = evaluation_result.get("grammar_issue", {}).get("has_issue", False)
                            naturalness_has_issue = evaluation_result.get("naturalness_issue", {}).get("has_issue", False)
                            
                            issues = []
                            if grammar_has_issue:
                                issues.append("문법")
                            if naturalness_has_issue:
                                issues.append("자연스러움")
                            
                            if issues:
                                print(f"  📝 피드백 저장: {', '.join(issues)} 개선 필요 - \"{evaluation_result.get('user_sentence', '')[:30]}...\"")
                            else:
                                print(f"  ✅ 완벽한 문장! 피드백 없음")
                        else:
                            print(f"  ✅ 완벽한 문장! 피드백 없음")
                    except Exception as e:
                        print(f"  ⚠️  평가 결과 저장 실패: {e}")
                
                # 백그라운드로 실행 (TTS를 blocking하지 않음)
                asyncio.create_task(save_evaluation())
                
                # 직전 턴(MAX_TURNS - 1)에 전반적 평가 생성
                is_second_to_last_turn = session.turn_count == (MAX_TURNS - 1)
                if is_second_to_last_turn:
                    print(f"\n{'🎯'*30}")
                    print(f"📊 [직전 턴] 전반적 평가 생성 시작 ({session.turn_count}/{MAX_TURNS})")
                    print(f"{'🎯'*30}\n")
                    
                    # 백그라운드로 전반적 평가 생성
                    async def generate_and_save_overall_assessment():
                        try:
                            # 현재까지 수집된 피드백으로 전반적 평가 생성
                            overall_assessment = await feedback_service.generate_overall_assessment(
                                session.feedback_items
                            )
                            session.overall_assessment = overall_assessment
                            print(f"\n✅ 전반적 평가 생성 완료!")
                            print(f"  - 주요 약점: {overall_assessment.get('main_weaknesses', 'N/A')[:50]}...")
                            print(f"  - 문법 점수: {overall_assessment.get('scores', {}).get('grammar', 'N/A')}")
                            print(f"  - 유창성 점수: {overall_assessment.get('scores', {}).get('fluency', 'N/A')}\n")
                        except Exception as e:
                            print(f"⚠️  전반적 평가 생성 실패: {e}")
                    
                    asyncio.create_task(generate_and_save_overall_assessment())
                
                # 마지막 턴이면 피드백 요약 출력 후 WebSocket 종료
                if is_final_turn:
                    print(f"\n{'='*60}")
                    print(f"📊 최종 수집된 피드백:")
                    print(f"  - 피드백 항목: {len(session.feedback_items)}개")
                    
                    # 문법/자연스러움 이슈 개수 세기
                    grammar_issues = sum(1 for item in session.feedback_items if item.get('grammar_issue', {}).get('has_issue', False))
                    naturalness_issues = sum(1 for item in session.feedback_items if item.get('naturalness_issue', {}).get('has_issue', False))
                    
                    print(f"    ㄴ 문법 이슈: {grammar_issues}개")
                    print(f"    ㄴ 자연스러움 이슈: {naturalness_issues}개")
                    print(f"{'='*60}\n")
                    
                    # 모든 메시지가 전송되도록 약간의 delay
                    await asyncio.sleep(0.2)
                    print(f"✅ 마지막 턴 완료 - WebSocket 연결 종료\n")
                    break
                
            elif message_type == "ping":
                # 연결 유지 확인
                await websocket.send_json({"type": "pong"})
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
    
    except WebSocketDisconnect:
        print(f"\n❌ WebSocket 연결 끊김: {character_id}")
    except Exception as e:
        print(f"\n⚠️  WebSocket 오류: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"서버 오류: {str(e)}"
            })
        except Exception:
            pass
        await websocket.close()
    finally:
        # 세션 정리
        print(f"\n{'🧹'*30}")
        print(f"세션 정리 중...")
        print(f"  세션 ID: {session.session_id}")
        print(f"  최종 턴 수: {session.turn_count}")
        print(f"  총 대화 메시지: {len(session.conversation_history)}개")
        session_manager.remove_session(websocket_id)
        print(f"✅ 세션 정리 완료!")
        print(f"{'🧹'*30}\n")
