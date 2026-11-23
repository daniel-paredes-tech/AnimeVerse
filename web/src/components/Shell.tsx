import { Outlet } from "react-router";
import { Colophon } from "./Colophon";
import { Masthead } from "./Masthead";

export function Shell() {
  return (
    <div className="shell">
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <Masthead />
      <main id="content" className="shell__main" tabIndex={-1}>
        <Outlet />
      </main>
      <Colophon />
    </div>
  );
}
