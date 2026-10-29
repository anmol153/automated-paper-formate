# Local demo walkthrough

The demo is real persisted data created through the application's existing APIs.
It uses a separate `[DEMO] Research Systems Conference` and four new accounts:
chair, submitting author, reviewer, and co-author.
Your other users, conferences and papers are not changed. No schema migration,
dependency installation, or application configuration change is required.

Credentials, generated record IDs and resumable progress are in the ignored local
file `backend/data/demo-walkthrough.json` (owner-readable only). Do not commit it.
To display the credentials and links again, run from the repository root:

```bash
.venv/bin/python scripts/create_demo_data.py
```

The backend must be running on port 8000. A completed run prints the same access
details without resetting any changes you made while testing. If initialization
stops, rerun to continue completed steps. Use a different `--state` path under
`backend/data/` to create a separate fresh demo, rather than resetting existing data.
Displaying a completed demo's credentials makes no API calls and does not sign in.
The existing sign-in protection allows 10 attempts per 15 minutes per client IP,
including successful logins. Browser QA shares that local budget; repeated QA runs
can temporarily block manual sign-in. The demo setup's exhausted local cooldown was
cleared after verification; normal rate limiting remains enabled.

## Start with the author

1. Open `http://localhost:5173/login`. Sign out first if necessary, then use the
   **author** demo credentials. Roles belong to conference memberships, so the
   sign-in form does not need a role selector.
2. Open Conferences, then the conference whose name begins with `[DEMO]`, then
   Papers. It contains the following submissions:

| Paper | Initial state | What to try |
|---|---|---|
| Reproducible Research Workflows | Under review | Overview, Conversation, protected PDF preview, earlier-revision anchors, Files and revisions, Compare revisions, Activity. Two actual PDF uploads are retained. |
| Formatting Fixes: A Hands-On Example | Draft | Open Formatting checks and Issues. The three-page paper exceeds the two-page requirement. Upload its two-page revised sample, then use Overview → Action → Submit for review. |
| Artifact Tracking for Open Research | Changes requested | Read the chair's reason, upload the revised sample, and resubmit using the available Overview action. |
| Transparent Collaboration in Peer Review | Accepted | Read the final decision and released formal review. Author access excludes confidential review notes and reviewer identity. Revision uploads are closed. |
| Document-Centered Research Collaboration | Submitted | Inspect a paper awaiting reviewer assignment. Switch to the chair account to assign its reviewer. |

3. Try posting a discussion, replying, and selecting an earlier revision/page.
   Earlier discussions retain their original document anchor.
4. Sign in as the co-author to inspect the shared paper, read its discussion, and
   try editing or uploading a revision with the granted paper access.
5. Revised PDFs are already available in `backend/data/demo-samples/`. Match the
   `formatting-revised.pdf` or `revision-revised.pdf` file to the relevant paper.
   Uploaded revisions create new records and retain previous files and reports.

The demo template deliberately allows formatting findings to proceed to review,
so you can exercise both validation and review workflows. Chairs can configure
blocking failures instead in the conference's workflow settings. Formatting
reports are actual engine outputs, not manually invented pass/fail badges.

## Switch to the reviewer

Sign out and sign in with the **reviewer** demo account. Open Review workspace.
The main paper has an existing private review draft. Edit scores/text, save the
draft, or submit the formal review. The accepted paper shows a previously submitted
review. Declaring a conflict is a real action that revokes that assignment, so use
it only when you want to test the conflict workflow.

## Switch to the chair

Sign out and use the **chair** demo account. Open the demo conference to inspect
settings, tracks, template rules, participant memberships and review progress.
Use the account IDs shown in People when assigning a reviewer or granting paper
access. The main paper includes a chair-only conversation thread; it is absent
when signed in as author, co-author, or reviewer. The author has explicitly
granted the co-author access to the main paper.

On the submitted paper, assign the demo reviewer through Overview. After a review
is submitted, inspect it as chair, release it to authors, request changes or record
a final decision. The conference requires one submitted review for acceptance.
In-app notifications are real notifications created by these actions. Google
sign-in and external email delivery are not simulated by this dataset.

## Verification and scope

The generator checks initial lifecycle states, two retained revisions,
co-author access, and confidential-thread filtering through the real backend.
Optional real-browser QA uses normal sign-in and reads only these demo papers:

Creation was verified on the running local backend. Earlier browser checks passed
for chair, author and reviewer sign-in, authorized paper access, protected PDF
preview, review access, and confidential-content filtering. Co-author access is
verified by the generator through the API; it has not been added to the browser
walkthrough yet. A completed run reuses the saved demo rather than creating duplicates.

```bash
PAPER_BROWSER_MODULE=/absolute/path/to/playwright-core/index.mjs \
node scripts/check_demo_walkthrough.mjs
```

This uses existing Chromium/Playwright tooling; no library installation is needed.
Changing demo statuses while testing can change what the optional checker expects.
Demo accounts have access to their own conference; your existing account is not
automatically added. To use that account, add its account ID through demo-chair
People management with the desired conference role.
