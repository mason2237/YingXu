// Adapted from Overture 1.3 motion.transition / focusPoint, MIT.
// ruiqichenbiec/design-systems@7a424c93b9be13cf835b91ea67495fec2ec0584e
// overture/src/dynamics.js. Changes: ES module, 180ms, cancellation,
// synchronous GPU palette update, reduced-motion fallback; no global Overture.
import {isDesktopHost} from '../../js/channel.js';
let active = null;
export function cancelThemeTransition() {
  active?.skipTransition(); active = null;
  document.documentElement.classList.remove('ov-vt');
}

export async function transitionTheme(apply, {origin, reduced = false} = {}) {
  cancelThemeTransition();
  const root = document.documentElement;
  const nativeDesktop = isDesktopHost();
  if (!document.startViewTransition || !origin || reduced || document.hidden || nativeDesktop) {
    root.dataset.themeTransitionReason = nativeDesktop ? 'desktop-stability' : !document.startViewTransition ? 'unsupported' : !origin ? 'no-origin' : reduced ? 'reduced' : 'hidden';
    root.classList.remove('ov-vt'); await apply(); return 'instant';
  }
  const rect = root.getBoundingClientRect();
  const point = origin.getBoundingClientRect?.();
  const x = (point ? point.left + point.width / 2 : origin[0]) - rect.left;
  const y = (point ? point.top + point.height / 2 : origin[1]) - rect.top;
  const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  root.classList.add('ov-vt');
  const transition = document.startViewTransition(apply); active = transition;
  const finished = transition.finished.catch(() => {});
  const updated = transition.updateCallbackDone.catch(() => {});
  try {
    await transition.ready;
    const animation = root.animate({clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`]},
      {duration: 180, easing: 'cubic-bezier(.16,1,.3,1)', pseudoElement: '::view-transition-new(root)'});
    await animation.finished.catch(() => {});
    await finished;
    root.dataset.themeTransitionReason = 'completed';
    return 'iris';
  } catch (error) {root.dataset.themeTransitionReason = error.message; await updated; return 'instant';}
  finally {if (active === transition) {active = null; root.classList.remove('ov-vt');}}
}
