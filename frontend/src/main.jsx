import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext.jsx";
import App from "./App.jsx";
import "./index.css";
import "./styles/management.css";
import "./styles/collaboration.css";
import "./styles/account-menu.css";
import "./styles/auth.css";
import "./styles/formatting.css";
import "./styles/paper-workspace.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider><App /></AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
