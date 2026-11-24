/**
 * Admin page — ADMIN-only management console.
 * Tabs: Beds | Doctors | Shifts | Users | Activity Log
 */
import { useState } from 'react';
import Tabs from '../components/ui/Tabs.jsx';
import BedsTab       from '../components/admin/BedsTab.jsx';
import DoctorsTab    from '../components/admin/DoctorsTab.jsx';
import ShiftsTab     from '../components/admin/ShiftsTab.jsx';
import UsersTab      from '../components/admin/UsersTab.jsx';
import ActivityLogTab from '../components/admin/ActivityLogTab.jsx';

const TABS = [
  { key: 'beds',     label: 'Beds'         },
  { key: 'doctors',  label: 'Doctors'      },
  { key: 'shifts',   label: 'Shifts'       },
  { key: 'users',    label: 'Users'        },
  { key: 'activity', label: 'Activity Log' },
];

export default function Admin() {
  const [tab, setTab] = useState('beds');

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-5">Admin Console</h1>
      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === 'beds'     && <BedsTab />}
      {tab === 'doctors'  && <DoctorsTab />}
      {tab === 'shifts'   && <ShiftsTab />}
      {tab === 'users'    && <UsersTab />}
      {tab === 'activity' && <ActivityLogTab />}
    </div>
  );
}
