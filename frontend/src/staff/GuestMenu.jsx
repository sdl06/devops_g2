import React, { useEffect, useState } from 'react';
import { getMenu, formatMoney } from '../api.js';

// The menu guests see: only dishes in stock, surplus dishes first and
// highlighted (the ranking is done by the Bill Service's GET /menu).
// Shown as a tab in the staff dashboard and on its own at /guest-menu.
export default function GuestMenu() {
  const [menu, setMenu] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getMenu()
      .then(setMenu)
      .catch((e) => setError(e.message));
  }, []);

  const recommended = (menu ?? []).filter((dish) => dish.surplus);
  const others = (menu ?? []).filter((dish) => !dish.surplus);

  return (
    <section className="staff-panel staff-guest-menu">
      <h2>Menu</h2>
      {error && <p className="staff-error">{error}</p>}
      {menu === null && !error && <p className="staff-empty">Loading…</p>}
      {menu?.length === 0 && <p className="staff-empty">No dishes available right now.</p>}

      {recommended.length > 0 && (
        <>
          <h3>Chef's recommendations</h3>
          <ul className="staff-menu-list">
            {recommended.map((dish) => (
              <li key={dish.id} className="surplus">
                <span>
                  <span className="staff-name">{dish.name}</span>{' '}
                  <span className="badge surplus">Recommended</span>
                </span>
                <span className="staff-price">{formatMoney(dish.price_cents)}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {others.length > 0 && (
        <>
          {recommended.length > 0 && <h3>Everything else</h3>}
          <ul className="staff-menu-list">
            {others.map((dish) => (
              <li key={dish.id}>
                <span className="staff-name">{dish.name}</span>
                <span className="staff-price">{formatMoney(dish.price_cents)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
