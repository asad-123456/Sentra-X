import React, { useRef, useState } from 'react';
import {
  Users,
  UserPlus,
  Shield,
  Check,
  X,
  AlertCircle,
} from 'lucide-react';
import type { User, UserRole } from '../../types/sentrax';
import { ApiError } from '../../api/client';
import { Button } from '../ui/button';

interface UserManagementTableProps {
  users: User[];
  onUpdateRole: (userId: string, role: UserRole) => Promise<void>;
  onToggleActive: (userId: string, isActive: boolean) => Promise<void>;
  onCreateUser: (newUser: Omit<User, 'id' | 'created_at'>) => Promise<string | undefined>;
}

export const UserManagementTable: React.FC<UserManagementTableProps> = ({
  users,
  onUpdateRole,
  onToggleActive,
  onCreateUser,
}) => {
  const [showAddDrawer, setShowAddDrawer] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('Analyst');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [createdAccount, setCreatedAccount] = useState<{ username: string; password?: string } | null>(null);
  const usernameField = useRef<HTMLInputElement>(null);

  // Confirmation guard modal state
  const [confirmModal, setConfirmModal] = useState<{
    type: 'ROLE' | 'STATUS';
    user: User;
    targetRole?: UserRole;
    targetStatus?: boolean;
  } | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

  const handleConfirmAction = async () => {
    if (!confirmModal) return;
    setIsUpdating(true);
    try {
      if (confirmModal.type === 'ROLE' && confirmModal.targetRole) {
        await onUpdateRole(confirmModal.user.id, confirmModal.targetRole);
      } else if (confirmModal.type === 'STATUS' && confirmModal.targetStatus !== undefined) {
        await onToggleActive(confirmModal.user.id, confirmModal.targetStatus);
      }
      setConfirmModal(null);
    } catch (err) {
      console.error('Failed to update user:', err);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !email.trim()) {
      setFormError('Enter a username and email address.');
      usernameField.current?.focus();
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const password = await onCreateUser({
        username: username.trim(),
        email: email.trim(),
        role,
        is_active: true,
      });
      setCreatedAccount({ username: username.trim(), password });
      setUsername('');
      setEmail('');
      setRole('Analyst');
      setShowAddDrawer(false);
    } catch (err) {
      setFormError(err instanceof ApiError && err.status < 500
        ? err.message
        : 'Unable to create the account. Check your connection and try again.');
      usernameField.current?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden flex flex-col">
      <div className="p-4 border-b border-zinc-800/80 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold font-mono text-zinc-100 flex items-center gap-2">
            <Users className="size-4 text-zinc-400" />
            User Accounts & Role Permissions
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Manage authenticated security analysts, team leads, and system administrators
          </p>
        </div>

        {!showAddDrawer && <Button
          type="button"
          onClick={() => { setCreatedAccount(null); setFormError(null); setShowAddDrawer(true); }}
          className="self-start sm:self-auto"
        >
          <UserPlus className="size-3.5" />
          Create user
        </Button>}
      </div>

      {createdAccount && (
        <section aria-labelledby="created-user-title" className="border-b border-border bg-secondary px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 id="created-user-title" role="status" className="text-sm font-medium">Account created for {createdAccount.username}</h3>
            <Button variant="ghost" onClick={() => setCreatedAccount(null)}>Dismiss</Button>
          </div>
          {createdAccount.password && (
            <div className="max-w-sm space-y-1">
              <label htmlFor="new-user-password" className="text-sm">Temporary password</label>
              <input id="new-user-password" className="field font-mono" readOnly value={createdAccount.password} aria-describedby="new-user-password-note" />
              <p id="new-user-password-note" className="text-xs text-muted-foreground">Save this password before leaving this tab. It is displayed once.</p>
            </div>
          )}
        </section>
      )}

      {/* Inline Create User Drawer */}
      {showAddDrawer && (
        <form onSubmit={handleCreate} className="p-4 border-b border-zinc-800 bg-zinc-900/30 space-y-3">
          <div className="text-xs font-mono text-zinc-300 font-semibold flex items-center gap-1.5">
            <UserPlus className="size-3.5 text-emerald-400" />
            Create Authenticated User
          </div>

          {formError && (
            <div id="create-user-error" role="alert" className="p-2.5 rounded bg-red-950/40 border border-red-800/60 text-sm text-red-300 flex items-center gap-2">
              <AlertCircle className="size-3.5 shrink-0" />
              {formError}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label htmlFor="new-user-username" className="text-sm text-foreground">Username</label>
              <input
                id="new-user-username"
                ref={usernameField}
                required
                minLength={3}
                maxLength={64}
                pattern="[A-Za-z0-9._\-]+"
                aria-describedby={formError ? 'new-user-username-limit create-user-error' : 'new-user-username-limit'}
                type="text"
                placeholder="e.g. analyst_02"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="field"
              />
              <p id="new-user-username-limit" className="text-xs text-muted-foreground">3–64 letters, digits, periods, underscores, or hyphens.</p>
            </div>

            <div className="space-y-1">
              <label htmlFor="new-user-email" className="text-sm text-foreground">Email address</label>
              <input
                id="new-user-email"
                required
                aria-describedby={formError ? 'create-user-error' : undefined}
                type="email"
                placeholder="e.g. analyst02@sentrax.internal"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="field"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="new-user-role" className="text-sm text-foreground">Assigned role</label>
              <select
                id="new-user-role"
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="field"
              >
                <option value="Analyst">Analyst</option>
                <option value="TeamLead">TeamLead</option>
                <option value="Admin">Admin</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setShowAddDrawer(false)}
              className="px-3 py-1 rounded-lg border border-zinc-800 text-xs font-mono text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1 rounded-lg bg-zinc-100 text-zinc-950 font-mono text-xs font-semibold hover:bg-zinc-200 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Save User'}
            </button>
          </div>
        </form>
      )}

      {/* Users Table */}
      <div className="table-region" tabIndex={0} role="region" aria-label="User accounts table">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="bg-zinc-900/60 text-zinc-400 font-mono text-[11px] uppercase tracking-wider border-b border-zinc-800">
              <th className="py-3 px-4">User ID</th>
              <th className="py-3 px-4">Username</th>
              <th className="py-3 px-4">Email</th>
              <th className="py-3 px-4">Assigned Role</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Created Date</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 font-mono">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-zinc-900/30 transition-colors">
                <td className="py-3 px-4 text-zinc-400">{u.id}</td>
                <td className="py-3 px-4 font-semibold text-zinc-200 flex items-center gap-2">
                  <div className="size-6 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center text-[10px] text-zinc-400">
                    {u.username.slice(0, 2).toUpperCase()}
                  </div>
                  {u.username}
                </td>
                <td className="py-3 px-4 text-zinc-400">{u.email}</td>
                <td className="py-3 px-4">
                  <select
                    aria-label={`Role for ${u.username}`}
                    value={u.role}
                    onChange={(e) => {
                      const targetRole = e.target.value as UserRole;
                      if (targetRole !== u.role) {
                        setConfirmModal({
                          type: 'ROLE',
                          user: u,
                          targetRole,
                        });
                      }
                    }}
                    className="field min-w-24"
                  >
                    <option value="Analyst">Analyst</option>
                    <option value="TeamLead">TeamLead</option>
                    <option value="Admin">Admin</option>
                  </select>
                </td>
                <td className="py-3 px-4">
                  {u.is_active ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
                      <Check className="size-2.5" />
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-500">
                      <X className="size-2.5" />
                      Deactivated
                    </span>
                  )}
                </td>
                <td className="py-3 px-4 text-zinc-500 text-[11px]">
                  {u.created_at.slice(0, 10)}
                </td>
                <td className="py-3 px-4 text-right">
                  <button
                    type="button"
                    onClick={() => {
                      setConfirmModal({
                        type: 'STATUS',
                        user: u,
                        targetStatus: !u.is_active,
                      });
                    }}
                    className={`px-2 py-1 rounded text-xs font-mono transition-colors cursor-pointer ${
                      u.is_active
                        ? 'border border-red-900/60 text-red-400 hover:bg-red-950/30'
                        : 'border border-emerald-900/60 text-emerald-400 hover:bg-emerald-950/30'
                    }`}
                  >
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="p-3 border-t border-zinc-800/80 bg-zinc-900/30 flex items-center justify-between text-xs text-zinc-400">
        <span className="flex items-center gap-1.5">
          <Shield className="size-3.5 text-zinc-500" />
          Enforces role-based view guarding across Triage Queue, Analytics, Governance, and Admin routes.
        </span>
        <span className="font-mono text-[11px] text-zinc-400">
          Total Users: {users.length}
        </span>
      </div>

      {/* Confirmation Guard Modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-zinc-950 border border-zinc-750 rounded-xl p-5 max-w-sm w-full space-y-4 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-amber-950/60 border border-amber-800/60 text-amber-400">
                <AlertCircle className="size-4" />
              </div>
              <h3 className="text-sm font-semibold font-mono text-zinc-100">
                {confirmModal.type === 'ROLE'
                  ? 'Confirm Role Modification'
                  : 'Confirm Account Status Change'}
              </h3>
            </div>

            <p className="text-xs text-zinc-300 font-sans leading-relaxed">
              {confirmModal.type === 'ROLE' ? (
                <>
                  Are you sure you want to change user{' '}
                  <span className="font-mono font-bold text-white">@{confirmModal.user.username}</span>'s role from{' '}
                  <span className="font-mono text-zinc-400">{confirmModal.user.role}</span> to{' '}
                  <span className="font-mono font-bold text-cyan-400">{confirmModal.targetRole}</span>?
                </>
              ) : (
                <>
                  Are you sure you want to{' '}
                  <span className="font-mono font-bold text-white">
                    {confirmModal.targetStatus ? 'ACTIVATE' : 'DEACTIVATE'}
                  </span>{' '}
                  the account for user{' '}
                  <span className="font-mono font-bold text-white">@{confirmModal.user.username}</span>?
                </>
              )}
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                disabled={isUpdating}
                onClick={() => setConfirmModal(null)}
                className="px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-mono text-zinc-300 hover:bg-zinc-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isUpdating}
                onClick={handleConfirmAction}
                className="px-4 py-1.5 rounded-lg bg-white text-zinc-950 font-mono text-xs font-semibold hover:bg-zinc-200 transition-colors disabled:opacity-50"
              >
                {isUpdating ? 'Updating...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

