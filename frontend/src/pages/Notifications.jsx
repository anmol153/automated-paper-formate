import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import useNotifications from "../lib/useNotifications.js";
import NotificationItem from "../components/NotificationItem.jsx";
import Button, { ButtonLink } from "../components/ui/Button.jsx";

export default function Notifications() {
  const { user, loading } = useAuth();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const feed = useNotifications({ unreadOnly });
  if (loading) return <p role="status">Loading account…</p>;
  if (!user) return <div className="pf-management pf-card pf-empty"><h1>Notifications</h1><p>Sign in to see your notifications.</p><ButtonLink variant="primary" to="/login">Sign in</ButtonLink></div>;
  return <div className="pf-management pf-notifications-page"><header className="pf-management-header"><div><p className="pf-eyebrow">STAY IN THE LOOP</p><h1>Notifications</h1><p>Updates for papers and conferences you can currently access.</p></div><Button disabled={feed.loading || feed.busy || !feed.count} onClick={() => feed.markRead()}>Mark all as read</Button></header>
    <div className="pf-dashboard-columns"><section className="pf-card"><div className="pf-notification-toolbar"><div className="pf-actions"><label className="pf-check-option"><input type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} /><span>Unread only</span></label>{feed.count !== null && <span role="status" className="pf-count">{feed.count} unread</span>}</div><Button disabled={feed.loading || feed.busy} onClick={feed.refresh}>Refresh notifications</Button></div>
      {feed.error && <div className="pf-card-body"><p role="alert" className="pf-message pf-message--error">{feed.error} Use Refresh notifications to retry.</p></div>}
      {feed.loading && <div className="pf-empty" role="status">Loading notifications…</div>}
      {!feed.loading && !feed.error && feed.items.length === 0 && <div className="pf-empty"><span className="pf-empty-symbol" aria-hidden="true">✓</span><h2>{unreadOnly ? "No unread notifications." : "No notifications yet."}</h2><p>New comments, assignments and conference updates will appear here.</p></div>}
      <ul className="pf-notification-history" aria-label="Notification history">{feed.items.map((item) => <NotificationItem key={item.notification_id} notification={item} onMarkRead={feed.markRead} disabled={feed.busy || feed.loading} />)}</ul>
      {feed.cursor && <div className="pf-form-footer"><Button disabled={feed.loading || feed.busy} onClick={feed.loadMore}>Load older notifications</Button></div>}
    </section><aside className="pf-form-help"><span className="pf-eyebrow">YOUR ACTIVITY IN ONE PLACE</span><h2>Follow the work that matters.</h2><p>Notifications reflect your current access to papers and conferences. Marking one as read does not change the underlying review or submission.</p><p className="pf-help-note">Refresh returns to the newest updates. Older updates can be loaded at the end of the list.</p><Link to="/reviewer">Open review workspace →</Link></aside></div>
  </div>;
}
