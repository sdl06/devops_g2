import React, { useState } from 'react';
import { addItem, updateItem, deleteItem, formatMoney } from '../api.js';
import Progress from './Progress.jsx';

// One bill: its items, the actions for its status, and (when open) the
// guests' payment progress with the Close button.
export default function BillDetail({
  bill,
  tableName,
  dishes,
  login,
  setLogin,
  run,
  onOpen,
  onClose,
  onDelete,
}) {
  const [dishId, setDishId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const editable = bill.status !== 'closed';
  const guestLink = `${window.location.origin}/?table_id=${bill.table_id}`;

  function handleAdd(event) {
    event.preventDefault();
    if (!dishId) return;
    run(async () => {
      await addItem(bill.id, Number(dishId), Number(quantity));
      setDishId('');
      setQuantity('1');
    });
  }

  // + and − buttons: change the quantity by one; going below 1 removes the item.
  function changeQuantity(item, change) {
    const newQuantity = item.quantity + change;
    run(() =>
      newQuantity < 1
        ? deleteItem(bill.id, item.id)
        : updateItem(bill.id, item.id, newQuantity),
    );
  }

  return (
    <section className="staff-panel">
      <div className="staff-bill-head">
        <div>
          <h2>{tableName}</h2>
          <div className="staff-sub">
            Bill #{bill.id} · version {bill.version}
          </div>
        </div>
        <span className={`badge ${bill.status}`}>{bill.status}</span>
      </div>

      {bill.items.length === 0 ? (
        <p className="staff-empty">No items yet.</p>
      ) : (
        <table className="staff-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {bill.items.map((item) => (
              <tr key={item.id}>
                <td className="staff-name">{item.name}</td>
                <td>
                  {editable ? (
                    <span className="staff-qty">
                      <button className="secondary" onClick={() => changeQuantity(item, -1)}>
                        −
                      </button>
                      {item.quantity}
                      <button className="secondary" onClick={() => changeQuantity(item, 1)}>
                        +
                      </button>
                    </span>
                  ) : (
                    item.quantity
                  )}
                </td>
                <td>{formatMoney(item.price_cents)}</td>
                <td>{formatMoney(item.total_cents)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan="3">Bill total</td>
              <td>{formatMoney(bill.total_cents)}</td>
            </tr>
          </tfoot>
        </table>
      )}

      {editable && (
        <form className="staff-form staff-add-item" onSubmit={handleAdd}>
          <select value={dishId} onChange={(e) => setDishId(e.target.value)}>
            <option value="">Add a dish…</option>
            {dishes.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} · {formatMoney(d.price_cents)}
              </option>
            ))}
          </select>
          <input
            className="short"
            type="number"
            min="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
          <button type="submit">Add</button>
        </form>
      )}

      {bill.status === 'draft' && (
        <div className="staff-actions staff-bill-actions">
          <button onClick={onOpen}>Open for guests</button>
          <button className="danger" onClick={onDelete}>
            Delete draft
          </button>
        </div>
      )}

      {bill.status === 'open' && (
        <>
          <p className="staff-hint">
            Guest link (what the table's QR code opens):{' '}
            <a href={guestLink} target="_blank" rel="noreferrer">
              {guestLink}
            </a>
          </p>
          <Progress bill={bill} login={login} setLogin={setLogin} onClose={onClose} />
        </>
      )}

      {bill.status === 'closed' && <p className="staff-hint">This table is closed.</p>}
    </section>
  );
}
