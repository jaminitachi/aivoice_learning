"""
세션 관리 서비스

WebSocket 연결마다 대화 세션을 생성하고 관리합니다.
각 세션은 대화 턴 수, 히스토리 등을 추적합니다.
"""

from typing import Dict, List, Optional
from datetime import datetime
import uuid


class ConversationSession:
    """대화 세션 데이터 모델"""
    
    def __init__(self, character_id: str):
        self.session_id: str = str(uuid.uuid4())
        self.character_id: str = character_id
        self.turn_count: int = 0
        self.conversation_history: List[Dict[str, str]] = []
        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None
        self.is_completed: bool = False
        self.feedback_items: List[Dict] = []  # 실시간으로 수집된 피드백 항목들 (문장별 통합)
        self.overall_assessment: Optional[Dict] = None  # 전반적 평가 (직전 턴에 생성)
    
    def add_message(self, speaker: str, text: str):
        """대화 메시지 추가 (speaker: 'user' 또는 'ai')"""
        self.conversation_history.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
        
        # user가 말한 경우에만 턴 카운트 증가
        if speaker == "user":
            self.turn_count += 1
    
    def add_feedback_item(self, feedback_item: dict):
        """피드백 항목 추가 (실시간 평가 결과 저장)"""
        self.feedback_items.append(feedback_item)
    
    def complete_session(self):
        """세션 완료 처리"""
        self.is_completed = True
        self.end_time = datetime.now()
    
    def get_user_messages(self) -> List[str]:
        """사용자 메시지만 추출"""
        return [
            msg["text"] 
            for msg in self.conversation_history 
            if msg["speaker"] == "user"
        ]
    
    def get_conversation_duration(self) -> float:
        """대화 시간 반환 (초 단위)"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> dict:
        """세션 정보를 딕셔너리로 변환"""
        return {
            "session_id": self.session_id,
            "character_id": self.character_id,
            "turn_count": self.turn_count,
            "conversation_history": self.conversation_history,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "is_completed": self.is_completed,
            "duration_seconds": self.get_conversation_duration()
        }


class SessionManager:
    """세션 관리자 - 모든 활성 세션을 관리합니다"""
    
    def __init__(self):
        # 세션 ID를 키로 하는 세션 저장소
        self.sessions: Dict[str, ConversationSession] = {}
        # WebSocket ID를 키로 세션 ID를 매핑
        self.websocket_to_session: Dict[str, str] = {}
    
    def create_session(self, character_id: str, websocket_id: str) -> ConversationSession:
        """새로운 세션 생성"""
        session = ConversationSession(character_id)
        self.sessions[session.session_id] = session
        self.websocket_to_session[websocket_id] = session.session_id
        print(f"세션 생성: {session.session_id} (캐릭터: {character_id})")
        return session
    
    def get_session_by_websocket(self, websocket_id: str) -> Optional[ConversationSession]:
        """WebSocket ID로 세션 조회"""
        session_id = self.websocket_to_session.get(websocket_id)
        if session_id:
            return self.sessions.get(session_id)
        return None
    
    def get_session_by_id(self, session_id: str) -> Optional[ConversationSession]:
        """세션 ID로 세션 조회"""
        return self.sessions.get(session_id)
    
    def remove_session(self, websocket_id: str):
        """세션 제거 (WebSocket 연결 종료 시)"""
        session_id = self.websocket_to_session.get(websocket_id)
        if session_id:
            session = self.sessions.get(session_id)
            if session:
                # 완료되지 않은 세션은 일정 시간 후 자동 삭제되도록 보관
                # (피드백 요청을 위해 잠시 보관)
                if not session.is_completed:
                    session.complete_session()
                print(f"세션 제거 예약: {session_id}")
            
            # WebSocket 매핑은 바로 제거
            del self.websocket_to_session[websocket_id]
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """오래된 세션 정리"""
        now = datetime.now()
        sessions_to_remove = []
        
        for session_id, session in self.sessions.items():
            if session.end_time:
                age_hours = (now - session.end_time).total_seconds() / 3600
                if age_hours > max_age_hours:
                    sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            print(f"오래된 세션 삭제: {session_id}")
    
    def get_active_session_count(self) -> int:
        """활성 세션 수 반환"""
        return len([s for s in self.sessions.values() if not s.is_completed])


# 전역 세션 매니저 인스턴스
session_manager = SessionManager()

