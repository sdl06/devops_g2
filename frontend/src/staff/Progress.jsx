import React, { useEffect, useState } from 'react';
import { getProgress, formatMoney } from '../api.js';

const REFRESH_MS = 10000; // check the guests' progress every 10 seconds

// Live payment progress for an open bill, from the Split Service.
// The Close button only works once the Split Service says ready_to_close.
export default function Progress({ bill, login, setLogin, onClose }) {
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // While logged in, load the progress now and then every 10 seconds.
  // Reloads when the bill changes (e.g. an item is added).
  useEffect(() => {
    if (!login) return undefined;
    let active = true;

    async function load() {
      try {
        const data = await getProgress(bill.id, login);
        if (active) {
          setProgress(data);
          setError('');
        }
      } catch (e) {
        if (!active) return;
        if (e.status === 401) {
          setLogin(null); // wrong login: ask again
          setError('Wrong staff username or password.');
        } else if (e.status >= 500 || e.status === 0) {
          // Partial failure: the rest of the dashboard keeps working.
          setError('Payment progress is unavailable right now. Retrying…');
        } else {
          setError(e.message);
        }
      }
    }

    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [bill.id, bill.version, login]);

  function handleLogin(event) {
    event.preventDefault();
    setLogin({ username, password });
    setPassword('');
  }

  if (!login) {
    return (
      <div className="staff-progress">
        <h3>Payment progress</h3>
        <p className="staff-hint">Sign in with the staff login to see what guests have paid.</p>
        {error && <p className="staff-error">{error}</p>}
        <form className="staff-form" onSubmit={handleLogin}>
          <input
            placeholder="Staff username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          <button type="submit">Sign in</button>
        </form>
      </div>
    );
  }

  const unclaimed = progress?.unallocated_subtotal_cents;
  const unpaid = progress?.allocated_unsettled_subtotal_cents;
  const knownAmounts = progress && unclaimed !== null && unpaid !== null;
  const paid = knownAmounts ? Math.max(bill.total_cents - unclaimed - unpaid, 0) : 0;
  const percent = bill.total_cents > 0 ? Math.round((paid / bill.total_cents) * 100) : 0;
  const ready = Boolean(progress?.ready_to_close);

  return (
    <div className="staff-progress">
      <h3>Payment progress</h3>
      {error && <p className="staff-error">{error}</p>}

      {!progress ? (
        <p className="staff-empty">Loading…</p>
      ) : (
        <>
          {knownAmounts ? (
            <>
              <div className="staff-bar">
                <div style={{ width: `${percent}%` }} />
              </div>
              <div className="staff-progress-numbers">
                <div>
                  <small>Paid</small>
                  <strong>{formatMoney(paid)}</strong>
                </div>
                <div>
                  <small>Claimed, not paid</small>
                  <strong>{formatMoney(unpaid)}</strong>
                </div>
                <div>
                  <small>Not claimed yet</small>
                  <strong>{formatMoney(unclaimed)}</strong>
                </div>
              </div>
            </>
          ) : null}
          {progress.needs_review && (
            <p className="staff-error">
              The bill changed after guests claimed items. Some guests need to review their
              claims.
            </p>
          )}
          <p className={ready ? 'staff-ready' : 'staff-hint'}>
            {ready ? '✓ Ready to close' : 'Waiting for guests to claim and pay…'}
          </p>
        </>
      )}

      <div className="staff-actions">
        <button onClick={onClose} disabled={!ready}>
          Close table
        </button>
        <button className="secondary" onClick={() => setLogin(null)}>
          Sign out
        </button>
      </div>
    </div>
  );
}
