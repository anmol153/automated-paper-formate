import { Link } from "react-router-dom";

export function notificationLink(notification) {
  return notification.type === "member_added" ? "/conferences" : `/submissions/${encodeURIComponent(notification.related_id)}`;
}

export default function NotificationItem({ notification, onMarkRead, disabled = false, onNavigate }) {
  const date = new Date(notification.created_at);
  return <li className="py-3 space-y-2 border-b border-surface-200 dark:border-surface-800">
    <Link to={notificationLink(notification)} onClick={onNavigate}
      className={`block text-primary-600 dark:text-primary-400 ${notification.read ? "font-normal" : "font-semibold"}`}>
      {notification.title}
    </Link>
    <p className="text-sm text-surface-600 dark:text-surface-400">{notification.body}</p>
    <div className="flex flex-wrap items-center gap-3 text-xs text-surface-500">
      <span>{notification.type.replaceAll("_", " ")}</span>
      {!Number.isNaN(date.getTime()) && <time dateTime={notification.created_at}>{date.toLocaleString()}</time>}
      <span>{notification.read ? "Read" : "Unread"}</span>
      {!notification.read && <button type="button" className="btn-outline text-xs" disabled={disabled}
        aria-label={`Mark ${notification.title} as read`} onClick={() => onMarkRead(notification.notification_id)}>Mark as read</button>}
    </div>
  </li>;
}
