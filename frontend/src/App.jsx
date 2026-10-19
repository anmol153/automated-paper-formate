import { Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext.jsx";
import AppShell from "./components/layout/AppShell.jsx";
import Login from "./pages/Login.jsx";
import Setup from "./pages/Setup.jsx";
import Submit from "./pages/Submit.jsx";
import Compare from "./pages/Home.jsx";
import Results from "./pages/Results.jsx";
import Reports from "./pages/Reports.jsx";
import Conferences from "./pages/Conferences.jsx";
import Issues from "./pages/Issues.jsx";
import Notifications from "./pages/Notifications.jsx";
import LatestTemplate from "./pages/LatestTemplate.jsx";
import TemplateDiff from "./pages/TemplateDiff.jsx";
import ConferencePapers from "./pages/ConferencePapers.jsx";
import SubmissionDetail from "./pages/SubmissionDetail.jsx";
import ReviewerWorkspace from "./pages/ReviewerWorkspace.jsx";
import Account from "./pages/Account.jsx";
import Invitation from "./pages/Invitation.jsx";
import Landing from "./pages/Landing.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import CreateConference from "./pages/CreateConference.jsx";
import ConferenceDetail from "./pages/ConferenceDetail.jsx";
import MyInvitations from "./pages/MyInvitations.jsx";
import MySchedule from "./pages/MySchedule.jsx";
import Docs from "./pages/Docs.jsx";

export default function App() {
  const { user } = useAuth();
  return <AppShell key={user?.user_id || "anonymous"}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/account" element={<Account />} />
          <Route path="/settings" element={<Account />} />
          <Route path="/invitations" element={<Invitation />} />
          <Route path="/my-invitations" element={<MyInvitations />} />
          <Route path="/my-schedule" element={<MySchedule />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="/" element={<Landing />} />
          <Route path="/home" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/submit" element={<Submit />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/results" element={<Results />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/conferences" element={<Conferences />} />
          <Route path="/conferences/new" element={<CreateConference />} />
          <Route path="/conferences/:confId" element={<ConferenceDetail />} />
          <Route path="/conferences/:confId/submissions" element={<ConferencePapers />} />
          <Route path="/conferences/:confId/submit" element={<ConferencePapers />} />
          <Route path="/reviewer" element={<ReviewerWorkspace />} />
          <Route path="/submissions/:submissionId" element={<SubmissionDetail />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/issues/:submissionId" element={<Issues />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/conferences/:confId/latest" element={<LatestTemplate />} />
          <Route path="/conferences/:confId/diff" element={<TemplateDiff />} />
        </Routes>
  </AppShell>;
}
