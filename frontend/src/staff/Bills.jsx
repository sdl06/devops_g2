import React, { useEffect, useState } from 'react';
import {
  getBills,
  getTables,
  getDishes,
  createBill,
  deleteBill,
  openBill,
  closeBill,
  formatMoney,
} from '../api.js';
import BillDetail from './BillDetail.jsx';

export default function Bills() {
  const [bills, setBills] = useState([]);
  const [tables, setTables] = useState([]);
  const [dishes, setDishes] = useState([]);
  const [newTableId, setNewTableId] = useState('');
  const [selectedId, setSelectedId] = useState(null); // bill shown on the right
  const [showClosed, setShowClosed] = useState(false);
  // Staff login for the payment progress check. Kept in memory only:
  // it disappears when the page is reloaded.
  const [login, setLogin] = useState(null);
  const [error, setError] = useState('');

  async function run(action) {
    setError('');
    try {
      await action();
    } catch (e) {
      setError(e.message);
    }
    try {
      const [billList, tableList, dishList] = await Promise.all([
        getBills(),
        getTables(),
        getDishes(),
      ]);
      setBills(billList);
      setTables(tableList);
      setDishes(dishList);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    run(async () => {});
  }, []);

  const tableName = (id) => tables.find((t) => t.id === id)?.name ?? `Table ${id}`;
  const visibleBills = bills.filter((b) => showClosed || b.status !== 'closed');
  const selectedBill = bills.find((b) => b.id === selectedId);

  function handleCreate(event) {
    event.preventDefault();
    if (!newTableId) return;
    run(async () => {
      const bill = await createBill(Number(newTableId));
      setSelectedId(bill.id);
      setNewTableId('');
    });
  }

  return (
    <div className="staff-bills">
      <section className="staff-panel">
        <h2>Bills</h2>
        {error && <p className="staff-error">{error}</p>}

        <form className="staff-form" onSubmit={handleCreate}>
          <select value={newTableId} onChange={(e) => setNewTableId(e.target.value)}>
            <option value="">Choose a table…</option>
            {tables.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <button type="submit">New bill</button>
        </form>

        <label className="staff-check">
          <input
            type="checkbox"
            checked={showClosed}
            onChange={(e) => setShowClosed(e.target.checked)}
          />
          Show closed bills
        </label>

        {visibleBills.length === 0 ? (
          <p className="staff-empty">No bills yet.</p>
        ) : (
          <ul className="staff-list staff-bill-list">
            {visibleBills.map((bill) => (
              <li
                key={bill.id}
                className={bill.id === selectedId ? 'selected' : ''}
                onClick={() => setSelectedId(bill.id)}
              >
                <div>
                  <span className="staff-name">{tableName(bill.table_id)}</span>
                  <div className="staff-sub">
                    Bill #{bill.id} · {formatMoney(bill.total_cents)}
                  </div>
                </div>
                <span className={`badge ${bill.status}`}>{bill.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selectedBill ? (
        <BillDetail
          key={selectedBill.id}
          bill={selectedBill}
          tableName={tableName(selectedBill.table_id)}
          dishes={dishes}
          login={login}
          setLogin={setLogin}
          run={run}
          onOpen={() => run(() => openBill(selectedBill.id))}
          onClose={() => run(() => closeBill(selectedBill.id))}
          onDelete={() =>
            run(async () => {
              await deleteBill(selectedBill.id);
              setSelectedId(null);
            })
          }
        />
      ) : (
        <section className="staff-panel staff-empty-panel">
          <p className="staff-empty">Select a bill, or create one for a table.</p>
        </section>
      )}
    </div>
  );
}
