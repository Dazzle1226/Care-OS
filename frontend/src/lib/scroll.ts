export function scrollWorkspaceToTop(doc: Document = document, win: Window = window) {
  const workspace = doc.querySelector<HTMLElement>('main.workspace');
  workspace?.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  win.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  doc.documentElement.scrollTop = 0;
  doc.body.scrollTop = 0;
}

export function scheduleScrollWorkspaceToTop(doc: Document = document, win: Window = window) {
  if (typeof win.requestAnimationFrame !== 'function') {
    scrollWorkspaceToTop(doc, win);
    return () => undefined;
  }

  const frame = win.requestAnimationFrame(() => {
    scrollWorkspaceToTop(doc, win);
  });

  return () => win.cancelAnimationFrame(frame);
}
