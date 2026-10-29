import { useEffect, useState } from "react";
import { errorMessage, getMyConferenceAccessRequest, requestConferenceAccess, listConferenceAccessRequests, decideConferenceAccessRequest } from "../lib/api.js";
import Button from "./ui/Button.jsx";

export function AccessRequestForm({ confId }) {
  const [item, setItem] = useState(undefined);
  const [role, setRole] = useState("author");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    getMyConferenceAccessRequest(confId).then((result) => { if (active) { setItem(result); if (result?.requested_role) setRole(result.requested_role); } })
      .catch((err) => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [confId]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    try { setItem(await requestConferenceAccess(confId, role)); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <section className="pf-card pf-access-request"><div className="pf-card-heading"><div><h2>Request conference access</h2><p>Ask a chair to add you to this conference. They’ll review your requested role.</p></div></div><div className="pf-card-body pf-stack">
    {error && <p role="alert" className="pf-message pf-message--error">{error}</p>}
    {item?.status === "pending" ? <p role="status" className="pf-message">Your {item.requested_role} request is waiting for a chair.</p>
      : item?.status === "approved" ? <p role="status" className="pf-message">Your request was approved. Refresh to open the conference.</p>
        : <form className="pf-form-grid" onSubmit={submit}><label className="pf-form-field">I’d like to join as<select value={role} disabled={busy} onChange={(event) => setRole(event.target.value)}><option value="author">Author</option><option value="reviewer">Reviewer</option></select></label><div className="pf-form-footer"><Button type="submit" variant="primary" busy={busy}>{item?.status === "declined" ? "Request again" : "Send request"}</Button></div></form>}
  </div></section>;
}

export function ConferenceAccessRequests({ confId }) {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => { let active = true; listConferenceAccessRequests(confId).then((rows) => { if (active) setItems(rows); }).catch((err) => { if (active) setError(errorMessage(err)); }); return () => { active = false; }; }, [confId, refresh]);
  async function decide(item, decision) {
    setBusy(item.request_id); setError("");
    try { await decideConferenceAccessRequest(confId, item.request_id, decision); setRefresh((value) => value + 1); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }
  const pending = (items || []).filter((item) => item.status === "pending");
  return <section className="pf-stack pf-section-divider" aria-label="Conference access requests"><div><h3>Access requests <span className="pf-count">{pending.length}</span></h3><p>Review requests from people who want to join this conference.</p></div>
    {error && <p role="alert" className="pf-message pf-message--error">{error}</p>}
    {!items ? <p role="status">Loading requests…</p> : !pending.length ? <p>No pending access requests.</p> : pending.map((item) => <article className="pf-access-request-row" key={item.request_id}><div><strong>{item.full_name}</strong><span>{item.email}</span><small>Requested {item.requested_role} · {new Date(item.created_at).toLocaleString()}</small></div><div className="pf-actions"><Button variant="primary" disabled={Boolean(busy)} busy={busy === item.request_id} onClick={() => decide(item, "approved")}>Approve</Button><Button variant="quiet" disabled={Boolean(busy)} onClick={() => decide(item, "declined")}>Decline</Button></div></article>)}
  </section>;
}
