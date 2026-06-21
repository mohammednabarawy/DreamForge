import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { IdeogramLayoutWindow } from "./components/IdeogramLayoutWindow";
import "./index.css";

const rootComponent =
  new URLSearchParams(window.location.search).get("tool") === "ideogram-layout" ? (
    <IdeogramLayoutWindow />
  ) : (
    <App />
  );

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      {rootComponent}
    </ErrorBoundary>
  </React.StrictMode>,
);
