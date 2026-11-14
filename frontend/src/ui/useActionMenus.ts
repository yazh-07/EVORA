import { useEffect } from 'react';

/** Native disclosures retain keyboard behavior; task menus close after an action. */
export function useActionMenus() {
  useEffect(() => {
    const openMenus = () => document.querySelectorAll<HTMLDetailsElement>('.action-menu[open]');
    const position = (event: Event) => {
      const menu = event.target;
      if (!(menu instanceof HTMLDetailsElement) || !menu.matches('.action-menu')) return;
      const popover = menu.querySelector<HTMLElement>('.action-popover');
      if (!popover) return;
      if (!menu.open) { delete popover.dataset.positioned; return; }
      const anchor = menu.querySelector('summary')?.getBoundingClientRect();
      if (!anchor) return;
      const box = popover.getBoundingClientRect(), gap = 8;
      const left = Math.max(gap, Math.min(anchor.left, innerWidth - box.width - gap));
      const below = anchor.bottom + 6;
      const top = below + box.height <= innerHeight - gap ? below
        : Math.max(gap, anchor.top - box.height - 6);
      popover.style.left = `${left}px`; popover.style.top = `${top}px`;
      popover.dataset.positioned = '';
    };
    const closeOnMove = (event: Event) => {
      if (event.target instanceof Element && event.target.closest('.action-popover')) return;
      openMenus().forEach(menu => { menu.open = false; });
    };
    const closeOutside = (event: PointerEvent) => document.querySelectorAll<HTMLDetailsElement>('.action-menu[open]').forEach(menu => { if (!menu.contains(event.target as Node)) menu.open = false; });
    const closeAction = (event: MouseEvent) => { const target = event.target as Element; if (target.closest('button')) { const menu = target.closest<HTMLDetailsElement>('.action-menu'); if (menu) menu.open = false; } };
    const escape = (event: KeyboardEvent) => { if (event.key !== 'Escape') return; const menus = [...openMenus()]; const menu = menus.at(-1); if (menu) { event.preventDefault(); event.stopPropagation(); menu.open = false; menu.querySelector('summary')?.focus({ preventScroll: true }); } };
    document.addEventListener('toggle', position, true); document.addEventListener('scroll', closeOnMove, true); window.addEventListener('resize', closeOnMove);
    document.addEventListener('pointerdown', closeOutside); document.addEventListener('click', closeAction); document.addEventListener('keydown', escape, true);
    return () => { document.removeEventListener('pointerdown', closeOutside); document.removeEventListener('click', closeAction); document.removeEventListener('keydown', escape, true); document.removeEventListener('toggle', position, true); document.removeEventListener('scroll', closeOnMove, true); window.removeEventListener('resize', closeOnMove); };
  }, []);
}
