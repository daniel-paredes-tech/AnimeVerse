import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/dela-gothic-one/latin-400.css";
import "@fontsource/biz-udpgothic/400.css";
import "@fontsource/biz-udpgothic/700.css";
import "./styles/global.css";
import "./styles/universe.css";
import "./styles/browse.css";
import { App } from "./App";

const root = document.getElementById("root");
if (!root) throw new Error("The page has no #root element.");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
