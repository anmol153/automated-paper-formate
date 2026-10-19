import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { listIssues, getIssue, updateIssue, addIssueComment } from "../lib/api.js";
import { errorMessage } from "../lib/api.js";

export default function Issues() {
  const { submissionId } = useParams();
  const navigate = useNavigate();
  const [issues, setIssues] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [commentText, setCommentText] = useState("");

  useEffect(() => {
    listIssues(submissionId)
      .then(setIssues)
      .catch((err) => setError(errorMessage(err)));
  }, [submissionId]);

  const selectIssue = (id) => {
    getIssue(id)
      .then(setSelected)
      .catch((err) => setError(errorMessage(err)));
  };

  const saveIssue = async () => {
    if (!selected) return;
    try {
      const updated = await updateIssue(selected.issue_id, {
        status: selected.status,
        assignee_id: selected.assignee_id,
      });
      setSelected(updated);
      // refresh list
      const refreshed = await listIssues(submissionId);
      setIssues(refreshed);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const addComment = async () => {
    if (!selected || !commentText.trim()) return;
    try {
      await addIssueComment(selected.issue_id, commentText.trim());
      // reload issue to get new comments
      const refreshed = await getIssue(selected.issue_id);
      setSelected(refreshed);
      setCommentText("");
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  return (
    <div className="animate-fade-in">
      <header className="mb-4">
        <h1 className="text-2xl font-bold">Issues for submission {submissionId}</h1>
        <button className="btn-primary mt-2" onClick={() => navigate(-1)}>
          Back
        </button>
      </header>

      {selected ? (
        <div className="panel">
          <h2 className="text-xl font-semibold mb-2">{selected.title}</h2>
          <p className="mb-2">{selected.description}</p>
          {selected.revision_id && <Link className="text-primary-600" to={`/submissions/${submissionId}?revision=${selected.revision_id}`}>View the revision where this finding was reported</Link>}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <label>
              Status
              <select
                className="input-base w-full"
                value={selected.status}
                onChange={(e) => setSelected({ ...selected, status: e.target.value })}
              >
                {Object.values(["open","in_progress","resolved","wont_fix"]).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Assignee ID
              <input
                className="input-base w-full"
                value={selected.assignee_id || ""}
                onChange={(e) => setSelected({ ...selected, assignee_id: e.target.value })}
              />
            </label>
          </div>
          <button className="btn-primary" onClick={saveIssue}>
            Save
          </button>

          <section className="mt-6">
            <h3 className="font-medium">Comments</h3>
            <ul className="divide-y divide-surface-200">
              {selected.comments?.map((c) => (
                <li key={c.comment_id} className="p-2">
                  <p className="text-sm">{c.text}</p>
                  <p className="text-xs text-surface-500">by {c.author_id} at {new Date(c.created_at).toLocaleString()}</p>
                </li>
              ))}
            </ul>
            <div className="mt-4">
              <textarea
                className="input-base w-full"
                rows={3}
                placeholder="Add a comment"
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
              />
              <button className="btn-primary mt-2" onClick={addComment}>
                Add Comment
              </button>
            </div>
          </section>
        </div>
      ) : (
        <ul className="divide-y divide-surface-200">
          {issues.map((i) => (
            <li key={i.issue_id} className="p-3 cursor-pointer hover:bg-surface-100" onClick={() => selectIssue(i.issue_id)}>
              <div className="flex justify-between items-center">
                <span className="font-medium">{i.title}</span>
                <span className={`badge ${i.status === "open" ? "badge-primary" : i.status === "resolved" ? "badge-success" : "badge-warning"}`}> {i.status} </span>
              </div>
              <p className="text-sm text-surface-600">{i.severity}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
