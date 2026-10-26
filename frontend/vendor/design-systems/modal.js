// Adapted from Overture's modal lifecycle. MIT © 2026 DayDreamInAReverie.
// Changes: remove sample business, sound/GPU dependencies; use short motion,
// track focus, and handle an interrupted exit without closing a reopened modal.
import {isDesktopHost} from '../../js/channel.js';
export function modal(dialog, {reduced = () => false, drawer = false, fadeClose = false, onClose = () => {}, focusFallback = () => {}} = {}) {
  // Qt/ANGLE must not allocate a whole-window blur/transform surface each
  // time a top-layer dialog opens. Settings close uses opacity only.
  const desktop = isDesktopHost;
  let opener = null;
  let closing = null;
  let generation = 0;
  function open(from = document.activeElement) {
    generation++; closing = null;
    dialog.getAnimations().forEach(animation => animation.cancel());
    dialog.classList.remove('is-closing');
    opener = from;
    if (!dialog.open) dialog.showModal();
    document.dispatchEvent(new CustomEvent('yingxu:overlay'));
    if (!reduced() && !desktop()) dialog.animate([
      {opacity: 0, transform: drawer ? 'translateX(24px)' : 'translateY(7px) scale(.99)'},
      {opacity: 1, transform: 'none'},
    ], {duration: 170, easing: 'cubic-bezier(.2,.8,.2,1)'});
    dialog.querySelector('[data-initial-focus]')?.focus();
  }
  function close({immediate = false} = {}) {
    if (!dialog.open) return Promise.resolve();
    if (closing) return closing;
    const current = generation;
    dialog.classList.add('is-closing');
    const fade = fadeClose && !immediate && !reduced() && !document.hidden;
    const instant = immediate || reduced() || document.hidden || (desktop() && !fade);
    const animation = instant ? null : dialog.animate(fade ? [{opacity:1},{opacity:0}] : [
      {opacity: 1, transform: 'none'}, {opacity: 0, transform: drawer ? 'translateX(16px)' : 'translateY(4px)'},
    ], {duration: fade ? 140 : 110, easing: 'ease-out', fill: 'forwards'});
    const exit = animation ? Promise.race([animation.finished.catch(()=>{}),new Promise(resolve=>setTimeout(resolve,240))]) : Promise.resolve();
    closing = exit.then(async () => {
      if (current !== generation) return;
      if (fade) await Promise.race([
        new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))),
        new Promise(resolve=>setTimeout(resolve,70)),
      ]);
      if (current !== generation) return;
      closing = null;
      if (dialog.open) dialog.close();
      dialog.getAnimations().forEach(animation => animation.cancel());
    });
    return closing;
  }
  dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || event.isComposing || event.target.matches?.('select:open')) return;
    event.preventDefault();event.stopPropagation();close();
  });
  if (desktop()) dialog.addEventListener('wheel', event => {
    if (!event.cancelable || event.ctrlKey || event.metaKey || event.altKey || !event.deltaY) return;
    // Keep small desktop overlay scrolls in the same main-thread commit as
    // their text. Chromium's independent fast-scroll layer can get ahead of
    // Qt's HDR source texture and expose unpainted tiles for a frame.
    let scroller = event.target instanceof Element ? event.target : dialog;
    while (scroller && dialog.contains(scroller)) {
      const style = getComputedStyle(scroller);
      if (/(auto|scroll)/.test(style.overflowY) && scroller.scrollHeight > scroller.clientHeight + 1) {
        const unit = event.deltaMode === 1 ? parseFloat(style.lineHeight) || 20 : event.deltaMode === 2 ? scroller.clientHeight : 1;
        event.preventDefault();
        scroller.scrollTop = Math.max(0, Math.min(scroller.scrollHeight - scroller.clientHeight, scroller.scrollTop + event.deltaY * unit));
        return;
      }
      if (scroller === dialog) break;
      scroller = scroller.parentElement;
    }
  }, {passive:false});
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close();
  });
  dialog.addEventListener('close', () => {
    if (dialog.open) return; // A queued close must not reset a reopened dialog.
    closing = null; dialog.classList.remove('is-closing');
    if (opener?.isConnected && opener !== document.body) opener.focus({preventScroll:true});
    else focusFallback();
    onClose();
    document.dispatchEvent(new CustomEvent('yingxu:overlay'));
  });
  dialog.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', close));
  return {open, close};
}
