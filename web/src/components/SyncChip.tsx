import { useLiveQuery } from "dexie-react-hooks";
import { useEffect, useState, useSyncExternalStore } from "react";
import { db } from "../db";
import { syncer } from "../sync";

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

function ago(iso: string | null): string {
  if (!iso) return "never";
  const min = Math.round((Date.now() - Date.parse(iso)) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  return h < 24 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

export default function SyncChip() {
  const status = useSyncExternalStore(syncer.subscribe, syncer.getStatus);
  const queued = useLiveQuery(() => db.queue.count(), [], 0);
  const online = useOnline();
  const failed = !!status.error;

  const dot = !online ? "bg-ink-soft" : failed ? "bg-bad" : "bg-good";
  const label = status.syncing
    ? "Syncing…"
    : !online
      ? "Offline"
      : failed
        ? "Can't reach server"
        : `Synced ${ago(status.lastSync)}`;

  return (
    <button
      type="button"
      onClick={() => void syncer.sync()}
      title={status.error ?? "Sync now"}
      className="flex min-h-11 items-center gap-2 rounded-full border border-rule bg-card px-3 text-xs text-ink-soft active:bg-paper-deep"
    >
      <span className={`size-2 rounded-full ${dot} ${status.syncing ? "animate-pulse" : ""}`} />
      <span>{label}</span>
      {queued > 0 && <span className="rounded-full bg-seal-wash px-1.5 text-seal">{queued} queued</span>}
    </button>
  );
}
