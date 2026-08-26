"use client";

import { Loader2, Mic, Square, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Status = "idle" | "recording" | "transcribing";

/**
 * Voice intake control: records a short clip via the browser MediaRecorder API,
 * POSTs it to /voice/transcribe and hands the text back to the parent (which
 * fills the note field).
 *
 * Degrades gracefully:
 *  - If MediaRecorder / mic permission is unavailable, only the audio-file
 *    upload fallback is shown.
 *  - When the backend returns a stubbed transcription (`stub: true`), that is
 *    surfaced honestly rather than presented as a real transcription.
 */
export function VoiceCapture({
  onTranscribed,
  lang,
}: {
  onTranscribed: (text: string) => void;
  lang?: string;
}) {
  const { t } = useI18n();
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [wasStub, setWasStub] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canRecord =
    typeof window !== "undefined" &&
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof window.MediaRecorder !== "undefined";

  async function transcribe(blob: Blob) {
    setStatus("transcribing");
    setError(null);
    try {
      const res = await api.transcribeVoice(blob, lang);
      setWasStub(res.stub);
      onTranscribed(res.text);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.voice.error);
    } finally {
      setStatus("idle");
    }
  }

  async function startRecording() {
    setError(null);
    setWasStub(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        void transcribe(blob);
      };
      recorderRef.current = recorder;
      recorder.start();
      setStatus("recording");
    } catch {
      setError(t.voice.permissionDenied);
      setStatus("idle");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    recorderRef.current = null;
  }

  function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) void transcribe(file);
  }

  const busy = status === "transcribing";

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {canRecord &&
          (status === "recording" ? (
            <button
              type="button"
              onClick={stopRecording}
              className="inline-flex items-center gap-1.5 rounded-md border border-danger/40 bg-danger-surface px-3 py-1.5 text-xs font-medium text-danger"
            >
              <Square className="h-3.5 w-3.5" aria-hidden />
              {t.voice.stop}
            </button>
          ) : (
            <button
              type="button"
              onClick={startRecording}
              disabled={busy}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-surface-muted",
                "disabled:pointer-events-none disabled:opacity-50",
              )}
            >
              {busy ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Mic className="h-3.5 w-3.5" aria-hidden />
              )}
              {t.voice.record}
            </button>
          ))}

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={busy || status === "recording"}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-surface-muted",
            "disabled:pointer-events-none disabled:opacity-50",
          )}
        >
          <Upload className="h-3.5 w-3.5" aria-hidden />
          {t.voice.uploadFallback}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          className="hidden"
          onChange={onFilePicked}
        />

        {status === "recording" && (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-danger">
            <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
            {t.voice.recording}
          </span>
        )}
        {busy && (
          <span className="text-xs text-muted">{t.voice.transcribing}</span>
        )}
        {wasStub && <Badge tone="warning">{t.voice.stub}</Badge>}
      </div>

      {!canRecord && (
        <p className="text-[11px] text-muted">{t.voice.noRecorder}</p>
      )}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
