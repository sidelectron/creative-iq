import { useAuth } from "../contexts/AuthContext";

export function AccountPage(): React.ReactElement {
  const { user } = useAuth();
  return (
    <div className="mx-auto max-w-lg">
      <h2 className="text-section">Account</h2>
      <dl className="mt-4 space-y-2 text-body">
        <div>
          <dt className="text-datalabel text-muted">Name</dt>
          <dd>{user?.full_name}</dd>
        </div>
        <div>
          <dt className="text-datalabel text-muted">Email</dt>
          <dd>{user?.email}</dd>
        </div>
      </dl>
    </div>
  );
}
