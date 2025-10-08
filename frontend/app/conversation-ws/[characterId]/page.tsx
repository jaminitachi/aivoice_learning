"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, StopCircle, User, ChevronLeft } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { API_ENDPOINTS, WS_ENDPOINTS } from "@/utils/config";

// --- Fingerprint 생성 함수 ---
async function generateFingerprint(): Promise<string> {
  try {
    // Canvas Fingerprinting
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.textBaseline = "top";
      ctx.font = "14px Arial";
      ctx.fillStyle = "#f60";
      ctx.fillRect(125, 1, 62, 20);
      ctx.fillStyle = "#069";
      ctx.fillText("Browser Fingerprint", 2, 15);
      ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
      ctx.fillText("Canvas Fingerprint", 4, 17);
    }
    const canvasData = canvas.toDataURL();

    // 브라우저 환경 정보 수집
    const fingerprint = {
      canvas: canvasData,
      userAgent: navigator.userAgent,
      language: navigator.language,
      platform: navigator.platform,
      screenResolution: `${screen.width}x${screen.height}`,
      screenColorDepth: screen.colorDepth,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      deviceMemory: (navigator as any).deviceMemory || 0,
      hardwareConcurrency: navigator.hardwareConcurrency || 0,
    };

    // JSON 문자열로 변환
    const fingerprintString = JSON.stringify(fingerprint);

    // SHA-256 해시 생성
    const encoder = new TextEncoder();
    const data = encoder.encode(fingerprintString);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

    console.log("🔐 Fingerprint 생성:", hashHex.substring(0, 16) + "...");
    return hashHex;
  } catch (error) {
    console.error("Fingerprint 생성 오류:", error);
    // 오류 시 랜덤 ID 반환 (fallback)
    return "fallback-" + Math.random().toString(36).substring(2, 15);
  }
}

// --- 타입 정의 ---
interface Message {
  speaker: "user" | "ai";
  text: string;
  imageUrl?: string;
}

interface Character {
  id: string;
  name: string;
  imageUrl: string;
  init_message: string;
}

interface ChatPageProps {
  params: {
    characterId: string;
  };
}

// --- WebSocket 메시지 타입 ---
interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

