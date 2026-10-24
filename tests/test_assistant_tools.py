"""Herramientas de ChefWise: cálculos deterministas, validación y errores controlados."""

from __future__ import annotations

import pytest

from backend.assistant.ingredients import parse_ingredient
from backend.assistant.tools import Tool, ToolRegistry, default_registry
from backend.assistant.tools.base import ToolInput, ToolOutput

from tests.assistant_fixtures import tool_ctx

REGISTRY = default_registry()


def run(name, args, ctx=None):
    out, record = REGISTRY.execute(name, args, ctx or tool_ctx())
    assert record.name == name and record.duration_ms >= 0
    return out


def ok(name, args, ctx=None):
    out = run(name, args, ctx)
    assert out["ok"], out
    return out["result"]


def error_code(name, args, ctx=None):
    out = run(name, args, ctx)
    assert not out["ok"], out
    return out["error"]["code"]


# ------------------------------------------------------------------ parseo


@pytest.mark.parametrize(
    "line, amount, amount_max, unit, name",
    [
        ("1 kilogramo de Filete de pescado cortado en tiras", 1.0, None, "kg", "Filete de pescado cortado en tiras"),
        ("¼ cucharadita de Polvo para hornear", 0.25, None, "tsp", "Polvo para hornear"),
        ("2 cucharadas soperas de Aceite", 2.0, None, "tbsp", "Aceite"),
        ("1 1/2 tazas de leche", 1.5, None, "cup", "leche"),
        ("1,5 kg de carne", 1.5, None, "kg", "carne"),
        ("100 grs. tocino o panceta", 100.0, None, "g", "tocino o panceta"),
        ("2-3 dientes de ajo", 2.0, 3.0, "dientes", "ajo"),
        ("1 Zanahoria grande", 1.0, None, None, "Zanahoria grande"),
        ("Aceite de oliva y sal", None, None, None, "Aceite de oliva y sal"),
    ],
)
def test_parse_ingredient(line, amount, amount_max, unit, name):
    p = parse_ingredient(line)
    assert (p.amount, p.amount_max, p.unit, p.name, p.text) == (amount, amount_max, unit, name, line)


def test_parse_ingredient_optional_and_notes():
    p = parse_ingredient("1 taza de Harina de trigo (140 gramos)")
    assert p.notes == "140 gramos"
    assert parse_ingredient("1 guindilla (opcional)").optional
    assert parse_ingredient("sal al gusto").notes == "al gusto"


# ------------------------------------------------------------------ escalado


def test_scaling_uses_real_recipe_and_rounds():
    r = ok("calculate_recipe_scaling", {"servings_target": 7})
    assert r["servings_original"] == 4 and r["scaling_factor"] == 1.75
    by_name = {i["name"]: i for i in r["scaled_ingredients"]}
    assert by_name["pollo en piezas"]["amount"] == 1.75 and by_name["pollo en piezas"]["unit"] == "kg"
    assert by_name["leche"]["amount_display"] == "2 ⅔"  # 1.5 × 1.75 = 2.625 -> fracción casera
    huevo = by_name["huevo"]
    assert huevo["amount"] == 4 and "3.50" in huevo["note"]  # 3.5 huevos -> 4, con el cálculo exacto
    assert by_name["ajo"]["amount_display"] == "3 ½ a 5 ¼"  # rango escalado en ambos extremos
    warnings = " ".join(r["warnings"])
    for word in ("Huevos", "Levadura", "Sal", "recipientes"):
        assert word in warnings


def test_scaling_does_not_touch_ingredients_without_amount():
    r = ok("calculate_recipe_scaling", {"servings_target": 4}, tool_ctx(current=2))
    assert all(not i["scaled"] and i["amount"] is None for i in r["scaled_ingredients"])
    assert any("no se escalaron" in w for w in r["warnings"])


def test_scaling_without_servings_asks_instead_of_guessing():
    assert error_code("calculate_recipe_scaling", {"servings_target": 6}, tool_ctx(current=3)) == "missing_servings"
    # Con el dato del usuario sí funciona.
    r = ok("calculate_recipe_scaling", {"servings_target": 6, "servings_original": 3}, tool_ctx(current=3))
    assert r["scaling_factor"] == 2


def test_scaling_explicit_ingredients():
    r = ok(
        "calculate_recipe_scaling",
        {"servings_original": 2, "servings_target": 3, "ingredients": [{"name": "harina", "amount": 250, "unit": "g"}]},
        tool_ctx(current=None),
    )
    assert r["scaled_ingredients"][0]["amount"] == 375


@pytest.mark.parametrize("args", [{"servings_target": 0}, {"servings_target": -2}, {"servings_target": 500}])
def test_scaling_invalid_servings(args):
    assert error_code("calculate_recipe_scaling", args) == "invalid_input"


def test_scaling_negative_amount_is_invalid():
    args = {"servings_original": 2, "servings_target": 4, "ingredients": [{"name": "sal", "amount": -1, "unit": "g"}]}
    assert error_code("calculate_recipe_scaling", args) == "invalid_input"


