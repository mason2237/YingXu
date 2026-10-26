// Adapted from Overture Toast and Tooltip in overture/src/overlays.js.
// MIT © 2026 DayDreamInAReverie; upstream commit and changes: UPSTREAM.md.
// Removes showcase actions/audio/media; adds IME, cancellation and native top-layer handling.
const floatInto = (panel, origin) => {
  const parent = origin?.closest('dialog[open]') || [...document.querySelectorAll('dialog[open]')].at(-1) || document.body;
  if (panel.parentElement !== parent) {if (panel.matches(':popover-open')) panel.hidePopover(); parent.append(panel);}
  panel.hidden = false;
  if (panel.showPopover && !panel.matches(':popover-open')) panel.showPopover();
};
const conceal = panel => {if (panel.matches(':popover-open')) panel.hidePopover(); panel.hidden = true;};

export function transientNotice(panel, {reduced = () => false, paint = () => {}} = {}) {
  const bar = panel.querySelector('[data-notice-timer]'), abort = new AbortController(), signal = abort.signal;
  let timer = 0, meter = null, left = 0, since = 0, held = false, pointerInside = false, generation = 0, opener = null;
  const paused = () => document.hidden || pointerInside || panel.contains(document.activeElement);
  function arm(ms) {
    clearTimeout(timer); meter?.cancel(); meter = null; left = ms; since = performance.now();
    if (!reduced()) {meter = bar.animate([{transform:'scaleX(1)'},{transform:'scaleX(0)'}], {duration:ms,fill:'forwards'}); if (held) meter.pause();}
    if (!held) timer = setTimeout(() => hide(), ms);
  }
  function hold() {
    const next = paused(); if (next === held || panel.hidden) return;
    held = next;
    if (held) {clearTimeout(timer); left = Math.max(0,left-(performance.now()-since)); meter?.pause();}
    else {since = performance.now(); timer = setTimeout(() => hide(),left); meter?.play();}
  }
  function hide({immediate = false} = {}) {
    clearTimeout(timer); meter?.cancel(); meter = null; const current = ++generation;
    if (panel.hidden) return;
    panel.getAnimations().forEach(animation => animation.cancel());
    const finish = () => {
      if (current !== generation) return;
      if (panel.contains(document.activeElement) && opener?.isConnected && !opener.closest('dialog:not([open])')) opener.focus({preventScroll:true});
      conceal(panel); panel.getAnimations().forEach(animation => animation.cancel()); held = pointerInside = false;
    };
    if (immediate || reduced() || document.hidden) finish();
    else panel.animate([{opacity:1,translate:'0 0'},{opacity:0,translate:'0 5px'}], {duration:100,fill:'forwards'}).finished.catch(() => {}).then(finish);
  }
  function show(message, {tone = 'info', duration = 4400} = {}) {
    generation++; clearTimeout(timer); panel.getAnimations().forEach(animation => animation.cancel());
    opener = document.activeElement; paint(String(message), tone); floatInto(panel, opener);
    pointerInside = panel.matches(':hover'); held = paused(); arm(duration);
    if (!reduced()) panel.animate([{opacity:0,translate:'0 5px'},{opacity:1,translate:'0 0'}], {duration:160,easing:'cubic-bezier(.2,.8,.2,1)'});
  }
  panel.addEventListener('pointerenter', () => {pointerInside = true;hold();}, {signal});
  panel.addEventListener('pointerleave', () => {pointerInside = false;hold();}, {signal});
  panel.addEventListener('focusin',hold,{signal});
  panel.addEventListener('focusout', () => queueMicrotask(hold), {signal});
  panel.querySelector('[data-notice-close]').addEventListener('click', () => hide(), {signal});
  document.addEventListener('visibilitychange',hold,{signal});
  document.addEventListener('close', event => {if (!panel.hidden && event.target.contains(panel)) floatInto(panel);}, {capture:true,signal});
  return {show,hide, refreshMotion() {if (!panel.hidden) {const remaining = held ? left : Math.max(0,left-(performance.now()-since)); panel.getAnimations().forEach(animation => animation.cancel()); arm(remaining);}},
    stats: () => ({visible:!panel.hidden,paused:held}),
    destroy() {generation++;clearTimeout(timer);meter?.cancel();panel.getAnimations().forEach(animation => animation.cancel());conceal(panel);abort.abort();}};
}

export function tooltips({reduced = () => false} = {}) {
  const panel = document.createElement('div'), abort = new AbortController(), signal = abort.signal;
  panel.id = 'workspace-tooltip'; panel.className = 'workspace-tooltip'; panel.role = 'tooltip'; panel.setAttribute('popover','manual'); panel.hidden = true; document.body.append(panel);
  const selector = '[data-tooltip],.icon-button[aria-label],button[title]';
  let anchor = null, timer = 0, described = null;
  function hide() {
    clearTimeout(timer); panel.getAnimations().forEach(animation => animation.cancel()); conceal(panel);
    if (anchor) {if (described === null) anchor.removeAttribute('aria-describedby');else anchor.setAttribute('aria-describedby',described);}
    anchor = null;
  }
  function schedule(target, delay) {
    if (anchor === target) return; hide(); if (!target || target.disabled) return;
    anchor = target; described = target.getAttribute('aria-describedby');
    if (target.title) {target.dataset.tooltip = target.title;target.removeAttribute('title');}
    timer = setTimeout(() => {
      if (!target.isConnected || target !== anchor || target.closest('[inert],dialog:not([open])')) return hide();
      panel.textContent = target.dataset.tooltip || target.getAttribute('aria-label'); floatInto(panel,target);
      const box = target.getBoundingClientRect(), tip = panel.getBoundingClientRect();
      panel.style.left = `${Math.max(8,Math.min(innerWidth-tip.width-8,box.left+(box.width-tip.width)/2))}px`;
      panel.style.top = `${box.top>tip.height+12 ? box.top-tip.height-7 : Math.min(innerHeight-tip.height-8,box.bottom+7)}px`;
      target.setAttribute('aria-describedby',[described,panel.id].filter(Boolean).join(' '));
      if (!reduced()) panel.animate([{opacity:0},{opacity:1}],{duration:100});
    },delay);
  }
  document.addEventListener('pointerover', event => {if (event.pointerType !== 'touch') schedule(event.target.closest(selector),380);}, {signal});
  document.addEventListener('pointerout', event => {if (anchor && !anchor.contains(event.relatedTarget) && !anchor.contains(document.activeElement)) hide();}, {signal});
  document.addEventListener('focusin', event => schedule(event.target.closest(selector),150), {signal});
  document.addEventListener('focusout', event => {if (anchor && !anchor.contains(event.relatedTarget)) hide();}, {signal});
  document.addEventListener('pointerdown',hide,{signal});
  document.addEventListener('keydown', event => {if (event.key === 'Escape') hide();}, {signal});
  document.addEventListener('scroll',hide,{capture:true,passive:true,signal});
  window.addEventListener('resize',hide,{signal});
  return {hide,destroy() {hide();abort.abort();panel.remove();}};
}
