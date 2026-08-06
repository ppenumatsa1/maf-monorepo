import type { UnderwritingApplication } from '../api'

type Props = {
  application: UnderwritingApplication
  onChange: (next: UnderwritingApplication) => void
}

export function ApplicationSection({ application, onChange }: Props) {
  return (
    <section className="card application-card form-grid">
      <h2>Application Input</h2>
      {Object.entries(application).map(([key, value]) => (
        <label key={key} className="field">
          {key}
          <input
            data-testid={`field-${key}`}
            value={String(value)}
            onChange={(e) =>
              onChange({
                ...application,
                [key]:
                  key === 'age' || key === 'credit_score' || key === 'income' || key === 'requested_coverage'
                    ? Number(e.target.value)
                    : e.target.value,
              })
            }
          />
        </label>
      ))}
    </section>
  )
}
