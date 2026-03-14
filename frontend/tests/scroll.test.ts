import assert from 'node:assert/strict';
import test from 'node:test';

import { scheduleScrollWorkspaceToTop, scrollWorkspaceToTop } from '../src/lib/scroll.ts';

test('scrollWorkspaceToTop resets both workspace and document scroll positions', () => {
  let workspaceScrollCalls = 0;
  let windowScrollCalls = 0;

  const workspace = {
    scrollTo(options: ScrollToOptions) {
      workspaceScrollCalls += 1;
      assert.deepEqual(options, { top: 0, left: 0, behavior: 'auto' });
    }
  };

  const documentStub = {
    querySelector(selector: string) {
      assert.equal(selector, 'main.workspace');
      return workspace;
    },
    documentElement: { scrollTop: 24 },
    body: { scrollTop: 12 }
  } as unknown as Document;

  const windowStub = {
    scrollTo(options: ScrollToOptions) {
      windowScrollCalls += 1;
      assert.deepEqual(options, { top: 0, left: 0, behavior: 'auto' });
    }
  } as unknown as Window;

  scrollWorkspaceToTop(documentStub, windowStub);

  assert.equal(workspaceScrollCalls, 1);
  assert.equal(windowScrollCalls, 1);
  assert.equal(documentStub.documentElement.scrollTop, 0);
  assert.equal(documentStub.body.scrollTop, 0);
});

test('scheduleScrollWorkspaceToTop uses requestAnimationFrame and supports cleanup', () => {
  const events: string[] = [];
  let rafCallback: FrameRequestCallback | null = null;
  const cancelledFrames: number[] = [];

  const workspace = {
    scrollTo() {
      events.push('workspace');
    }
  };

  const documentStub = {
    querySelector() {
      return workspace;
    },
    documentElement: { scrollTop: 10 },
    body: { scrollTop: 6 }
  } as unknown as Document;

  const windowStub = {
    requestAnimationFrame(callback: FrameRequestCallback) {
      rafCallback = callback;
      events.push('raf');
      return 7;
    },
    cancelAnimationFrame(frame: number) {
      cancelledFrames.push(frame);
    },
    scrollTo() {
      events.push('window');
    }
  } as unknown as Window;

  const cleanup = scheduleScrollWorkspaceToTop(documentStub, windowStub);
  assert.deepEqual(events, ['raf']);

  rafCallback?.(0);
  assert.deepEqual(events, ['raf', 'workspace', 'window']);
  assert.equal(documentStub.documentElement.scrollTop, 0);
  assert.equal(documentStub.body.scrollTop, 0);

  cleanup();
  assert.deepEqual(cancelledFrames, [7]);
});
