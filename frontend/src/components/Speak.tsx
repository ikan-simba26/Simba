/**
 * Read this step aloud (2026-10-14, approved by Raham; CLAUDE.md).
 *
 * The system's own speech voice, through the browser's `speechSynthesis`: no
 * bundled voice, no cloud, no dependency. English only — the button is not
 * shown when the system has no English voice, rather than reading English
 * words in another language's voice. Off by default: nothing is ever read
 * unless the button is pressed, and what is being read stops the moment the
 * step changes or the screen does.
 *
 * What is read is the step's own sentence, then the answers it offers, in
 * the words on the buttons (`SPEAK.answers` in `copy.ts`). The way to stop
 * the task is not read out: it is on every step and is not an answer.
 *
 * Pressing it is not counted as asking for help. That may be wrong — a person
 * who needs a step read to them may be finding it hard — and it is flagged
 * for the estimator's owner rather than decided here.
 */

import { useEffect, useState } from "react";

import type { StepPresented } from "@shared/schema";

import { SPEAK } from "../copy";

/** An English voice the system offers, or null. Voices load late on some
 *  systems, so this is re-read when the list changes. */
function useEnglishVoice(): SpeechSynthesisVoice | null {
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  useEffect(() => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synth) return;
    const pick = () => {
      const voices = synth.getVoices().filter((v) => v.lang.toLowerCase().startsWith("en"));
      // The system's default English voice if it has one, else its first.
      setVoice(voices.find((v) => v.default) ?? voices[0] ?? null);
    };
    pick();
    synth.addEventListener("voiceschanged", pick);
    return () => synth.removeEventListener("voiceschanged", pick);
  }, []);
  return voice;
}

/** The words to say for a step: its sentence, then what can be pressed. */
export function spokenFor(step: StepPresented): string {
  const answers = step.actions
    .filter((action) => action.kind !== "secondary")
    .map((action) => action.label);
  return [step.note ?? "", step.instruction, answers.length ? SPEAK.answers(answers) : ""]
    .filter(Boolean)
    .join(" ");
}

export function SpeakButton({ step }: { step: StepPresented | null }) {
  const voice = useEnglishVoice();
  const [speaking, setSpeaking] = useState(false);

  // A new step, or no step: whatever was being read stops.
  const key = step ? `${step.step_index}:${step.instruction}` : null;
  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel();
      setSpeaking(false);
    };
  }, [key]);

  if (!step || !voice) return null;

  const toggle = () => {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(spokenFor(step));
    utterance.voice = voice;
    utterance.lang = voice.lang;
    // A little slower than the system's default, for this audience.
    utterance.rate = 0.9;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    synth.speak(utterance);
  };

  // Smaller than the step's own buttons on purpose: it sits in the row above
  // the card, which has 48px, and it is not an answer to the step.
  return (
    <button type="button" onClick={toggle} aria-pressed={speaking} data-testid="speak"
            className="inline-flex h-11 items-center gap-2 rounded-full border border-line
                       bg-surface px-5 text-small font-semibold text-ink shadow-press
                       transition-colors duration-200 hover:bg-sunk
                       aria-pressed:border-accent aria-pressed:bg-tint">
      <SpeakerIcon />
      {speaking ? SPEAK.stop : SPEAK.read}
    </button>
  );
}

function SpeakerIcon() {
  return (
    <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" />
      <path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" />
    </svg>
  );
}
