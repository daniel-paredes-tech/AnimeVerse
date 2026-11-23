import { Link, NavLink } from "react-router";
import { issueLabel } from "../lib/labels";

export function Masthead({ today = new Date() }: { today?: Date }) {
  const issue = issueLabel(today);
  return (
    <header className="masthead">
      <div className="masthead__bar">
        <Link to="/" className="masthead__logotype">
          AnimeVerse
        </Link>
        <p className="masthead__issue">
          <span className="masthead__issue-no">{issue.number}</span>
          <time dateTime={today.toISOString().slice(0, 10)}>{issue.date}</time>
        </p>
        <nav className="masthead__nav" aria-label="Main">
          <NavLink to="/" end>
            Universe
          </NavLink>
          <span aria-hidden="true" className="masthead__dot">
            ·
          </span>
          <NavLink to="/anime">Browse</NavLink>
        </nav>
      </div>
    </header>
  );
}
