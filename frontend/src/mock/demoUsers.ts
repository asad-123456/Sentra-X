import type { User } from '../types/sentrax';

export const DEMO_USERS: User[] = [
  {
    id: 'usr-001',
    username: 'analyst_01',
    email: 'analyst@sentrax.internal',
    role: 'Analyst',
    is_active: true,
    created_at: '2026-09-01T00:00:00Z',
  },
  {
    id: 'usr-002',
    username: 'teamlead_mercer',
    email: 'alex.mercer@sentrax.internal',
    role: 'TeamLead',
    is_active: true,
    created_at: '2026-09-01T00:00:00Z',
  },
  {
    id: 'usr-003',
    username: 'admin_sys',
    email: 'admin@sentrax.internal',
    role: 'Admin',
    is_active: true,
    created_at: '2026-09-01T00:00:00Z',
  },
];
