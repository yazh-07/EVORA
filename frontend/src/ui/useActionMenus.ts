import { useEffect } from 'react';

/** Native disclosures retain keyboard behavior; task menus close after an action. */
export function useActionMenus() {
  useEffect(() => {
    const closeOutside = (event: PointerEvent) => document.querySelectorAll<HTMLDetailsElement>('.action-menu[open]').forEach(menu => { if (!menu.contains(event.target as Node)) menu.open = false; });
    const closeAction = (event: MouseEvent) => { const target = event.target as Element; if (target.closest('button')) { const menu = target.closest<HTMLDetailsElement>('.action-menu'); if (menu) menu.open = false; } };
    const escape = (event: KeyboardEvent) => { if (event.key !== 'Escape') return; const menus = [...document.querySelectorAll<HTMLDetailsElement>('.action-menu[open]')]; const menu = menus.at(-1); if (menu) { event.preventDefault(); event.stopPropagation(); menu.open = false; menu.querySelector('summary')?.focus(); } };
    document.addEventListener('pointerdown', closeOutside); document.addEventListener('click', closeAction); document.addEventListener('keydown', escape, true);
    return () => { document.removeEventListener('pointerdown', closeOutside); document.removeEventListener('click', closeAction); document.removeEventListener('keydown', escape, true); };
  }, []);
}
