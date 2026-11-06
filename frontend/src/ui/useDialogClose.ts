import { useCallback, useEffect, useRef } from 'react';
import type { RefObject } from 'react';

/** Keep the native dialog modal until its exit finishes; cancel safely on session teardown. */
export function useDialogClose(dialog: RefObject<HTMLDialogElement | null>, onClose: () => void) {
  const mounted = useRef(true);
  const animation = useRef<Animation | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; animation.current?.cancel(); animation.current = null; };
  }, []);
  return useCallback(() => {
    if (animation.current) return;
    const element = dialog.current;
    if (!element || typeof element.animate !== 'function' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      onClose(); return;
    }
    const exit = animation.current = element.animate(
      [{ opacity: getComputedStyle(element).opacity, transform: getComputedStyle(element).transform },
        { opacity: 0, transform: 'translateY(6px) scale(.99)' }],
      { duration: 140, easing: 'cubic-bezier(.4, 0, 1, 1)', fill: 'forwards' },
    );
    void exit.finished.then(() => { if (mounted.current) onClose(); }).catch(() => { /* Unmount cancels the exit. */ });
  }, [dialog, onClose]);
}
