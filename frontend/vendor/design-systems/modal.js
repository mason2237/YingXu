// Adapted from Overture's modal lifecycle. MIT © 2026 DayDreamInAReverie.
// Changes: remove sample business, sound/GPU dependencies; use short motion,
// track focus, and handle an interrupted exit without closing a reopened modal.
export function modal(dialog, {reduced = () => false, drawer = false, onClose = () => {}, focusFallback = () => {}} = {}) {
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
    if (!reduced()) dialog.animate([
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
    const exit = immediate || reduced() ? Promise.resolve() : dialog.animate([
      {opacity: 1, transform: 'none'}, {opacity: 0, transform: drawer ? 'translateX(16px)' : 'translateY(4px)'},
    ], {duration: 110, easing: 'ease-in', fill: 'forwards'}).finished.catch(() => {});
    closing = exit.then(() => {
      if (current !== generation) return;
      closing = null;
      if (dialog.open) dialog.close();
      dialog.getAnimations().forEach(animation => animation.cancel());
    });
    return closing;
  }
  dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close();
  });
  dialog.addEventListener('close', () => {
    closing = null; dialog.classList.remove('is-closing');
    if (opener?.isConnected && opener !== document.body) opener.focus();
    else focusFallback();
    onClose();
    document.dispatchEvent(new CustomEvent('yingxu:overlay'));
  });
  dialog.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', close));
  return {open, close};
}
