# User Acceptance Testing (UAT) Scenarios
## Paper-Format Conference Paper Review Platform

### UAT Goal
Validate that the Phase 3 features (diff engine, notification system, latest template endpoint) and existing Phase 1-2 features work correctly in end-to-end workflows.

---

## Scenario 1: Author Creates Conference, Uploads Paper, Sees Formatting Report

**Preconditions:**
- User is authenticated (has valid JWT token)
- User has AUTHOR role in at least one conference (or can create one)

**Steps:**
1. User calls `POST /api/v1/auth/login` with valid credentials
2. User calls `POST /api/v1/conferences` to create a new conference named "Test Conference 2026"
3. User is automatically added as OWNER of the new conference
4. User calls `POST /api/v1/conferences` again to add a template version:
   - Payload includes RuleSet with `pages.max_pages: 8`, `sections.required_sections: ["Abstract", "Introduction", "Conclusion", "References"]`
5. User uploads a LaTeX paper via `POST /api/v1/conferences/{conf_id}/submissions` with a .tex file
6. User calls `GET /api/v1/conferences/{conf_id}/latest` to retrieve the template

**Expected Outcomes:**
- Conference is created with a unique conference_id
- Template version is saved immutably with a new template_id
- Paper upload triggers compliance assessment automatically
- Response includes `PaperAssessment` with verdict, score, passed/failed/missing counts
- `template_id` in the submission matches the latest template version
- `GET /api/v1/conferences/{conf_id}/latest` returns the correct RuleSet

**Verification Points:**
- `POST /api/v1/conferences` returns 201 with conference_id
- `POST /api/v1/conferences/{conf_id}/submissions` returns 201 with submission_id
- Assessment response has all required fields: `score`, `passed`, `failed`, `missing`, `verdict`, `results`
- `GET /api/v1/conferences/{conf_id}/latest` returns 200 with a RuleSet
- Database has new rows in `submissions` and `template_versors` tables (additive only, no existing data overwritten)

---

## Scenario 2: Reviewer Is Assigned, Receives Notification, Submits Verdict

**Preconditions:**
- User (organizer) is authenticated and has OWNER role in a conference
- A submission exists for that conference with a verdict of "needs_review" or "accepted"/"rejected"
- Another user exists with REVIEWER role in the same conference

**Steps:**
1. Organizer calls `POST /api/v1/conferences/{conf_id}/submissions/{submission_id}/review` with reviewer_id
2. System creates a `ReviewAssignment` and updates submission status to `under_review`
3. System creates a `Notification` of type `REVIEW_ASSIGNMENT` for the reviewer
4. Reviewer authenticates and calls `GET /api/v1/notifications/unread` to see the new notification
5. Reviewer calls `POST /api/v1/conferences/{submission_id}/verdict` with verdict "accept" and score 85
6. System updates the submission with the verdict and score
7. System creates another Notification of type `SUBMISSION_VERDICT` for the author

**Expected Outcomes:**
- Review assignment succeeds; submission status becomes `under_review`
- Notification is created for reviewer with their email (snowflake pattern)
- Reviewer can see the unread notification via `GET /api/v1/notifications/unread`
- Verdict is set on the submission; compliance score is stored
- Author receives a `SUBMISSION_VERDICT` notification
- All database changes are additive (new rows, no existing data overwritten)

**Verification Points:**
- `POST /api/v1/conferences/{conf_id}/submissions/{submission_id}/review` returns 201
- Notification store has new entry with `type=review_assignment` and the reviewer's email
- `GET /api/v1/notifications/unread` for reviewer shows count ≥ 1
- `POST /api/v1/conferences/{submission_id}/verdict` returns 200
- Submission's `verdict` field is set to "accept" and `compliance_score` is 85
- Author's notifications include `type=submission_verdict`

---

## Scenario 3: Author Uploads Revision, Diff Is Shown Between Revisions

**Preconditions:**
- Two submissions exist for the same conference with different `template_id` values (immutable versions)
- Or: two paper files have been uploaded to the same submission, creating revisions

