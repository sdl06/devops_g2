import React, { useState } from 'react';
import Tables from './Tables.jsx';
import Menu from './Menu.jsx';
import Stock from './Stock.jsx';

// Each tab: [label shown on the button, screen component]
const TABS = {
  tables: ['Tables', Tables],
  menu: ['Menu', Menu],
  stock: ['Stock', Stock],
};

export default function StaffApp() {
  const [tab, setTab] = useState('tables');
  const Screen = TABS[tab][1];

  return (
    <div className="staff">
      <header className="staff-header">
        <div className="staff-brand">
          Easy<span>Pay</span> <small>Staff</small>
        </div>
        <nav className="staff-tabs">
          {Object.entries(TABS).map(([key, [label]]) => (
            <button
              key={key}
              className={key === tab ? 'active' : ''}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>
      <main className="staff-main">
        <Screen />
      </main>
    </div>
  );
}