// --- 메인 컴포넌트 ---
export default function ConversationWebSocketPage({ params }: ChatPageProps) {
  const { characterId } = params;

  // --- 상태 관리 ---
  const [character, setCharacter] = useState<Character | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "disconnected" | "connecting" | "connected"
  >("disconnected");
  const [statusMessage, setStatusMessage] = useState("");
  const [turnCount, setTurnCount] = useState(0);
  const [maxTurns, setMaxTurns] = useState(10);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isSessionCompleted, setIsSessionCompleted] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [completedSessionId, setCompletedSessionId] = useState<string | null>(
    null
  );
  const [audioInitialized, setAudioInitialized] = useState(false);
  const [showDifficultyModal, setShowDifficultyModal] = useState(false);
  const [selectedDifficulty, setSelectedDifficulty] = useState<string | null>(
    null
  );
  const [suggestedResponses, setSuggestedResponses] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const isSessionCompletedRef = useRef(false); // closure 문제 방지용 ref

  // 오디오 스트리밍 관련
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioBuffersRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const audioTimeoutRef = useRef<NodeJS.Timeout | null>(null); // TTS 타임아웃 추적

  // 메시지 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // 캐릭터 정보 로드
  useEffect(() => {
    const fetchCharacterInfo = async () => {
      try {
        const response = await fetch(API_ENDPOINTS.CHARACTERS);
        const characters: Character[] = await response.json();
        const currentChar = characters.find((c) => c.id === characterId);
        setCharacter(currentChar || null);
      } catch (error) {
        console.error("Failed to fetch character info:", error);
      }
    };
    fetchCharacterInfo();
  }, [characterId]);

  // 🎵 페이지 가시성 변경 감지 (모바일 중요!)
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

  // WebSocket 연결 설정
  useEffect(() => {
    if (!character) return;

    // WebSocket 연결
    const connectWebSocket = async () => {
      setConnectionStatus("connecting");
      const ws = new WebSocket(WS_ENDPOINTS.CHAT(characterId));

      ws.onopen = async () => {
        console.log("WebSocket connected");
        setConnectionStatus("connected");

        // Fingerprint와 난이도는 난이도 선택 후 전송됨
      };

      ws.onmessage = async (event) => {
        const data: WebSocketMessage = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setConnectionStatus("disconnected");
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        setConnectionStatus("disconnected");

        // 세션이 완료된 경우 재연결하지 않음
        if (isSessionCompletedRef.current) {
          console.log("✅ 세션 완료됨 - 재연결하지 않음");
          return;
        }

        // 자동 재연결 (5초 후)
        setTimeout(() => {
          if (
            wsRef.current?.readyState !== WebSocket.OPEN &&
            !isSessionCompletedRef.current
          ) {
            connectWebSocket();
          }
        }, 5000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    // 클린업
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      // 타임아웃 정리
      if (audioTimeoutRef.current) {
        clearTimeout(audioTimeoutRef.current);
        audioTimeoutRef.current = null;
      }
    };
  }, [character, characterId]);

  // WebSocket 메시지 처리
  const handleWebSocketMessage = async (data: WebSocketMessage) => {
    switch (data.type) {
      case "connected":
        console.log("Connected to character:", data.character_name);
        setSessionId(data.session_id);
        setMaxTurns(data.max_turns || 10);

        // 캐릭터의 초기 메시지 표시
        if (data.init_message) {
          setMessages([
            {
              speaker: "ai",
              text: data.init_message,
              imageUrl: character?.imageUrl,
            },
          ]);
        }

        // 난이도 선택 모달 표시 요청
        if (data.request_difficulty) {
          setShowDifficultyModal(true);
        }
        break;

      case "init_audio_stream_start":
        // 초기 메시지 오디오 스트리밍 시작
        console.log("🎵 Init 오디오 스트리밍 시작");
        audioBuffersRef.current = [];
        // AudioContext는 playAudioStream에서 생성됨
        break;

      case "init_audio_chunk":
        // 초기 메시지 오디오 청크 수신 및 버퍼에 저장
        const initChunkData = atob(data.data);
        const initChunkArray = new Uint8Array(initChunkData.length);
        for (let i = 0; i < initChunkData.length; i++) {
          initChunkArray[i] = initChunkData.charCodeAt(i);
        }
        audioBuffersRef.current.push(initChunkArray.buffer);
        break;

      case "init_audio_stream_end":
        // 초기 메시지 오디오 재생
        if (audioBuffersRef.current.length > 0) {
          playAudioStream();
        }
        break;

      case "status":
        setStatusMessage(data.message);
        break;

      case "turn_count_update":
        setTurnCount(data.turn_count);
        break;

      case "session_completed":
        console.log("📤 session_completed 이벤트 수신!");
        setIsSessionCompleted(true);
        isSessionCompletedRef.current = true; // ref도 업데이트
        setCompletedSessionId(data.session_id);
        setIsLoading(false);
        console.log(
          "✅ 세션 완료 상태 저장됨. TTS 재생 완료 후 모달 표시 예정"
        );
        break;

      case "stt_result":
        // 사용자 메시지 추가
        setMessages((prev) => [...prev, { speaker: "user", text: data.text }]);
        break;

      case "llm_result":
        // AI 메시지 추가
        setMessages((prev) => [...prev, { speaker: "ai", text: data.text }]);
        break;

      case "character_image":
        // 마지막 AI 메시지에 이미지 추가
        setMessages((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].speaker === "ai") {
              updated[i].imageUrl = data.image_url;
              break;
            }
          }
          return updated;
        });
        break;

      case "audio_stream_start":
        // 오디오 스트리밍 시작
        audioBuffersRef.current = [];
        // AudioContext는 playAudioStream에서 생성됨
        break;

      case "audio_chunk":
        // 오디오 청크 수신 및 버퍼에 저장
        const chunkData = atob(data.data);
        const chunkArray = new Uint8Array(chunkData.length);
        for (let i = 0; i < chunkData.length; i++) {
          chunkArray[i] = chunkData.charCodeAt(i);
        }
        audioBuffersRef.current.push(chunkArray.buffer);
        break;

      case "audio_stream_end":
        // 모든 청크를 받은 후 한 번에 재생
        setIsLoading(false);
        if (audioBuffersRef.current.length > 0) {
          playAudioStream();
        }
        break;

      case "suggested_responses":
        // 추천 멘트 수신
        if (data.suggestions && Array.isArray(data.suggestions)) {
          setSuggestedResponses(data.suggestions);
          console.log("💡 추천 멘트 수신:", data.suggestions);
        }
        break;

      case "error":
        console.error("WebSocket error:", data.message);
        setStatusMessage("");
        setIsLoading(false);
        alert(data.message);
        break;

      default:
        console.log("Unknown message type:", data.type);
    }
  };

  // AudioContext 초기화 및 재개 함수
  const ensureAudioContext = async () => {
    if (!audioContextRef.current) {
      // AudioContext 생성 (모바일 호환성을 위해 webkitAudioContext도 지원)
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

  // 오디오 스트림 재생
  const playAudioStream = async () => {
    // 기존 타임아웃 제거
    if (audioTimeoutRef.current) {
      clearTimeout(audioTimeoutRef.current);
      audioTimeoutRef.current = null;
    }

    if (audioBuffersRef.current.length === 0) {
      console.warn("⚠️ 재생할 오디오 버퍼가 없습니다");
      // 버퍼가 없어도 세션 완료 시 모달 표시
      if (isSessionCompletedRef.current) {
        console.log("✅ 세션 완료! 모달 표시 (버퍼 없음)");
        setShowCompletionModal(true);
      }
      return;
    }

    isPlayingRef.current = true;

    // 🔔 TTS 타임아웃 설정 (30초) - 재생이 너무 오래 걸리면 강제로 완료 처리
    audioTimeoutRef.current = setTimeout(() => {
      console.warn("⏰ TTS 재생 타임아웃 (30초)");
      isPlayingRef.current = false;

      if (isSessionCompletedRef.current) {
        console.log("✅ 세션 완료! 모달 표시 (타임아웃)");
        setShowCompletionModal(true);
      }
    }, 30000);

    try {
      // AudioContext 확보 및 재개
      const audioContext = await ensureAudioContext();

      const totalLength = audioBuffersRef.current.reduce(
        (acc, arr) => acc + arr.byteLength,
        0
      );
      const combined = new Uint8Array(totalLength);
      let offset = 0;

      for (const buffer of audioBuffersRef.current) {
        combined.set(new Uint8Array(buffer), offset);
        offset += buffer.byteLength;
      }

      console.log(`🎵 오디오 디코딩 시작 (${totalLength} bytes)`);
      const audioBuffer = await audioContext.decodeAudioData(combined.buffer);

      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);

      source.onended = () => {
        // 타임아웃 제거
        if (audioTimeoutRef.current) {
          clearTimeout(audioTimeoutRef.current);
          audioTimeoutRef.current = null;
        }

        isPlayingRef.current = false;
        console.log("🎵 TTS 재생 완료!");

        // TTS 재생 완료 후 세션이 완료된 경우 모달 표시
        if (isSessionCompletedRef.current) {
          console.log("✅ 세션 완료! 모달 표시");
          setShowCompletionModal(true);
        }
      };

      console.log("🎵 오디오 재생 시작");
      source.start(0);
    } catch (error) {
      console.error("❌ 오디오 재생 오류:", error);
      isPlayingRef.current = false;

      // 타임아웃 제거
      if (audioTimeoutRef.current) {
        clearTimeout(audioTimeoutRef.current);
        audioTimeoutRef.current = null;
      }

      // 재생 실패해도 세션 완료 시 모달 표시 (중요!)
      if (isSessionCompletedRef.current) {
        console.log("✅ 세션 완료! 모달 표시 (재생 오류 발생)");
        setShowCompletionModal(true);
      }

      // 사용자에게 알림
      alert(
        "음성 재생에 실패했습니다. 화면을 터치하여 오디오를 활성화해주세요."
      );
    }
  };

  // 녹음 시작
  const startRecording = async () => {
    if (connectionStatus !== "connected") {
      alert("WebSocket이 연결되지 않았습니다. 잠시 후 다시 시도해주세요.");
      return;
    }

    try {
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

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });
        await sendAudioToWebSocket(audioBlob);

        // 스트림 정리
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error("녹음 시작 실패:", error);
      alert("마이크 권한이 필요합니다.");
    }
  };

  // 녹음 중지
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // 난이도 선택 처리
  const handleDifficultySelect = async (difficulty: string) => {
    setSelectedDifficulty(difficulty);
    setShowDifficultyModal(false);

    console.log(`📚 난이도 선택: ${difficulty}`);

    // Fingerprint 생성 후 난이도와 함께 전송
    const fingerprint = await generateFingerprint();

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "init",
          fingerprint: fingerprint,
          difficulty: difficulty,
        })
      );
      console.log("📤 Fingerprint 및 난이도 전송 완료");
    }
  };

  // WebSocket으로 오디오 전송
  const sendAudioToWebSocket = async (audioBlob: Blob) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      alert("WebSocket이 연결되지 않았습니다.");
      return;
    }

    setIsLoading(true);

    try {
      // Blob을 Base64로 변환
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = () => {
        const base64Audio = reader.result as string;
        // "data:audio/webm;base64," 제거
        const base64Data = base64Audio.split(",")[1];

        // WebSocket으로 전송
        wsRef.current?.send(
          JSON.stringify({
            type: "audio",
            audio: base64Data,
          })
        );
      };
    } catch (error) {
      console.error("오디오 전송 실패:", error);
      setIsLoading(false);
    }
  };

  if (!character) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <p className="text-white">캐릭터 정보를 불러오는 중...</p>
      </div>
    );
  }

  return (
    <div className="relative bg-black">
      {/* 배경 패턴 효과 */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/20 via-transparent to-transparent"></div>
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40"></div>

      <div className="relative w-full max-w-[390px] mx-auto flex rounded-3xl flex-col h-screen text-white bg-gradient-to-br from-slate-950 via-purple-950 to-slate-900">
        {/* 헤더 - 글래스모피즘 효과 */}
        <header className="relative backdrop-blur-xl bg-white/5 border-b border-white/10 shadow-lg">
          <div className="relative flex items-center justify-center pt-2 pb-2 px-4">
            <Link
              href="/"
              className="absolute left-4 p-2 rounded-full hover:bg-white/10 transition-all duration-300 hover:scale-110"
            >
              <ChevronLeft className="w-6 h-6" />
            </Link>
            {character && (
              <div className="flex items-center">
                <div className="relative w-12 h-12 rounded-full overflow-hidden mr-3 ring-2 ring-purple-400/50">
                  <Image
                    src={character.imageUrl}
                    alt={character.name}
                    fill
                    style={{ objectFit: "cover" }}
                    unoptimized
                  />
                  {/* 온라인 상태 인디케이터 */}
                  <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-400 rounded-full border-2 border-slate-900"></div>
                </div>
                <div>
                  <h1 className="text-xl font-bold bg-gradient-to-r from-white to-purple-200 bg-clip-text text-transparent">
                    {character.name}
                  </h1>
                  <p className="text-xs text-purple-300">온라인</p>
                </div>
              </div>
            )}
          </div>

          {/* 턴 카운터 */}
          <div className="pb-2 flex flex-col items-center justify-center gap-1">
            <div className="flex items-center gap-2">
              <div className="text-sm text-purple-300">대화 진행:</div>
              <div className="flex items-center gap-1">
                {Array.from({ length: maxTurns }).map((_, idx) => (
                  <div
                    key={idx}
                    className={`w-3 h-3 rounded-full ${
                      idx < turnCount ? "bg-purple-500" : "bg-gray-700"
                    }`}
                    title={`${idx + 1}턴`}
                  />
                ))}
              </div>
              <div className="text-sm font-semibold text-white">
                {turnCount}/{maxTurns}
              </div>
            </div>
            <p className="text-[10px] text-purple-300/60">
              10번 대화 후 피드백을 받을 수 있습니다!
            </p>
          </div>
        </header>

        {/* 대화 영역 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-purple-500/50 scrollbar-track-transparent">
          {/* 초기 로딩 중일 때 캐릭터 이미지 먼저 표시 */}
          {messages.length === 0 && connectionStatus === "connecting" && (
            <div className="flex flex-col items-start animate-fadeInUp">
              <div className="relative w-full max-w-[320px] h-[400px] rounded-3xl overflow-hidden mb-3 shadow-2xl">
                <Image
                  src={character.imageUrl}
                  alt={character.name}
                  fill
                  style={{ objectFit: "cover" }}
                  unoptimized
                />
              </div>
              <div className="backdrop-blur-lg bg-white/10 border border-white/20 rounded-2xl p-4 max-w-[320px] shadow-xl">
                <div className="flex gap-2 items-center">
                  <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></span>
                  <span
                    className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></span>
                  <span
                    className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></span>
                  <p className="ml-2 text-sm text-purple-300">연결 중...</p>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`animate-fadeInUp ${
                msg.speaker === "user"
                  ? "flex justify-end"
                  : "flex flex-col items-start"
              }`}
              style={{ animationDelay: `${idx * 0.1}s` }}
            >
              {msg.speaker === "ai" ? (
                <>
                  {/* AI 메시지: 큰 이미지 위에 메시지 */}
                  {msg.imageUrl && (
                    <div className="relative w-full max-w-[320px] h-[400px] rounded-3xl overflow-hidden mb-3 shadow-2xl">
                      <Image
                        src={msg.imageUrl}
                        alt={character?.name || "Character"}
                        fill
                        style={{ objectFit: "cover" }}
                        unoptimized
                      />
                    </div>
                  )}
                  <div className="backdrop-blur-lg bg-white/10 border border-white/20 rounded-2xl p-4 max-w-[320px] shadow-xl transition-all duration-300 hover:scale-[1.02]">
                    <p className="leading-relaxed">{msg.text}</p>
                  </div>
                </>
              ) : (
                /* 사용자 메시지 */
                <div className="flex items-start gap-3">
                  <div className="bg-gradient-to-br from-purple-600 to-blue-600 text-white rounded-2xl p-4 max-w-[280px] shadow-xl transition-all duration-300 hover:scale-[1.02]">
                    <p className="leading-relaxed">{msg.text}</p>
                  </div>
                  <div className="w-10 h-10 rounded-full flex-shrink-0 bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center ring-2 ring-green-400/30">
                    <User className="w-6 h-6 text-white" />
                  </div>
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex flex-col items-start animate-fadeInUp">
              <div className="backdrop-blur-lg bg-white/10 border border-white/20 rounded-2xl p-4 max-w-md flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></span>
                  <span
                    className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></span>
                  <span
                    className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></span>
                </div>
                {statusMessage && (
                  <p className="ml-2 text-sm text-purple-300">
                    {statusMessage}
                  </p>
                )}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 녹음 버튼 - 업그레이드된 디자인 */}
        <div className="relative backdrop-blur-xl bg-white/5 border-t border-white/10 p-3">
          {/* 추천 멘트 영역 */}
          {suggestedResponses.length > 0 && (
            <div className="mb-3">
              {/* 토글 버튼 */}
              <button
                onClick={() => setShowSuggestions(!showSuggestions)}
                className="w-full flex items-center justify-center gap-2 py-2 text-purple-300 hover:text-purple-200 transition-colors text-sm"
              >
                <span>💡 추천 멘트 보기</span>
                <span
                  className={`transform transition-transform ${
                    showSuggestions ? "rotate-180" : ""
                  }`}
                >
                  ▼
                </span>
              </button>

              {/* 추천 멘트 리스트 */}
              {showSuggestions && (
                <div className="mt-2 space-y-2 animate-fadeInUp">
                  {suggestedResponses.map((suggestion, idx) => (
                    <button
                      key={idx}
                      className="w-full py-2 px-4 bg-gradient-to-r from-purple-600/20 to-blue-600/20 hover:from-purple-600/40 hover:to-blue-600/40 border border-purple-400/30 rounded-xl text-white text-sm text-left transition-all duration-200 hover:scale-[1.02]"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 구분선 */}
          {suggestedResponses.length > 0 && (
            <div className="border-t border-white/10 mb-3"></div>
          )}

          <div className="flex justify-center items-center">
            {/* 녹음 중 웨이브 애니메이션 */}
            {isRecording && (
              <>
                <div className="absolute w-32 h-32 rounded-full bg-red-500/30 animate-ping"></div>
                <div className="absolute w-28 h-28 rounded-full bg-red-500/20 animate-pulse"></div>
              </>
            )}

            <button
              onClick={isRecording ? stopRecording : startRecording}
              disabled={
                isLoading ||
                connectionStatus !== "connected" ||
                isSessionCompleted
              }
              className={`relative z-10 rounded-full p-4 transition-all duration-500 ease-out disabled:opacity-50 disabled:cursor-not-allowed shadow-2xl ${
                isRecording
                  ? "bg-gradient-to-br from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700 scale-110 animate-pulse"
                  : "bg-gradient-to-br from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 hover:scale-110"
              } ${
                !isLoading && !isRecording ? "hover:shadow-purple-500/50" : ""
              }`}
            >
              {/* 버튼 내부 글로우 효과 */}
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-white/20 to-transparent opacity-50"></div>

              {isRecording ? (
                <StopCircle size={18} className="relative animate-pulse" />
              ) : (
                <Mic size={20} className="relative" />
              )}
            </button>

            {/* 녹음 중 시각적 인디케이터 */}
            {isRecording && (
              <div className="absolute -bottom-2 flex gap-1">
                {[...Array(5)].map((_, i) => (
                  <div
                    key={i}
                    className="w-1 bg-red-400 rounded-full animate-soundWave"
                    style={{
                      height: "20px",
                      animationDelay: `${i * 0.1}s`,
                    }}
                  ></div>
                ))}
              </div>
            )}
          </div>

          {/* 힌트 텍스트 */}
          <div className="mt-2 text-center">
            <p className="text-xs text-purple-300/70">
              {isRecording
                ? "녹음 중... 버튼을 눌러 종료"
                : isLoading
                ? "처리 중..."
                : "버튼을 눌러 말하기"}
            </p>
          </div>
        </div>
      </div>

      {/* 난이도 선택 모달 */}
      {showDifficultyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-md mx-4 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 rounded-3xl border border-purple-400/30 shadow-2xl p-8 animate-fadeInUp">
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500/20 to-pink-500/20 rounded-3xl blur-2xl opacity-50"></div>

            <div className="relative">
              <h2 className="text-2xl font-bold text-center mb-3 bg-gradient-to-r from-white to-purple-200 bg-clip-text text-transparent">
                난이도를 선택하세요
              </h2>
              <p className="text-center text-purple-200 mb-8 text-sm">
                영어 수준에 맞는 난이도를 선택하면
                <br />더 효과적인 학습이 가능합니다
              </p>

              <div className="space-y-3">
                {/* 초급 */}
                <button
                  onClick={() => handleDifficultySelect("beginner")}
                  className="w-full py-4 px-6 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white font-bold rounded-2xl shadow-lg transition-all duration-300 hover:scale-105 active:scale-95 text-left"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-lg">🌱 초급 (Beginner)</div>
                      <div className="text-xs text-green-100 mt-1">
                        아주 쉬운 단어로 천천히 대화해요
                      </div>
                    </div>
                  </div>
                </button>

                {/* 중급 */}
                <button
                  onClick={() => handleDifficultySelect("intermediate")}
                  className="w-full py-4 px-6 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold rounded-2xl shadow-lg transition-all duration-300 hover:scale-105 active:scale-95 text-left"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-lg">🎯 중급 (Intermediate)</div>
                      <div className="text-xs text-blue-100 mt-1">
                        고등학교 수준의 자연스러운 대화
                      </div>
                    </div>
                  </div>
                </button>

                {/* 고급 */}
                <button
                  onClick={() => handleDifficultySelect("advanced")}
                  className="w-full py-4 px-6 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-2xl shadow-lg transition-all duration-300 hover:scale-105 active:scale-95 text-left"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-lg">🚀 고급 (Advanced)</div>
                      <div className="text-xs text-purple-100 mt-1">
                        원어민처럼 자유로운 표현으로
                      </div>
                    </div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 학습 완료 모달 */}
      {showCompletionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-md mx-4 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 rounded-3xl border border-purple-400/30 shadow-2xl p-8 animate-fadeInUp">
            {/* 배경 글로우 효과 */}
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500/20 to-pink-500/20 rounded-3xl blur-2xl opacity-50"></div>

            <div className="relative">
              {/* 체크 아이콘 */}
              <div className="flex justify-center mb-6">
                <div className="relative">
                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center shadow-xl shadow-green-500/50">
                    <svg
                      className="w-14 h-14 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={3}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                  {/* 펄스 애니메이션 */}
                  <div className="absolute inset-0 rounded-full bg-green-400/50 animate-ping"></div>
                </div>
              </div>

              {/* 텍스트 */}
              <h2 className="text-3xl font-bold text-center mb-3 bg-gradient-to-r from-white to-purple-200 bg-clip-text text-transparent">
                학습 완료!
              </h2>
              <p className="text-center text-purple-200 mb-8">
                10턴의 대화를 완료했습니다!
                <br />
                지금 바로 피드백을 확인하세요.
              </p>

              {/* 확인 버튼 */}
              <button
                onClick={() => {
                  if (completedSessionId) {
                    window.location.href = `/feedback/${completedSessionId}`;
                  }
                }}
                className="w-full py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-2xl shadow-lg shadow-purple-500/50 transition-all duration-300 hover:scale-105 active:scale-95"
              >
                피드백 확인하기
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes soundWave {
          0%,
          100% {
            height: 8px;
          }
          50% {
            height: 24px;
          }
        }

        .animate-fadeInUp {
          animation: fadeInUp 0.5s ease-out forwards;
        }

        .animate-soundWave {
          animation: soundWave 0.6s ease-in-out infinite;
        }

        /* 스크롤바 스타일링 */
        .scrollbar-thin::-webkit-scrollbar {
          width: 6px;
        }

        .scrollbar-thin::-webkit-scrollbar-track {
          background: transparent;
        }

        .scrollbar-thin::-webkit-scrollbar-thumb {
          background: rgba(168, 85, 247, 0.5);
          border-radius: 3px;
        }

        .scrollbar-thin::-webkit-scrollbar-thumb:hover {
          background: rgba(168, 85, 247, 0.7);
        }
      `}</style>
    </div>
  );
}
