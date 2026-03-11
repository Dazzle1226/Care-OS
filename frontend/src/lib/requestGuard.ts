export interface RequestGuard {
  begin: () => number;
  invalidate: () => number;
  isCurrent: (requestId: number) => boolean;
}

export function createRequestGuard(): RequestGuard {
  let currentRequestId = 0;

  return {
    begin() {
      currentRequestId += 1;
      return currentRequestId;
    },
    invalidate() {
      currentRequestId += 1;
      return currentRequestId;
    },
    isCurrent(requestId: number) {
      return requestId === currentRequestId;
    }
  };
}
