import BrandName from "./BrandName";

interface AuthStatusViewProps {
  message: string;
}

export default function AuthStatusView({
  message,
}: AuthStatusViewProps) {
  return (
    <div className="auth-status-page" role="status" aria-live="polite">
      <div className="auth-status-card">
        <span className="auth-status-spinner" aria-hidden="true" />

        <div>
          <strong>
            <BrandName />
          </strong>
          <span>{message}</span>
        </div>
      </div>
    </div>
  );
}