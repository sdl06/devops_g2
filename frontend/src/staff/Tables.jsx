import React, { useEffect, useState } from 'react';
import { getTables, createTable, renameTable, deleteTable } from '../api.js';

export default function Tables() {
  const [tables, setTables] = useState([]);
  const [newName, setNewName] = useState('');
  const [editingId, setEditingId] = useState(null); // table being renamed
  const [editName, setEditName] = useState('');
  const [error, setError] = useState('');

  // Run an API call, show its error message if it fails, then reload the list.
  async function run(action) {
    setError('');
    try {
      await action();
    } catch (e) {
      setError(e.message);
    }
    try {
      setTables(await getTables());
    } catch (e) {
      setError(e.message);
    }
  }

  // Load the tables once when the screen opens.
  useEffect(() => {
    run(async () => {});
  }, []);

  function handleAdd(event) {
    event.preventDefault();
    if (!newName.trim()) return;
    run(async () => {
      await createTable(newName.trim());
      setNewName('');
    });
  }

  function startRename(table) {
    setEditingId(table.id);
    setEditName(table.name);
  }

  function saveRename(id) {
    if (!editName.trim()) return;
    run(async () => {
      await renameTable(id, editName.trim());
      setEditingId(null);
    });
  }

  function handleDelete(table) {
    if (!window.confirm(`Delete ${table.name}?`)) return;
    // The Bill Service answers 409 if the table still has an open bill;
    // run() shows that message.
    run(() => deleteTable(table.id));
  }

  return (
    <section className="staff-panel">
      <h2>Tables</h2>
      {error && <p className="staff-error">{error}</p>}

      <form className="staff-form" onSubmit={handleAdd}>
        <input
          placeholder="New table name, e.g. Table 4"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button type="submit">Add table</button>
      </form>

      {tables.length === 0 ? (
        <p className="staff-empty">No tables yet.</p>
      ) : (
        <ul className="staff-list">
          {tables.map((table) => (
            <li key={table.id}>
              {editingId === table.id ? (
                <>
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} />
                  <div className="staff-actions">
                    <button onClick={() => saveRename(table.id)}>Save</button>
                    <button className="secondary" onClick={() => setEditingId(null)}>
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <span className="staff-name">{table.name}</span>
                  <div className="staff-actions">
                    <button className="secondary" onClick={() => startRename(table)}>
                      Rename
                    </button>
                    <button className="danger" onClick={() => handleDelete(table)}>
                      Delete
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
