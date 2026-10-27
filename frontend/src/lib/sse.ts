import { SSEEventData } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export type SSEEventType = "progress" | "stage_complete" | "done" | "error" | "ping";

export interface SSEEvent {
  type: SSEEventType;
  data: SSEEventData;
}

export function connectSSE(
  taskId: string,
  onEvent: (event: SSEEvent) => void,
  onOpen?: () => void,
  onReconnect?: () => void,
  onConnectionClosed?: () => void
): EventSource {
  const es = new EventSource(`${API_URL}/api/analyze/${taskId}/stream`);

  const eventTypes: SSEEventType[] = ["progress", "stage_complete", "done", "error", "ping"];

  for (const eventType of eventTypes) {
    es.addEventListener(eventType, (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      onEvent({ type: eventType, data });
      if (eventType === "done" || eventType === "error") {
        es.close();
      }
    });
  }

  es.onopen = () => onOpen?.();
  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      onConnectionClosed?.();
      return;
    }
    // EventSource reconnects automatically; a transient failure is not a task failure.
    onReconnect?.();
  };

  return es;
}
