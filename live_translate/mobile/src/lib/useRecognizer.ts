import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from "expo-speech-recognition";
import { useCallback, useLayoutEffect, useRef, useState } from "react";

/**
 * Sentence-by-sentence live recognition.
 *
 * iOS only marks results final when a continuous session stops, so instead of
 * one long continuous session we run single-utterance sessions and restart
 * after each one ends. Every finished utterance is handed to `onSentence`.
 */
export function useRecognizer(onSentence: (text: string, tag: string) => void) {
  const [listening, setListening] = useState(false);
  const [tag, setTag] = useState<string | null>(null); // which speaker/button is active
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);

  const wantRef = useRef<{ lang: string; tag: string } | null>(null);
  const pendingRef = useRef(""); // last interim text not yet committed
  const switchRef = useRef<{ lang: string; tag: string } | null>(null); // queued speaker switch
  const activeRef = useRef(false); // a native session is running
  const lastTagRef = useRef("A"); // survives stop() so the final sentence keeps its speaker
  const onSentenceRef = useRef(onSentence);
  useLayoutEffect(() => {
    onSentenceRef.current = onSentence;
  });

  const commit = (text: string) => {
    const t = text.trim();
    pendingRef.current = "";
    setInterim("");
    if (t) onSentenceRef.current(t, lastTagRef.current);
  };

  const begin = (lang: string) => {
    activeRef.current = true;
    ExpoSpeechRecognitionModule.start({
      lang,
      interimResults: true,
      continuous: false,
      addsPunctuation: true,
      maxAlternatives: 1,
    });
  };

  useSpeechRecognitionEvent("result", (ev) => {
    const text = ev.results[0]?.transcript ?? "";
    if (ev.isFinal) commit(text);
    else {
      pendingRef.current = text;
      setInterim(text);
    }
  });

  useSpeechRecognitionEvent("end", () => {
    activeRef.current = false;
    if (pendingRef.current) commit(pendingRef.current); // session ended without a final result
    if (switchRef.current) {
      wantRef.current = switchRef.current;
      lastTagRef.current = switchRef.current.tag;
      switchRef.current = null;
    }
    const want = wantRef.current;
    if (want) begin(want.lang); // keep listening: next sentence
    else setListening(false);
  });

  useSpeechRecognitionEvent("error", (ev) => {
    // "no-speech" / "speech-timeout" just mean silence: the "end" handler restarts.
    if (ev.error === "no-speech" || ev.error === "speech-timeout" || ev.error === "aborted") return;
    if (ev.error === "not-allowed" || ev.error === "service-not-allowed" || ev.error === "language-not-supported") {
      wantRef.current = null;
      setListening(false);
      setTag(null);
    }
    setError(ev.message || ev.error);
  });

  const start = useCallback(async (lang: string, newTag: string) => {
    setError(null);
    const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!perm.granted) {
      setError("沒有麥克風或語音辨識權限，請到系統設定中允許 LinguaLive。");
      return;
    }
    setTag(newTag);
    setListening(true);
    if (activeRef.current) {
      // finish the current sentence first; the "end" handler starts the new speaker
      switchRef.current = { lang, tag: newTag };
      ExpoSpeechRecognitionModule.stop();
      return;
    }
    wantRef.current = { lang, tag: newTag };
    lastTagRef.current = newTag;
    begin(lang);
  }, []);

  const stop = useCallback(() => {
    wantRef.current = null;
    switchRef.current = null;
    setTag(null);
    if (!activeRef.current) setListening(false);
    // stop() (not abort) so the last sentence still produces a final result
    ExpoSpeechRecognitionModule.stop();
  }, []);

  return { listening, tag, interim, error, start, stop };
}
