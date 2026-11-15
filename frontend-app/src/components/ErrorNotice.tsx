import { errorText } from "../api/errors";
import { DEMO_FIELDS, type DemoField } from "../demoFields";
import { useI18n } from "../i18n";

interface Props {
  error: unknown;
  onRetry?: () => void;
  /** Shown when the error says a demo field is the way out (cache_miss, out_of_region). */
  onPickDemo?: (field: DemoField) => void;
}

export function ErrorNotice({ error, onRetry, onPickDemo }: Props) {
  const { tr, pick } = useI18n();
  const text = errorText(error);
  return (
    <div className="notice" role="alert">
      <h3>{pick(text.title)}</h3>
      <p>{pick(text.body)}</p>
      <div className="btn-row">
        {text.offerDemoFields &&
          onPickDemo &&
          DEMO_FIELDS.map((field) => (
            <button key={field.id} type="button" className="btn" onClick={() => onPickDemo(field)}>
              {tr(`Use ${field.name}`, `Usar ${field.name}`)}
            </button>
          ))}
        {onRetry && !text.offerDemoFields && (
          <button type="button" className="btn btn--secondary" onClick={onRetry}>
            {tr("Try again", "Intentar de nuevo")}
          </button>
        )}
      </div>
    </div>
  );
}