def test_scaling_unknown_recipe_and_no_recipe():
    assert error_code("calculate_recipe_scaling", {"servings_target": 2, "recipe_id": 999}) == "recipe_not_found"
    assert error_code("calculate_recipe_scaling", {"servings_target": 2}, tool_ctx(current=None)) == "no_recipe"


# ---------------------------------------------------------------- conversión


def test_convert_grams_to_other_weight_units_is_exact():
    r = ok("convert_cooking_units", {"value": 500, "from_unit": "gramos", "to_unit": "lb"})
    assert r["exact"] and r["result"] == 1.1  # 500 / 453.59 = 1.102
    assert ok("convert_cooking_units", {"value": 1.5, "from_unit": "kg", "to_unit": "g"})["result"] == 1500


def test_convert_temperature_both_ways():
    assert ok("convert_cooking_units", {"value": 180, "from_unit": "°C", "to_unit": "°F"})["result"] == 356
    assert ok("convert_cooking_units", {"value": 350, "from_unit": "F", "to_unit": "celsius"})["result"] == 177
    assert ok("convert_cooking_units", {"value": -18, "from_unit": "C", "to_unit": "F"})["result"] == 0


def test_convert_volume_to_weight_uses_density_and_is_marked_approximate():
    r = ok("convert_cooking_units", {"value": 1, "from_unit": "taza", "to_unit": "g", "ingredient": "harina de trigo"})
    assert r["result"] == 125 and not r["exact"] and "harina" in r["method"]


def test_convert_volume_to_weight_unknown_ingredient_is_estimate():
    r = ok("convert_cooking_units", {"value": 1, "from_unit": "cup", "to_unit": "g", "ingredient": "mermelada de higo"})
    assert not r["exact"]
    assert any("ESTIMACIÓN" in w for w in r["warnings"])


def test_convert_grams_are_not_milliliters_without_ingredient():
    r = ok("convert_cooking_units", {"value": 100, "from_unit": "g", "to_unit": "ml"})
    assert not r["exact"] and any("no son equivalentes" in w for w in r["warnings"])


def test_convert_errors():
    assert error_code("convert_cooking_units", {"value": 1, "from_unit": "g", "to_unit": "parsecs"}) == "unknown_unit"
    assert error_code("convert_cooking_units", {"value": -5, "from_unit": "g", "to_unit": "kg"}) == "negative_value"
    assert error_code("convert_cooking_units", {"value": 5, "from_unit": "g", "to_unit": "°C"}) == "incompatible_units"
    assert error_code("convert_cooking_units", {"value": "mucho", "from_unit": "g", "to_unit": "kg"}) == "invalid_input"
    assert error_code("convert_cooking_units", {"value": 1, "from_unit": "g"}) == "invalid_input"


# --------------------------------------------------------------- sustitución


def test_substitution_has_function_ratio_and_amount():
    r = ok("ingredient_substitution", {"ingredient": "mantequilla", "amount": 100, "unit": "g", "recipe_context": "panqué"})
    assert r["found"] and "Grasa" in r["function"]
    oil = next(s for s in r["substitutions"] if s["substitute"].startswith("aceite vegetal"))
    assert oil["amount"] == "75 g" and oil["texture_changes"]
    assert r["ratio"] and r["instructions"] is not None


def test_substitution_context_orders_options():
    r = ok("ingredient_substitution", {"ingredient": "cerveza", "recipe_context": "capeado de pescado"})
    assert r["substitutions"][0]["substitute"].startswith("agua mineral")


def test_substitution_respects_allergy_from_user_and_input():
    r = ok("ingredient_substitution", {"ingredient": "mayonesa", "allergies": ["Lácteos"]})
    assert "yogur griego natural" in r["excluded_by_restrictions"]
    assert all("Lácteos" not in s["contains_allergens"] for s in r["substitutions"])
    # Las alergias guardadas del usuario se aplican aunque el modelo no las pase.
    r2 = ok("ingredient_substitution", {"ingredient": "leche"}, tool_ctx(allergies=("Soya", "Frutos secos")))
    names = [s["substitute"] for s in r2["substitutions"]]
    assert not any("soya" in n or "almendra" in n for n in names)
    assert any("etiquetas" in w for w in r2["warnings"])


def test_substitution_dietary_restriction_vegan():
    r = ok("ingredient_substitution", {"ingredient": "crema", "dietary_restrictions": ["vegano"]})
    assert r["substitutions"] and all("coco" in s["substitute"] or "anacardo" in s["substitute"] for s in r["substitutions"])


def test_substitution_unknown_ingredient_is_flagged():
    r = ok("ingredient_substitution", {"ingredient": "huitlacoche"})
    assert not r["found"] and r["substitutions"] == []
    assert any("conocimiento culinario general" in w for w in r["warnings"])


def test_substitution_warns_when_ingredient_not_in_recipe():
    r = ok("ingredient_substitution", {"ingredient": "cerveza"})
    assert any("no aparece en los ingredientes" in w for w in r["warnings"])


# --------------------------------------------------------- seguridad alimentaria


