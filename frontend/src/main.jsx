import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import StaffApp from './staff/StaffApp.jsx';
import './style.css';
import './staff/staff.css';

// /staff shows the staff dashboard; every other address shows the guest page
// (the one the QR code opens).
const isStaff = window.location.pathname.startsWith('/staff');

createRoot(document.getElementById('root')).render(isStaff ? <StaffApp /> : <App />);
