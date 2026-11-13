import { useEffect } from 'react';

const unsaved = new Set<symbol>();

/** Route changes keep hidden tab drafts; leaving their case or analysis must be explicit. */
export function confirmLeaveWorkspace(): boolean {
  return unsaved.size === 0 || window.confirm('This report has edits that have not been exported. Leave and discard these edits?');
}
export function useUnsavedChanges(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const key = Symbol('report');
    unsaved.add(key);
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', beforeUnload);
    return () => { unsaved.delete(key); window.removeEventListener('beforeunload', beforeUnload); };
  }, [dirty]);
}