def test_food_safety_chicken():
    r = ok("food_safety", {"food": "pechuga de pollo", "cooking_method": "horno"})
    assert r["safe_temperature"] == {"celsius": 74, "fahrenheit": 165, "rest_minutes": None}
    assert "más gruesa" in r["measurement_guidance"] and r["source"].startswith("USDA")


def test_food_safety_ground_meat_and_rest_time():
    assert ok("food_safety", {"food": "carne de res", "preparation_method": "molida"})["safe_temperature"]["celsius"] == 71
    steak = ok("food_safety", {"food": "bistec de res"})["safe_temperature"]
    assert steak == {"celsius": 63, "fahrenheit": 145, "rest_minutes": 3}


def test_food_safety_warns_on_unsafe_target_temperature():
    r = ok("food_safety", {"food": "pollo", "target_temperature": 140, "target_temperature_unit": "F"})
    assert any("por debajo" in w for w in r["warnings"])


def test_food_safety_unknown_food_gives_only_general_rules():
    r = ok("food_safety", {"food": "kombucha"})
    assert not r["found"] and r["safe_temperature"] is None
    assert "2 horas" in r["storage_guidance"] and any("no inventes" in w for w in r["warnings"])


def test_food_safety_ambiguous_ingredient_uses_context():
    # "filete" a secas es un corte de carne; "filete de pescado" es pescado.
    assert ok("food_safety", {"food": "filete"})["food_category"].startswith("cortes enteros")
    assert ok("food_safety", {"food": "filete de pescado"})["food_category"] == "pescado"


# --------------------------------------------------------------- paso / búsqueda / despensa


def test_step_context_current_step():
    r = ok("recipe_step_context", {"step_number": 2})
    assert r["total_steps"] == 3 and r["time"] == ["30 minutos"]
    assert "1 1/2 tazas de leche" in r["ingredients"] and "2-3 dientes de ajo" in r["ingredients"]
    assert r["previous_step"].startswith("Precalienta") and r["next_step"].startswith("Hornea")
    assert ok("recipe_step_context", {"step_number": 1})["temperature"] == ["200 °C"]


def test_step_context_errors():
    assert error_code("recipe_step_context", {"step_number": 9}) == "step_out_of_range"
    assert error_code("recipe_step_context", {"step_number": 1}, tool_ctx(current=3)) == "no_steps"
    assert error_code("recipe_step_context", {"step_number": 0}) == "invalid_input"


def test_recipe_search_filters_time_and_restrictions():
    ctx = tool_ctx(current=1)
    r = ok("recipe_search", {"query": "sopa", "max_time": 60, "dietary_restrictions": ["vegano"]}, ctx)
    assert [x["recipe_id"] for x in r["results"]] == [5]  # la abierta (1) se excluye; las de huevo/leche no son veganas
    assert ctx.recipes.searches[-1]["max_minutes"] == 60
    assert error_code("recipe_search", {}) == "empty_query"


def test_pantry_check():
    r = ok("pantry_check", {"available_ingredients": ["pollo", "huevos", "leche", "ajo"]})
    assert r["missing"] == ["½ cucharadita de levadura seca"]
    assert r["missing_optional"] == ["1 guindilla (opcional)"]
    assert "1 cucharadita de sal" in r["basics_assumed"]
    assert not r["can_make"]


# ------------------------------------------------------------------ registro


class _In(ToolInput):
    x: int


class _Out(ToolOutput):
    y: int


def _registry_with(handler):
    reg = ToolRegistry()
    reg.register(Tool("t", "prueba", _In, _Out, handler, "…"))
    return reg


def test_tool_crash_is_controlled_and_does_not_leak():
    def boom(_inp, _ctx):
        raise RuntimeError("secreto interno /etc/passwd")

    out, record = _registry_with(boom).execute("t", {"x": 1}, tool_ctx())
    assert out == {"ok": False, "error": {"code": "internal_error", "message": "La herramienta falló; no inventes su resultado."}}
    assert not record.ok and record.error_code == "internal_error"


def test_tool_invalid_output_is_rejected():
    out, _ = _registry_with(lambda _i, _c: {"y": "no es número"}).execute("t", {"x": 1}, tool_ctx())
    assert out["error"]["code"] == "invalid_output"


def test_unknown_tool_and_extra_args():
    reg = _registry_with(lambda i, _c: _Out(y=i.x))
    assert reg.execute("nope", {}, tool_ctx())[0]["error"]["code"] == "unknown_tool"
    assert reg.execute("t", {"x": 1, "hack": True}, tool_ctx())[0]["error"]["code"] == "invalid_input"
    assert reg.execute("t", {"x": 2}, tool_ctx())[0] == {"ok": True, "result": {"y": 2}}


def test_declarations_have_name_description_and_json_schema():
    decls = REGISTRY.declarations()
    assert {d["name"] for d in decls} == {
        "calculate_recipe_scaling", "convert_cooking_units", "ingredient_substitution", "food_safety",
        "recipe_step_context", "recipe_search", "pantry_check",
    }
    for d in decls:
        assert d["description"] and d["parameters"]["type"] == "object"
        assert d["parameters"].get("additionalProperties") is False
