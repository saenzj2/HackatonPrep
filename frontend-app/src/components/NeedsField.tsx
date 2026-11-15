import { Link } from "react-router";

/** Shown on later steps when no field was chosen yet. */
export function NeedsField() {
  return (
    <div className="notice notice--info">
      <h2>Choose your field first</h2>
      <p>We need a location to look up NASA climate data and soil for your field.</p>
      <Link to="/field" className="btn">
        Go to My field
      </Link>
    </div>
  );
}
