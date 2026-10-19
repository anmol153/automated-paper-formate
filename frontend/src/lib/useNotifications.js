import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { countUnreadNotifications, errorMessage, getNotificationFeed, markAllNotificationsRead, markNotificationRead } from "./api.js";

const CHANGED = "paper:notifications-changed";

export default function useNotifications({ unreadOnly = false, limit = 25, poll = false } = {}) {
  const { user } = useAuth();
  const userId = user?.user_id;
  const [state, setState] = useState({ items: [], count: null, cursor: null, loading: true });
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const request = useRef(null);
  const identity = useRef(userId);
  identity.current = userId;
  const fetchPage = useCallback(async (before) => {
    if (!userId) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setState((old) => ({ ...old, owner: userId, loading: true, error: "", ...(before ? {} : { items: [], cursor: null, count: null }) }));
    try {
      const [page, count] = await Promise.all([
        getNotificationFeed({ unreadOnly, limit, before, signal: controller.signal }),
        countUnreadNotifications(controller.signal),
      ]);
      if (controller.signal.aborted || identity.current !== userId) return;
      setState((old) => ({ owner: userId, loading: false, error: "", count, cursor: page.next_cursor,
        items: before ? [...new Map([...old.items, ...page.items].map((item) => [item.notification_id, item])).values()] : page.items }));
    } catch (error) {
      if (!controller.signal.aborted && identity.current === userId) {
        setState({ owner: userId, items: [], count: null, cursor: null, loading: false, error: errorMessage(error) });
      }
    }
  }, [userId, unreadOnly, limit]);
  useEffect(() => {
    if (!userId) return;
    const refresh = () => { if (document.visibilityState !== "hidden") fetchPage(); };
    const changed = (event) => { if (event.detail === userId) fetchPage(); };
    fetchPage();
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener(CHANGED, changed);
    const timer = poll ? window.setInterval(refresh, 60_000) : null;
    return () => {
      request.current?.abort();
      if (timer !== null) window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener(CHANGED, changed);
    };
  }, [fetchPage, userId, poll]);
  const mutate = async (id) => {
    if (pending.current || !userId) return;
    pending.current = true; setBusy(true);
    try {
      if (id) await markNotificationRead(id);
      else await markAllNotificationsRead();
      if (identity.current === userId) window.dispatchEvent(new CustomEvent(CHANGED, { detail: userId }));
    } catch (error) {
      if (identity.current === userId) setState((old) => ({ ...old, error: errorMessage(error) }));
    } finally {
      pending.current = false; setBusy(false);
    }
  };
  const current = state.owner === userId && !!userId ? state : { items: [], count: null, cursor: null, loading: !!userId, error: "" };
  return { ...current, busy, refresh: () => fetchPage(), loadMore: () => fetchPage(current.cursor), markRead: mutate };
}