**Steps:**
1. Author has submission `sub-1` with `template_id=v1` (initial template)
2. Author uploads a revised paper to the same conference:
   - `POST /api/v1/conferences/{conf_id}/submissions` creates `sub-2` with `template_id=v2` (new version)
   - Or: existing submission `sub-1` has a new template version assigned
3. User calls `POST /api/v1/conferences/diff` with `old_template_id=v1` and `new_template_id=v2`
4. System returns a diff payload showing changes between the two template versions

**Expected Outcomes:**
- New submission/revision is created without modifying the earlier revision
- Diff endpoint returns a structured diff with `added`, `removed`, `changed`, `unchanged` fields
- Summary text describes the differences (e.g., "1 top-level rule changed, 2 group changes")
- Both template versions remain accessible independently

**Verification Points:**
- `POST /api/v1/conferences/{conf_id}/submissions` creates new submission with new `template_id`
- `POST /api/v1/conferences/diff` returns 200 with diff object
- Diff has keys: `added`, `removed`, `changed`, `unchanged` (all dicts or simplified values)
- `summary` field provides human-readable description
- Existing submissions with `v1` template remain unchanged and retrievable

---

## Scenario 4: Organizer Makes Final Decision, Status Changes, Author Is Notified

**Preconditions:**
- A submission exists with status `under_review`
- Organizer is authenticated with OWNER role in the conference
- A reviewer has submitted a verdict

**Steps:**
1. Organizer calls `PATCH /api/v1/submissions/{submission_id}` with status "accepted" or "rejected"
2. System updates the submission status and `updated_at` timestamp
3. System creates a Notification for the author about the decision
4. Organizer can also call `POST /api/v1/conferences/{submission_id}/verdict` if a reviewer verdict exists

**Expected Outcomes:**
- Submission status changes to `accepted` or `rejected`
- `compliance_score` remains if previously set, or becomes null
- Author receives a `SUBMISSION_VERDICT` or `MEMBER_ADDED` notification
- Activity log records the status change

**Verification Points:**
- `PATCH /api/v1/submissions/{submission_id}` with status "accepted" returns 200
- Submission's `status` field is "accepted" or "rejected"
- Notification store has new entry for the author
- `updated_at` timestamp is updated

---

## Scenario 5: User Cannot Access Another Conference's Private Paper

**Preconditions:**
- User (Alice) is authenticated and is AUTHOR in conference "conf-A"
- User (Bob) is authenticated and is AUTHOR in conference "conf-B"
- Both conferences exist and have submissions

**Steps:**
1. Alice authenticates and calls `GET /api/v1/conferences/{conf_B_id}/submissions`
2. Bob authenticates and calls `GET /api/v1/conferences/{conf_A_id}/submissions`

**Expected Outcomes:**
- Alice can only see submissions from conference "conf-A", not "conf-B"
- Bob can only see submissions from conference "conf-B", not "conf-A"
- Access attempts to the other conference's submissions return 403 Forbidden
- Membership check correctly filters by conference_id

**Verification Points:**
- `GET /api/v1/conferences/{conf_B_id}/submissions` for Alice returns 403
- `GET /api/v1/conferences/{conf_A_id}/submissions` for Bob returns 403
- Each user can successfully retrieve their own conference's submissions (200)
- Role-based access control (`require_role`) correctly filters by conference membership

---

## Summary of Verification Areas

| Area | Test Focus |
|---|---|
| **Database** | Additive schema only; no existing tables overwritten; new rows only |
| **Authentication** | JWT validation works; tokens accepted/rejected correctly |
| **Role hierarchy** | owner > reviewer > author checks work across all endpoints |
| **Immutability** | Template versions and submissions create new rows, don't overwrite |
| **Notification snowflake** | Emails captured on creation; notifications fetchable by user |
| **Diff engine** | Structured diff returned; summary text generated; both versions remain accessible |
| **API consistency** | All new endpoints follow existing `/api/v1/` prefix and tag patterns |
| **Error handling** | Invalid inputs return appropriate 400/401/403/422 status codes |

---

## Run Criteria

UAT is considered passed when:
- All 5 scenarios complete without unhandled exceptions
- All database state is consistent and additive
- No existing test suite tests are broken (10/10 backend API tests still pass)
- Frontend builds successfully after any changes
- User permissions are correctly enforced in all scenarios