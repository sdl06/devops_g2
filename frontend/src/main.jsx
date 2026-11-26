import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import StaffApp from './staff/StaffApp.jsx';
import GuestMenu from './staff/GuestMenu.jsx';
import './style.css';
import './staff/staff.css';

// Pick the page from the address:
//   /staff       -> staff dashboard
//   /guest-menu  -> the guest menu, surplus dishes first
//   anything else -> the guest page (the one the QR code opens)
const path = window.location.pathname;

let page = <App />;
if (path.startsWith('/staff')) page = <StaffApp />;
else if (path.startsWith('/guest-menu'))
  page = (
    <div className="staff">
      <GuestMenu />
    </div>
  );

createRoot(document.getElementById('root')).render(page);
