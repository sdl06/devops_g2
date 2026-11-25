import React, { useEffect, useState } from 'react';
import { getIngredients, createIngredient, updateIngredient, deleteIngredient } from '../api.js';

const EMPTY_FORM = { name: '', unit: 'g', stock: '', surplus_level: '' };

export default function Stock() {
  const [ingredients, setIngredients] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null); // null = adding a new one
  const [error, setError] = useState('');

  async function run(action) {
    setError('');
    try {
      await action();
    } catch (e) {
      setError(e.message);
    }
    try {
      setIngredients(await getIngredients());
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    run(async () => {});
  }, []);

  // Update one field of the form, e.g. updateField('stock', '5000')
  const updateField = (field, value) => setForm({ ...form, [field]: value });

  function handleSubmit(event) {
    event.preventDefault();
    const ingredient = {
      name: form.name.trim(),
      unit: form.unit.trim(),
      stock: Number(form.stock),
      surplus_level: Number(form.surplus_level),
    };
    run(async () => {
      if (editingId) await updateIngredient(editingId, ingredient);
      else await createIngredient(ingredient);
      cancelEdit();
    });
  }

  function startEdit(ingredient) {
    setEditingId(ingredient.id);
    setForm({
      name: ingredient.name,
      unit: ingredient.unit,
      stock: String(ingredient.stock),
      surplus_level: String(ingredient.surplus_level),
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  function handleDelete(ingredient) {
    if (!window.confirm(`Delete ${ingredient.name}?`)) return;
    // 409 if a dish still uses this ingredient; run() shows the message.
    run(() => deleteIngredient(ingredient.id));
  }

  return (
    <section className="staff-panel">
      <h2>Stock</h2>
      <p className="staff-hint">
        An ingredient is in <strong>surplus</strong> when its stock is above its surplus level.
        Dishes that use it are pushed to the top of the guest menu.
      </p>
      {error && <p className="staff-error">{error}</p>}

      <form className="staff-form" onSubmit={handleSubmit}>
        <input
          placeholder="Name, e.g. Chicken"
          value={form.name}
          onChange={(e) => updateField('name', e.target.value)}
          required
        />
        <input
          className="short"
          placeholder="Unit"
          value={form.unit}
          onChange={(e) => updateField('unit', e.target.value)}
          required
        />
        <input
          className="short"
          type="number"
          min="0"
          placeholder="Stock"
          value={form.stock}
          onChange={(e) => updateField('stock', e.target.value)}
          required
        />
        <input
          className="short"
          type="number"
          min="0"
          placeholder="Surplus level"
          value={form.surplus_level}
          onChange={(e) => updateField('surplus_level', e.target.value)}
          required
        />
        <button type="submit">{editingId ? 'Save' : 'Add ingredient'}</button>
        {editingId && (
          <button type="button" className="secondary" onClick={cancelEdit}>
            Cancel
          </button>
        )}
      </form>

      {ingredients.length === 0 ? (
        <p className="staff-empty">No ingredients yet.</p>
      ) : (
        <table className="staff-table">
          <thead>
            <tr>
              <th>Ingredient</th>
              <th>Stock</th>
              <th>Surplus level</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {ingredients.map((ingredient) => (
              <tr key={ingredient.id}>
                <td className="staff-name">{ingredient.name}</td>
                <td>
                  {ingredient.stock} {ingredient.unit}
                </td>
                <td>
                  {ingredient.surplus_level} {ingredient.unit}
                </td>
                <td>
                  {ingredient.stock > ingredient.surplus_level ? (
                    <span className="badge surplus">Surplus</span>
                  ) : (
                    <span className="badge">Normal</span>
                  )}
                </td>
                <td className="staff-actions">
                  <button className="secondary" onClick={() => startEdit(ingredient)}>
                    Edit
                  </button>
                  <button className="danger" onClick={() => handleDelete(ingredient)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
