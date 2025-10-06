"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, StopCircle, User, ChevronLeft } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { API_ENDPOINTS, WS_ENDPOINTS } from "@/utils/config";
import router from "next/router";

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

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // 오디오 스트리밍 관련
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioBuffersRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);

  // Init 오디오 전용 버퍼
  const initAudioBuffersRef = useRef<ArrayBuffer[]>([]);
  const isPlayingInitRef = useRef(false);

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

        // ✅ Fingerprint 생성 및 전송
        const fingerprint = await generateFingerprint();
        ws.send(
          JSON.stringify({
            type: "init",
            fingerprint: fingerprint,
          })
        );
        console.log("📤 Fingerprint 전송 완료");
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
        // 자동 재연결 (5초 후)
        setTimeout(() => {
          if (wsRef.current?.readyState !== WebSocket.OPEN) {
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
        break;

      case "init_audio_stream_start":
        // 초기 메시지 오디오 스트리밍 시작
        console.log("🎵 Init 오디오 스트리밍 시작");
        initAudioBuffersRef.current = [];
        isPlayingInitRef.current = false;
        if (!audioContextRef.current) {
          audioContextRef.current = new AudioContext();
        }
        break;

      case "init_audio_chunk":
        // 초기 메시지 오디오 청크 수신 및 재생
        const initChunkData = atob(data.data);
        const initChunkArray = new Uint8Array(initChunkData.length);
        for (let i = 0; i < initChunkData.length; i++) {
          initChunkArray[i] = initChunkData.charCodeAt(i);
        }
        initAudioBuffersRef.current.push(initChunkArray.buffer);
        console.log(
          `🎵 Init 오디오 청크 수신 (${initAudioBuffersRef.current.length}개)`
        );

        // 첫 청크부터 즉시 재생 시작
        if (
          !isPlayingInitRef.current &&
          initAudioBuffersRef.current.length > 0
        ) {
          playInitAudioStream();
        }
        break;

      case "init_audio_stream_end":
        // 초기 메시지 오디오 스트리밍 완료
        console.log("✅ 초기 메시지 음성 스트리밍 완료");
        break;

      case "status":
        setStatusMessage(data.message);
        break;

      case "turn_count_update":
        setTurnCount(data.turn_count);
        break;

      case "session_completed":
        setIsSessionCompleted(true);
        setSessionId(data.session_id);
        // 로딩은 audio_stream_end에서 자동으로 꺼짐
        // 피드백 페이지로 리다이렉트
        setTimeout(() => {
          window.location.href = `/feedback/${data.session_id}`;
        }, 2000);
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
        if (!audioContextRef.current) {
          audioContextRef.current = new AudioContext();
        }
        break;

      case "audio_chunk":
        // 오디오 청크 수신 및 재생
        const chunkData = atob(data.data); // base64 디코딩
        const chunkArray = new Uint8Array(chunkData.length);
        for (let i = 0; i < chunkData.length; i++) {
          chunkArray[i] = chunkData.charCodeAt(i);
        }
        audioBuffersRef.current.push(chunkArray.buffer);

        // 첫 청크부터 즉시 재생 시작
        if (!isPlayingRef.current && audioBuffersRef.current.length > 0) {
          playAudioStream();
        }
        break;

      case "audio_stream_end":
        setIsLoading(false);
        setStatusMessage("");
        break;

      case "blocked":
        // 차단된 경우 - 깨끗한 알림창과 홈으로 이동
        console.warn("🚫 사용자 차단:", data.message);
        setStatusMessage("");
        setIsLoading(false);
        alert(data.message);
        router.push("/");
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

  // 오디오 스트림 재생 (일반 메시지용)
  const playAudioStream = async () => {
    if (!audioContextRef.current || audioBuffersRef.current.length === 0)
      return;

    isPlayingRef.current = true;

    try {
      // 모든 청크를 하나로 합치기
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

      // AudioContext로 디코딩 및 재생
      const audioBuffer = await audioContextRef.current.decodeAudioData(
        combined.buffer
      );
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);

      source.onended = () => {
        isPlayingRef.current = false;
      };

      source.start(0);
    } catch (error) {
      console.error("오디오 재생 오류:", error);
      isPlayingRef.current = false;
    }
  };

  // Init 오디오 스트림 재생 (초기 메시지용)
  const playInitAudioStream = async () => {
    if (!audioContextRef.current || initAudioBuffersRef.current.length === 0) {
      console.log("⚠️ Init 오디오 재생 불가: AudioContext 또는 버퍼 없음");
      return;
    }

    isPlayingInitRef.current = true;
    console.log(
      `🎵 Init 오디오 재생 시작 (청크 ${initAudioBuffersRef.current.length}개)`
    );

    try {
      // 모든 청크를 하나로 합치기
      const totalLength = initAudioBuffersRef.current.reduce(
        (acc, arr) => acc + arr.byteLength,
        0
      );
      const combined = new Uint8Array(totalLength);
      let offset = 0;

      for (const buffer of initAudioBuffersRef.current) {
        combined.set(new Uint8Array(buffer), offset);
        offset += buffer.byteLength;
      }

      console.log(`🎵 Init 오디오 디코딩 중 (${totalLength} bytes)...`);

      // AudioContext로 디코딩 및 재생
      const audioBuffer = await audioContextRef.current.decodeAudioData(
        combined.buffer
      );
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);

      source.onended = () => {
        isPlayingInitRef.current = false;
        console.log("✅ Init 오디오 재생 완료");
      };

      source.start(0);
      console.log("🎵 Init 오디오 재생 중...");
    } catch (error) {
      console.error("❌ Init 오디오 재생 오류:", error);
      isPlayingInitRef.current = false;
    }
  };

  // 녹음 시작
  const startRecording = async () => {
    if (connectionStatus !== "connected") {
      alert("WebSocket이 연결되지 않았습니다. 잠시 후 다시 시도해주세요.");
      return;
    }

    try {
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
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-blue-50 to-white">
        <p className="text-gray-600">캐릭터 정보를 불러오는 중...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex flex-col">
      {/* 헤더 */}
      <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
            <span className="font-medium">돌아가기</span>
          </Link>
          <h1 className="text-xl font-bold text-gray-900">
            {character.name}와의 대화
          </h1>
          <div
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              connectionStatus === "connected"
                ? "bg-green-100 text-green-700"
                : connectionStatus === "connecting"
                ? "bg-yellow-100 text-yellow-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {connectionStatus === "connected"
              ? "연결됨"
              : connectionStatus === "connecting"
              ? "연결 중..."
              : "연결 끊김"}
          </div>
        </div>

        {/* 턴 카운터 */}
        <div className="mt-3 flex items-center justify-center gap-4">
          <div className="flex items-center gap-2">
            <div className="text-sm text-gray-600">대화 진행:</div>
            <div className="flex items-center gap-1">
              {Array.from({ length: maxTurns }).map((_, idx) => (
                <div
                  key={idx}
                  className={`w-3 h-3 rounded-full ${
                    idx < turnCount ? "bg-blue-500" : "bg-gray-300"
                  }`}
                  title={`${idx + 1}턴`}
                />
              ))}
            </div>
            <div className="text-sm font-semibold text-gray-900">
              {turnCount}/{maxTurns}
            </div>
          </div>
        </div>
      </header>

      {/* 대화 영역 */}
      <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6">
        {/* 세션 완료 메시지 */}
        {isSessionCompleted && (
          <div className="bg-green-50 border-2 border-green-500 rounded-xl p-6 text-center mb-6 animate-pulse">
            <h2 className="text-xl font-bold text-green-800 mb-2">
              🎉 대화가 완료되었습니다!
            </h2>
            <p className="text-green-700 mb-4">
              잠시 후 피드백 페이지로 이동합니다...
            </p>
            <div className="flex items-center justify-center gap-2">
              <div className="w-2 h-2 bg-green-600 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-green-600 rounded-full animate-bounce delay-75"></div>
              <div className="w-2 h-2 bg-green-600 rounded-full animate-bounce delay-150"></div>
            </div>
          </div>
        )}

        {messages.length === 0 && !isLoading && !isSessionCompleted && (
          <div className="text-center text-gray-500 mt-12">
            <p className="text-lg">마이크 버튼을 눌러 대화를 시작하세요</p>
            <p className="text-sm mt-2">
              10번의 대화 후 피드백을 받을 수 있습니다
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-4 ${
              msg.speaker === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {msg.speaker === "ai" && (
              <div className="flex-shrink-0">
                {msg.imageUrl ? (
                  <Image
                    src={msg.imageUrl}
                    alt={character.name}
                    width={48}
                    height={48}
                    className="rounded-full object-cover"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white font-semibold">
                    AI
                  </div>
                )}
              </div>
            )}

            <div
              className={`max-w-md px-4 py-3 rounded-2xl shadow-sm ${
                msg.speaker === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-white text-gray-800 border border-gray-200"
              }`}
            >
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {msg.text}
              </p>
            </div>

            {msg.speaker === "user" && (
              <div className="flex-shrink-0">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center">
                  <User className="w-6 h-6 text-white" />
                </div>
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-4 justify-start">
            <div className="flex-shrink-0">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white font-semibold">
                AI
              </div>
            </div>
            <div className="max-w-md px-4 py-3 rounded-2xl bg-white border border-gray-200 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-75"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-150"></div>
                {statusMessage && (
                  <p className="ml-2 text-sm text-gray-600">{statusMessage}</p>
                )}
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 녹음 버튼 */}
      <div className="bg-white border-t border-gray-200 px-6 py-6">
        <div className="max-w-2xl mx-auto flex justify-center">
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={
              isLoading ||
              connectionStatus !== "connected" ||
              isSessionCompleted
            }
            className={`group relative w-20 h-20 rounded-full flex items-center justify-center transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${
              isRecording
                ? "bg-red-500 shadow-lg shadow-red-500/50"
                : "bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/50"
            }`}
          >
            {isRecording ? (
              <StopCircle className="w-10 h-10 text-white" />
            ) : (
              <Mic className="w-10 h-10 text-white" />
            )}

            {isRecording && (
              <span className="absolute -top-2 -right-2 w-4 h-4 bg-red-500 rounded-full animate-ping"></span>
            )}
          </button>
        </div>
        <p className="text-center text-sm text-gray-500 mt-4">
          {isSessionCompleted
            ? "대화가 완료되었습니다"
            : isRecording
            ? "녹음 중... 버튼을 다시 눌러 전송하세요"
            : connectionStatus === "connected"
            ? "마이크 버튼을 눌러 말하기"
            : "WebSocket 연결 대기 중..."}
        </p>
      </div>
    </div>
  );
}
