import { useState, useEffect } from "react";
import { LogOut, Mic, MicOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import TranscriptPanel from "@/components/ui/transcript-panel";
import Settings from "@/components/ui/settings";

import useRealTime from "@/hooks/useRealtime";
import useAudioRecorder from "@/hooks/useAudioRecorder";
import useAudioPlayer from "@/hooks/useAudioPlayer";

import { ExtensionMiddleTierToolResponse } from "./types";

import { ThemeProvider, useTheme } from "./context/theme-context";
import { AuthProvider, useAuth } from "@/context/auth-context";
import StatusMessage from "./components/ui/status-message";

function App() {
    const [isRecording, setIsRecording] = useState(false);
    const [isMobile, setIsMobile] = useState(false);
    const { theme } = useTheme();
    const { logout, authEnabled } = useAuth();

    const [transcripts, setTranscripts] = useState<Array<{ text: string; isUser: boolean; timestamp: Date }>>(() => {
        return [];
    });

    const realtime = useRealTime({
        enableInputAudioTranscription: true,
        onWebSocketOpen: () => console.log("WebSocket connection opened"),
        onWebSocketClose: () => console.log("WebSocket connection closed"),
        onWebSocketError: event => console.error("WebSocket error:", event),
        onReceivedError: message => console.error("error", message),
        onReceivedResponseAudioDelta: message => {
            isRecording && playAudio(message.delta);
        },
        onReceivedInputAudioBufferSpeechStarted: () => {
            stopAudioPlayer();
        },
        onReceivedExtensionMiddleTierToolResponse: ({ tool_name, tool_result }: ExtensionMiddleTierToolResponse) => {
            if (tool_name === "update_order") {
                console.log(JSON.parse(tool_result));
            }
        },
        onReceivedInputAudioTranscriptionCompleted: message => {
            const newTranscriptItem = {
                text: message.transcript,
                isUser: true,
                timestamp: new Date()
            };
            setTranscripts(prev => [...prev, newTranscriptItem]);
        },
        onReceivedResponseDone: message => {
            const transcript = message.response.output.map(output => output.content?.map(content => content.transcript).join(" ")).join(" ");
            if (!transcript) return;

            const newTranscriptItem = {
                text: transcript,
                isUser: false,
                timestamp: new Date()
            };
            setTranscripts(prev => [...prev, newTranscriptItem]);
        }
    });

    const { reset: resetAudioPlayer, play: playAudio, stop: stopAudioPlayer } = useAudioPlayer();
    const { start: startAudioRecording, stop: stopAudioRecording } = useAudioRecorder({
        onAudioRecorded: realtime.addUserAudio
    });

    const onToggleListening = async () => {
        if (!isRecording) {
            realtime.startSession();
            await startAudioRecording();
            resetAudioPlayer();
            setIsRecording(true);
        } else {
            await stopAudioRecording();
            stopAudioPlayer();
            realtime.inputAudioBufferClear();
            setIsRecording(false);
        }
    };

    const { t } = useTranslation();

    useEffect(() => {
        const checkMobile = () => {
            setIsMobile(window.innerWidth < 768);
        };
        checkMobile();
        window.addEventListener("resize", checkMobile);
        return () => window.removeEventListener("resize", checkMobile);
    }, []);

    return (
        <div className={`min-h-screen bg-background p-4 text-foreground ${theme}`}>
            <div className="mx-auto flex max-w-2xl flex-col items-center justify-center">
                <div className="relative mb-6 w-full flex flex-col items-center">
                    <h1 className="bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-center text-4xl font-bold text-transparent md:text-6xl">
                        Voice Chat
                    </h1>
                    <div className="absolute right-0 top-1/2 flex -translate-y-1/2 transform items-center gap-2">
                        <Settings isMobile={isMobile} />
                        {authEnabled && (
                            <Button variant="ghost" size="icon" className="rounded-full" onClick={logout} title="Logout">
                                <LogOut className="h-4 w-4" />
                            </Button>
                        )}
                    </div>
                </div>

                <Card className="w-full max-w-2xl p-8 flex flex-col items-center">
                    {/* Recording Button */}
                    <Button
                        onClick={onToggleListening}
                        className={`mb-6 h-12 w-60 ${isRecording ? "bg-red-600 hover:bg-red-700" : "bg-purple-500 hover:bg-purple-600"}`}
                        aria-label={isRecording ? t("app.stopRecording") : t("app.startRecording")}
                    >
                        {isRecording ? (
                            <>
                                <MicOff className="mr-2 h-4 w-4" />
                                {t("app.stopConversation")}
                            </>
                        ) : (
                            <>
                                <Mic className="mr-2 h-6 w-6" />
                            </>
                        )}
                    </Button>
                    <StatusMessage isRecording={isRecording} />

                    {/* Transcript Panel */}
                    <div className="mt-8 w-full">
                        <h2 className="mb-4 text-center font-semibold">Transcript</h2>
                        <div className="h-[400px] overflow-auto rounded-md p-4">
                            <TranscriptPanel transcripts={transcripts} />
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
}

// Main app component with authentication wrapper
function AppWrapper() {
    const { isAuthenticated, isLoading, authEnabled } = useAuth();

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <div className="text-center">
                    <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
                    <p className="text-lg">Loading...</p>
                </div>
            </div>
        );
    }

    if (!isAuthenticated && authEnabled) {
        return null; // Auth provider will handle redirect
    }

    return <App />;
}

export default function RootApp() {
    return (
        <AuthProvider>
            <ThemeProvider>
                <AppWrapper />
            </ThemeProvider>
        </AuthProvider>
    );
}
