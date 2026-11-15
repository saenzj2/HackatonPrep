import { Link } from "react-router";
import { useI18n } from "../i18n";

/** Shown on later steps when no field was chosen yet. */
export function NeedsField() {
  const { tr } = useI18n();
  return (
    <div className="notice notice--info">
      <h2>{tr("Choose your field first", "Primero elija su campo")}</h2>
      <p>
        {tr(
          "We need a location to look up NASA climate data and soil for your field.",
          "Necesitamos una ubicación para buscar los datos de clima de la NASA y el suelo de su campo.",
        )}
      </p>
      <Link to="/field" className="btn">
        {tr("Go to My field", "Ir a Mi campo")}
      </Link>
    </div>
  );
}
