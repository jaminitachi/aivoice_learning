// API 설정을 중앙화하여 관리합니다
// 환경 변수가 있으면 사용하고, 없으면 기본값을 사용합니다
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// WebSocket URL (http를 ws로 변환)
export const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  API_BASE_URL.replace("http://", "ws://").replace("https://", "wss://");

// API 엔드포인트들
export const API_ENDPOINTS = {
  CHARACTERS: `${API_BASE_URL}/api/characters`,
  CHAT: `${API_BASE_URL}/api/chat`,
  PRE_REGISTRATION: `${API_BASE_URL}/api/pre-registration`,
  STATISTICS: `${API_BASE_URL}/api/statistics`,
  CHECK_BLOCK: `${API_BASE_URL}/api/check-block`,
} as const;

// WebSocket 엔드포인트
export const WS_ENDPOINTS = {
  CHAT: (characterId: string) => `${WS_BASE_URL}/ws/chat/${characterId}`,
} as const;
