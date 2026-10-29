import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { assignSubmissionReviewer, errorMessage, getConference, getConferenceReviewProgress, listConferences } from "../lib/api.js";
import Button, { ButtonLink } from "./ui/Button.jsx";
import Field from "./ui/Field.jsx";
import StateBadge from "./ui/StateBadge.jsx";

// The public directory deliberately omits ownership. Resolve membership through
// authenticated conference views, then request progress only for actual chairs.
async function batches(items, operation, active) {
  const output = [];
  for (let index = 0; index < items.length && active(); index += 4) {
    output.push(...await Promise.allSettled(items.slice(index, index + 4).map(operation)));
  }
  return output;
}

const eligibleAssignments = (paper) => (paper.assignments || []).filter((assignment) => assignment.eligible);
const assignable = (paper) => ["submitted", "under_review"].includes(paper.status);
const needsReviewers = (paper) => assignable(paper) && eligibleAssignments(paper).length === 0;

export default function ChairAssignments({ userId, refreshKey, visible, onLoaded, onAssigned }) {
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, conferences: [], error: "", incomplete: false });
  const [attempt, setAttempt] = useState(0);
  const [search, setSearch] = useState("");
  const [conferenceId, setConferenceId] = useState("");
  const [filter, setFilter] = useState("");
  const [selection, setSelection] = useState({});
  const [busy, setBusy] = useState("");
  const [mutationError, setMutationError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    let current = true;
    setState({ loading: true, conferences: [], error: "", incomplete: false });
    async function load() {
      try {
        const directory = await listConferences();
        if (!current) return;
        const membership = await batches(directory, (item) => getConference(item.conference_id), () => current);
        if (!current) return;
        const owned = membership.filter((result) => result.status === "fulfilled" && result.value.members?.some((member) => member.user_id === userId && member.role === "owner")).map((result) => result.value);
        const incomplete = membership.some((result) => result.status === "rejected" && ![403, 404].includes(result.reason?.response?.status));
        const progress = await batches(owned, (conference) => getConferenceReviewProgress(conference.conference_id), () => current);
        if (!current) return;
        setState({ loading: false, error: "", incomplete, conferences: owned.map((conference, index) => ({ conference, data: progress[index]?.status === "fulfilled" ? progress[index].value : null, error: progress[index]?.status === "rejected" ? errorMessage(progress[index].reason) : "" })) });
        onLoaded(owned.length);
      } catch (err) {
        if (current) { setState({ loading: false, conferences: [], error: errorMessage(err), incomplete: false }); onLoaded(0); }
      }
    }
    load();
    return () => { current = false; };
  }, [userId, refreshKey, attempt, onLoaded]);

  async function assign(event, paper, reviewerId, openReview = false) {
    event.preventDefault(); const reviewer = reviewerId || selection[paper.submission_id];
    if (!reviewer || busy) return;
    setBusy(paper.submission_id); setMutationError(""); setMessage("");
    try {
      await assignSubmissionReviewer(paper.submission_id, reviewer);
      setSelection((previous) => ({ ...previous, [paper.submission_id]: "" }));
      setMessage("Reviewer assigned. Review progress is being refreshed.");
      if (onAssigned) onAssigned(); else setAttempt((value) => value + 1);
      if (openReview) navigate(`/submissions/${paper.submission_id}?tab=reviews`);
    } catch (err) { setMutationError(errorMessage(err)); }
    finally { setBusy(""); }
  }
  const retry = () => setAttempt((value) => value + 1);
  if (state.loading) return <p role="status">{visible ? "Loading conference assignments…" : "Checking conference access…"}</p>;
  const loadError = state.error || (state.incomplete ? "Some conference memberships could not be checked. The list may be incomplete." : "");
  if (!visible) return loadError ? <div role="alert" className="pf-message pf-message--error">{loadError} <Button onClick={retry}>Retry conference access</Button></div> : null;
  const rows = state.conferences.flatMap((item) => (item.data?.papers || []).map((paper) => ({ ...paper, conference: item.conference })));
  const scoped = conferenceId ? rows.filter((paper) => paper.conference.conference_id === conferenceId) : rows;
  const totalsUnavailable = state.conferences.some(({ conference, data }) => (!conferenceId || conference.conference_id === conferenceId) && !data);
  const matched = (paper) => (!search || `${paper.title || ""} ${paper.filename || ""} ${paper.paper_number || ""} ${paper.conference.name}`.toLowerCase().includes(search.toLowerCase())) && (!filter || (filter === "unassigned" ? needsReviewers(paper) : filter === "missing" ? paper.status === "under_review" && paper.missing > 0 : paper.status === filter));
  const shown = scoped.filter(matched);
  return <section className="pf-chair-assignments pf-stack" aria-label="Chair conference assignments">
    {loadError && <div role="alert" className="pf-message pf-message--error">{loadError} <Button onClick={retry}>Retry conference access</Button></div>}
    {mutationError && <p role="alert" className="pf-message pf-message--error">{mutationError}</p>}
    {message && <p role="status" className="pf-message">{message}</p>}
    <div className="pf-chair-assignment-stats">{[["Papers", scoped.length], ["Need reviewers", scoped.filter(needsReviewers).length], ["Current assignments", scoped.reduce((total, paper) => total + eligibleAssignments(paper).length, 0)], ["Reviews submitted", scoped.reduce((total, paper) => total + paper.submitted, 0)]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{totalsUnavailable ? "—" : value}</strong></div>)}</div>
    <div className="pf-chair-assignment-filters"><Field label="Search conference papers"><input type="search" value={search} placeholder="Title, paper number or conference" onChange={(event) => setSearch(event.target.value)} /></Field>
      <Field label="Managed conference"><select value={conferenceId} onChange={(event) => setConferenceId(event.target.value)}><option value="">All managed conferences</option>{state.conferences.map(({ conference }) => <option key={conference.conference_id} value={conference.conference_id}>{conference.name}</option>)}</select></Field>
      <Field label="Assignment filter"><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">All papers</option><option value="unassigned">Needs reviewers</option><option value="under_review">Under review</option><option value="missing">Missing reviews</option><option value="submitted">Submitted</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select></Field></div>
    {state.conferences.filter(({ conference }) => !conferenceId || conference.conference_id === conferenceId).map(({ conference, data, error }) => {
      const papers = shown.filter((paper) => paper.conference.conference_id === conference.conference_id);
      return <section className="pf-card" key={conference.conference_id}><div className="pf-card-heading"><div><h2>{conference.name}</h2><p>{data ? `${data.papers.length} accessible papers · Minimum ${data.minimum_reviews} current-revision reviews for a decision` : "Review progress unavailable"}</p></div><Link to={`/conferences/${conference.conference_id}?tab=reviews`}>Conference review settings →</Link></div>
        {error ? <div role="alert" className="pf-card-body">{error} <Button onClick={retry}>Retry conference assignments</Button></div> : !papers.length ? <div className="pf-empty"><h3>{data?.papers.length ? "No papers match these filters" : "No accessible submissions yet"}</h3><p>{data?.papers.length ? "Change the search or assignment filter to see more papers." : "Submitted papers will appear here. Papers with a chair conflict are excluded."}</p><ButtonLink to={`/conferences/${conference.conference_id}/submissions`}>Open conference papers</ButtonLink></div> : <div className="pf-chair-paper-list">{papers.map((paper) => {
          const active = eligibleAssignments(paper); const inactive = (paper.assignments || []).filter((assignment) => !assignment.eligible);
          const reviewers = (conference.members || []).filter((member) => ["reviewer", "owner"].includes(member.role) && !active.some((assignment) => assignment.reviewer_id === member.user_id));
          const ownAssignment = active.find((assignment) => assignment.reviewer_id === userId);
          return <article className="pf-chair-paper" key={paper.submission_id}><div className="pf-chair-paper-heading"><div><span className="pf-eyebrow">{paper.paper_number ? `PAPER #${paper.paper_number}` : "CONFERENCE PAPER"}</span><Link to={`/submissions/${paper.submission_id}`}>{paper.title || paper.filename}</Link></div><StateBadge status={paper.status} /></div>
            <div className="pf-chair-paper-grid"><section><h3>Reviewers</h3>{active.length ? <ul>{active.map((assignment) => <li key={assignment.assignment_id}><code>{assignment.reviewer_id}</code><span className="pf-count">{assignment.review_state.replaceAll("_", " ")}</span></li>)}</ul> : <p>{assignable(paper) ? "No reviewers assigned" : "No current assignments"}</p>}{inactive.length > 0 && <details><summary>{inactive.length} inactive {inactive.length === 1 ? "assignment" : "assignments"}</summary><ul>{inactive.map((assignment) => <li key={assignment.assignment_id}><code>{assignment.reviewer_id}</code><span>{assignment.status}</span></li>)}</ul></details>}</section>
            <section><h3>Current revision reviews</h3><p>{paper.submitted} submitted · {paper.missing} missing</p>{!active.length && assignable(paper) && <span className="pf-status-chip pf-status-chip--attention">Needs reviewers</span>}</section>
            <div className="pf-chair-paper-actions">{ownAssignment ? <ButtonLink to={`/submissions/${paper.submission_id}?tab=reviews`}>{ownAssignment.review_state === "submitted" ? "View my review →" : "Write my review →"}</ButtonLink> : assignable(paper) && <Button disabled={Boolean(busy)} busy={busy === paper.submission_id} onClick={(event) => assign(event, paper, userId, true)}>Review this paper</Button>}<ButtonLink to={`/submissions/${paper.submission_id}?tab=overview`}>Manage assignments →</ButtonLink><Link to={`/submissions/${paper.submission_id}?tab=reviews`}>View formal reviews</Link></div></div>
            {assignable(paper) && <details className="pf-chair-assign-form"><summary>Assign a reviewer</summary>{reviewers.length ? <form onSubmit={(event) => assign(event, paper)}><Field label={`Reviewer for paper ${paper.paper_number || paper.submission_id}`} required><select value={selection[paper.submission_id] || ""} disabled={Boolean(busy)} onChange={(event) => setSelection((previous) => ({ ...previous, [paper.submission_id]: event.target.value }))}><option value="">Choose a conference reviewer</option>{reviewers.map((member) => <option key={member.user_id} value={member.user_id}>{member.user_id === userId ? "You (chair)" : `${member.user_id}${member.role === "owner" ? " (chair)" : ""}`}</option>)}</select></Field><Button type="submit" variant="primary" busy={busy === paper.submission_id} disabled={Boolean(busy) || !selection[paper.submission_id]}>Assign reviewer</Button><p>Assignment starts review when the paper and conference policy allow it.</p></form> : <p>No other conference reviewers or chairs are available. <Link to={`/conferences/${conference.conference_id}?tab=people`}>Manage people</Link> or <Link to={`/conferences/${conference.conference_id}?tab=invitations`}>invite a reviewer</Link>.</p>}</details>}
          </article>;
        })}</div>}
      </section>;
    })}
    <p className="pf-fine-print">Only papers you are authorized to manage are included. Draft papers are not ready for reviewer assignment, and papers with a chair conflict are omitted.</p>
  </section>;
}
