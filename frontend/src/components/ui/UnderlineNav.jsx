import { Link } from "react-router-dom";

export default function UnderlineNav({ label, items, className = "" }) {
  return <nav className={`pf-underline-nav ${className}`} aria-label={label}>
    {items.map((item) => <Link key={item.id} to={item.to} aria-current={item.current ? "page" : undefined}>
      {item.icon}{item.label}{Number.isInteger(item.count) && <span className="pf-counter">{item.count}</span>}
    </Link>)}
  </nav>;
}
