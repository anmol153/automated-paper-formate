import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import useNotifications from "../lib/useNotifications.js";
import NotificationItem from "./NotificationItem.jsx";

export default function NotificationDropdown() {
  const { user } = useAuth();
  const feed = useNotifications({ unreadOnly: true, limit: 5, poll: true });
  const [open, setOpen] = useState(false);
  const container = useRef(null);
  const trigger = useRef(null);
  const location = useLocation();
  useEffect(() => { setOpen(false); }, [location.pathname, user?.user_id]);
  useEffect(() => {
    if (!open) return;
    const outside = (event) => { if (!container.current?.contains(event.target)) setOpen(false); };
    const escape = (event) => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  if (!user) return null;
  return <div className="relative" ref={container}>
    <button type="button" ref={trigger} title="Notifications" className="btn-outline text-sm inline-flex items-center gap-1" aria-expanded={open} aria-controls="notification-panel"
      aria-label={feed.count === null ? "Notifications" : `Notifications (${feed.count} unread)`}
      onClick={() => { if (!open) feed.refresh(); setOpen(!open); }}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5 shrink-0" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 8a6 6 0 00-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
      </svg><span className="sr-only">Notifications</span>{feed.count !== null && <span>{feed.count}</span>}
    </button>
    {open && <section id="notification-panel" aria-label="Recent notifications"
      className="absolute right-0 mt-2 w-[min(22rem,calc(100vw-2rem))] max-h-[70vh] overflow-y-auto panel p-4 shadow-lg z-50">
      <h2 className="font-semibold">Recent unread notifications</h2>
      {feed.loading && <p role="status">Loading notifications…</p>}
      {feed.error && <p role="alert" className="text-danger-600">{feed.error}</p>}
      {!feed.loading && !feed.error && feed.items.length === 0 && <p>No unread notifications.</p>}
      <ul>{feed.items.map((item) => <NotificationItem key={item.notification_id} notification={item} onMarkRead={feed.markRead}
        disabled={feed.loading || feed.busy} onNavigate={() => setOpen(false)} />)}</ul>
      <div className="flex flex-wrap gap-3 mt-3">
        <Link className="text-primary-600" to="/notifications" onClick={() => setOpen(false)}>View all notifications</Link>
        <button type="button" className="btn-outline text-xs" disabled={feed.loading || feed.busy} onClick={feed.refresh}>Refresh</button>
        <button type="button" className="btn-outline text-xs" disabled={feed.loading || feed.busy || !feed.count} onClick={() => feed.markRead()}>Mark all as read</button>
      </div>
    </section>}
  </div>;
}
