"use client";

import { useEffect, useRef } from "react";

/**
 * Keyboard shortcuts tuned for a five-minute consult: the doctor should never
 * have to reach for the mouse to move through a snapshot.
 *
 * Handlers are keyed by a lowercase `event.key`. Keys are deliberately NOT
 * captured while the user is typing (input / textarea / select / any
 * contenteditable host), or while a modifier is held, so nothing is hijacked.
 */

export type ShortcutMap = Record<string, (event: KeyboardEvent) => void>;

/** True when focus is somewhere the user could be typing. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useShortcuts(map: ShortcutMap, enabled = true): void {
  // Keep the latest handlers without re-binding the listener each render.
  const ref = useRef(map);
  ref.current = map;

  useEffect(() => {
    if (!enabled) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTypingTarget(event.target)) return;

      const handler = ref.current[event.key.toLowerCase()];
      if (!handler) return;
      event.preventDefault();
      handler(event);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
