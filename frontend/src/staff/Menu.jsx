import React, { useEffect, useState } from 'react';
import {
  getDishes,
  createDish,
  updateDish,
  deleteDish,
  setRecipe,
  getIngredients,
  formatMoney,
} from '../api.js';

const EMPTY_FORM = { name: '', price: '' }; // price typed in euros, e.g. "12.50"

export default function Menu() {
  const [dishes, setDishes] = useState([]);
  const [ingredients, setIngredients] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null); // dish being edited
  const [recipeDishId, setRecipeDishId] = useState(null); // dish whose recipe is open
  const [recipeLines, setRecipeLines] = useState([]); // [{ ingredient_id, amount }]
  const [error, setError] = useState('');

  async function run(action) {
    setError('');
    try {
      await action();
    } catch (e) {
      setError(e.message);
    }
    try {
      const [dishList, ingredientList] = await Promise.all([getDishes(), getIngredients()]);
      setDishes(dishList);
      setIngredients(ingredientList);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    run(async () => {});
  }, []);

  const ingredientById = (id) => ingredients.find((i) => i.id === Number(id));

  // ---------- dish name and price ----------
  function handleSubmit(event) {
    event.preventDefault();
    const dish = {
      name: form.name.trim(),
      price_cents: Math.round(parseFloat(form.price) * 100), // money is stored in cents
    };
    run(async () => {
      if (editingId) await updateDish(editingId, dish);
      else await createDish(dish);
      cancelEdit();
    });
  }

  function startEdit(dish) {
    setEditingId(dish.id);
    setForm({ name: dish.name, price: (dish.price_cents / 100).toFixed(2) });
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  function handleDelete(dish) {
    if (!window.confirm(`Delete ${dish.name}?`)) return;
    run(() => deleteDish(dish.id));
  }

  // ---------- recipe (which ingredients a dish uses) ----------
  function openRecipe(dish) {
    setRecipeDishId(dish.id);
    setRecipeLines(dish.ingredients.map((line) => ({ ...line })));
  }

  const addRecipeLine = () =>
    setRecipeLines([...recipeLines, { ingredient_id: ingredients[0]?.id ?? '', amount: '' }]);

  const updateRecipeLine = (index, field, value) =>
    setRecipeLines(
      recipeLines.map((line, i) => (i === index ? { ...line, [field]: value } : line)),
    );

  const removeRecipeLine = (index) => setRecipeLines(recipeLines.filter((_, i) => i !== index));

  function saveRecipe() {
    const lines = recipeLines.map((line) => ({
      ingredient_id: Number(line.ingredient_id),
      amount: Number(line.amount),
    }));
    run(async () => {
      await setRecipe(recipeDishId, lines);
      setRecipeDishId(null);
    });
  }

  function recipeText(dish) {
    if (dish.ingredients.length === 0) return 'No recipe yet';
    return dish.ingredients
      .map((line) => {
        const ingredient = ingredientById(line.ingredient_id);
        return ingredient ? `${ingredient.name} ${line.amount} ${ingredient.unit}` : '?';
      })
      .join(', ');
  }

  return (
    <section className="staff-panel">
      <h2>Menu</h2>
      {error && <p className="staff-error">{error}</p>}

      <form className="staff-form" onSubmit={handleSubmit}>
        <input
          placeholder="Dish name, e.g. Chicken curry"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          required
        />
        <input
          className="short"
          type="number"
          min="0"
          step="0.01"
          placeholder="Price (€)"
          value={form.price}
          onChange={(e) => setForm({ ...form, price: e.target.value })}
          required
        />
        <button type="submit">{editingId ? 'Save' : 'Add dish'}</button>
        {editingId && (
          <button type="button" className="secondary" onClick={cancelEdit}>
            Cancel
          </button>
        )}
      </form>

      {dishes.length === 0 ? (
        <p className="staff-empty">No dishes yet.</p>
      ) : (
        <ul className="staff-list">
          {dishes.map((dish) => (
            <li key={dish.id} className="staff-dish">
              <div className="staff-dish-row">
                <div>
                  <span className="staff-name">{dish.name}</span>{' '}
                  <span className="staff-price">{formatMoney(dish.price_cents)}</span>
                  <div className="staff-sub">{recipeText(dish)}</div>
                </div>
                <div className="staff-actions">
                  <button className="secondary" onClick={() => startEdit(dish)}>
                    Edit
                  </button>
                  <button className="secondary" onClick={() => openRecipe(dish)}>
                    Recipe
                  </button>
                  <button className="danger" onClick={() => handleDelete(dish)}>
                    Delete
                  </button>
                </div>
              </div>

              {recipeDishId === dish.id && (
                <div className="staff-recipe">
                  {recipeLines.map((line, index) => (
                    <div key={index} className="staff-recipe-line">
                      <select
                        value={line.ingredient_id}
                        onChange={(e) => updateRecipeLine(index, 'ingredient_id', e.target.value)}
                      >
                        {ingredients.map((i) => (
                          <option key={i.id} value={i.id}>
                            {i.name}
                          </option>
                        ))}
                      </select>
                      <input
                        className="short"
                        type="number"
                        min="1"
                        placeholder="Amount"
                        value={line.amount}
                        onChange={(e) => updateRecipeLine(index, 'amount', e.target.value)}
                      />
                      <span>{ingredientById(line.ingredient_id)?.unit}</span>
                      <button className="secondary" onClick={() => removeRecipeLine(index)}>
                        Remove
                      </button>
                    </div>
                  ))}
                  {ingredients.length === 0 ? (
                    <p className="staff-empty">Add ingredients in the Stock tab first.</p>
                  ) : (
                    <button className="secondary" onClick={addRecipeLine}>
                      + Ingredient
                    </button>
                  )}
                  <div className="staff-actions">
                    <button onClick={saveRecipe}>Save recipe</button>
                    <button className="secondary" onClick={() => setRecipeDishId(null)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
