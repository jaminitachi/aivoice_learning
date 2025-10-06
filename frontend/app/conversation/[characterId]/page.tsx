"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Mic, StopCircle, User, ChevronLeft } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { API_ENDPOINTS } from "@/utils/config";

// --- 타입 정의 ---
interface Message {
  speaker: "user" | "ai";
  text: string;
  imageUrl?: string; // AI 메시지의 경우 해당 감정 이미지
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
export default function ConversationPage({ params }: ChatPageProps) {
  const { characterId } = params;

  // --- 상태 관리 ---
  const [character, setCharacter] = useState<Character | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [completedSessionId, setCompletedSessionId] = useState<string | null>(
    null
  );
  const [isSessionCompleted, setIsSessionCompleted] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioBuffersRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const sessionCompletedRef = useRef(false); // 세션 완료 플래그 (즉시 참조용)
  const completedSessionIdRef = useRef<string | null>(null); // 세션 ID (즉시 참조용)

  // 메시지 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

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

  // 오디오 스트림 재생
  const playAudioStream = useCallback(async () => {
    if (!audioContextRef.current || audioBuffersRef.current.length === 0)
      return;

    isPlayingRef.current = true;

    try {
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

      const audioBuffer = await audioContextRef.current.decodeAudioData(
        combined.buffer
      );
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);

      source.onended = () => {
        isPlayingRef.current = false;
        console.log("🎵 TTS 재생 완료!");

        // TTS 재생 완료 후 세션이 완료된 경우 모달 표시
        if (sessionCompletedRef.current && completedSessionIdRef.current) {
          console.log("✅ 세션 완료! 모달 표시");
          setShowCompletionModal(true);
        }
      };

      source.start(0);
    } catch (error) {
      console.error("오디오 재생 오류:", error);
      isPlayingRef.current = false;
    }
  }, []);

  // WebSocket 메시지 처리
  const handleWebSocketMessage = useCallback(
    async (data: WebSocketMessage) => {
      switch (data.type) {
        case "connected":
          // 연결 성공 시 초기 메시지 표시
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
          audioBuffersRef.current = [];
          if (!audioContextRef.current) {
            audioContextRef.current = new AudioContext();
          }
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

        case "stt_result":
          // 사용자 메시지 추가
          setMessages((prev) => [
            ...prev,
            { speaker: "user", text: data.text },
          ]);
          break;

        case "llm_result":
          // AI 메시지 추가 (이미지 나중에 업데이트)
          setMessages((prev) => [
            ...prev,
            { speaker: "ai", text: data.text, imageUrl: undefined },
          ]);
          break;

        case "character_image":
          // 마지막 AI 메시지에 이미지 추가
          setMessages((prev) => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].speaker === "ai" && !updated[i].imageUrl) {
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
            // TTS 재생이 끝나면 source.onended에서 모달 표시됨
          }
          break;

        case "session_completed":
          // 10턴 완료 상태 저장 (모달은 TTS 재생 완료 후 표시)
          console.log("📤 session_completed 이벤트 수신!");
          setIsSessionCompleted(true);
          sessionCompletedRef.current = true;
          setCompletedSessionId(data.session_id);
          completedSessionIdRef.current = data.session_id;
          setIsLoading(false);
          console.log(
            "✅ 세션 완료 상태 저장됨. TTS 재생 완료 후 모달 표시 예정"
          );
          break;

        case "error":
          console.error("WebSocket error:", data.message);
          setIsLoading(false);
          setMessages((prev) => [
            ...prev,
            {
              speaker: "ai",
              text: "Sorry, an error occurred. Please try again.",
            },
          ]);
          break;
      }
    },
    [playAudioStream, isSessionCompleted]
  );

  // WebSocket 연결 설정
  useEffect(() => {
    if (!character) return;

    const connectWebSocket = () => {
      const ws = new WebSocket(`ws://localhost:8000/ws/chat/${characterId}`);

      ws.onopen = () => {
        console.log("WebSocket connected");
        // 초기 메시지는 서버의 'connected' 이벤트에서 처리됨
      };

      ws.onmessage = async (event) => {
        const data: WebSocketMessage = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        // 세션 완료 전에는 재연결 시도 안 함 (의도적 종료)
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    return () => {
      // cleanup 시 WebSocket 닫기
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [character, characterId]);

  const sendAudioToBackend = async (audioBlob: Blob) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      alert("연결이 끊어졌습니다. 페이지를 새로고침 해주세요.");
      return;
    }

    setIsLoading(true);

    try {
      // Blob을 Base64로 변환
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = () => {
        const base64Audio = reader.result as string;
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

  const handleRecord = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        streamRef.current = stream;
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (event) =>
          audioChunksRef.current.push(event.data);

        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(audioChunksRef.current, {
            type: "audio/webm",
          });
          sendAudioToBackend(audioBlob);
          stream.getTracks().forEach((track) => track.stop());
        };

        mediaRecorder.start();
        setIsRecording(true);
      } catch (error) {
        alert("마이크에 접근할 수 없습니다. 브라우저 설정을 확인해주세요.");
      }
    }
  };

  return (
    <div className="relative bg-black">
      {/* 배경 패턴 효과 */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/20 via-transparent to-transparent"></div>
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40"></div>

      <div className="relative w-full max-w-[390px] mx-auto flex rounded-3xl flex-col h-screen text-white bg-gradient-to-br from-slate-950 via-purple-950 to-slate-900">
        {/* 헤더 - 글래스모피즘 효과 */}
        <header className="relative backdrop-blur-xl bg-white/5 border-b border-white/10 shadow-lg">
          <div className="flex items-center pt-2 pb-2 px-4">
            <Link
              href={`/chat/${characterId}`}
              className="mr-4 p-2 rounded-full hover:bg-white/10 transition-all duration-300 hover:scale-110"
            >
              <ChevronLeft className="w-6 h-6" />
            </Link>
            {character && (
              <div className="flex items-center">
                <div className="relative w-12 h-12 rounded-full overflow-hidden mr-3 ring-2 ring-purple-400/50 ring-offset-2 ring-offset-transparent">
                  <Image
                    src={character.imageUrl}
                    alt={character.name}
                    fill
                    style={{ objectFit: "cover" }}
                    unoptimized
                  />
                  {/* 온라인 상태 인디케이터 */}
                  <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-400 rounded-full border-2 border-slate-900 "></div>
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
        </header>

        {/* 대화 내용 */}
        <div className="flex-grow overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-purple-500/50 scrollbar-track-transparent">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`animate-fadeInUp ${
                msg.speaker === "user"
                  ? "flex justify-end"
                  : "flex flex-col items-start"
              }`}
              style={{ animationDelay: `${index * 0.1}s` }}
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
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 녹음 버튼 - 업그레이드된 디자인 */}
        <div className="relative backdrop-blur-xl bg-white/5 border-t border-white/10 p-4">
          <div className="flex justify-center items-center">
            {/* 녹음 중 웨이브 애니메이션 */}
            {isRecording && (
              <>
                <div className="absolute w-32 h-32 rounded-full bg-red-500/30 animate-ping"></div>
                <div className="absolute w-28 h-28 rounded-full bg-red-500/20 animate-pulse"></div>
              </>
            )}

            <button
              onClick={handleRecord}
              disabled={isLoading}
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
          <div className="mt-4 text-center">
            <p className="text-sm text-purple-300/80">
              {isRecording
                ? "녹음 중... 버튼을 눌러 종료"
                : isLoading
                ? "처리 중..."
                : "버튼을 눌러 말하기"}
            </p>
          </div>
        </div>
      </div>

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
