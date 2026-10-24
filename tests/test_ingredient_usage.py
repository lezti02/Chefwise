"""'Con lo que tengo': uso de ingredientes, orden por menos extras y paginado."""

from __future__ import annotations

from src.ingredient_match import query_terms, usage


def _usage(user: list[str], lines: list[str]):
    return usage(query_terms(user), lines)


def test_matches_ignoring_accents_case_and_plurals():
    u = _usage(["Jitomate", "cebollas", "limón"], ["3 jitomates", "1/2 Cebolla", "el jugo de 2 limones", "sal"])
    assert u.matched == ["Jitomate", "cebollas", "limón"]
    assert u.extras == 1  # solo la sal


def test_multiword_ingredient_needs_all_its_words_in_one_line():
    assert _usage(["pechuga de pollo"], ["2 pechugas de pollo deshuesadas"]).matched == ["pechuga de pollo"]
    assert _usage(["pechuga de pollo"], ["1 pechuga de pavo", "caldo de pollo"]).matched == []


def test_does_not_match_partial_words():
    assert _usage(["pan"], ["1 panela", "2 panes"]).matched == ["pan"]  # "panes" sí, "panela" no
    assert _usage(["pan"], ["1 panela"]).matched == []


def test_extras_count_lines_unrelated_to_what_the_user_has():
    u = _usage(["arroz"], ["1 taza de arroz", "2 tazas de agua", "sal", "aceite"])
    assert u.matched == ["arroz"]
    assert u.extras == 3


def test_blank_and_duplicate_ingredients_are_ignored():
    assert [raw for raw, _ in query_terms(["pollo", " ", "Pollo", "pollos", "arroz"])] == ["pollo", "arroz"]


def test_api_reports_usage_and_extras_per_recipe(client):
    body = client.post(
        "/recommendations/by-ingredients", json={"ingredients": ["pollo", "arroz", "jitomate"], "top_n": 5}
    ).json()
    meta = body["meta"]
    assert meta["ingredients_total"] == 3
    assert 0 <= meta["best_match_count"] <= 3
    for item in body["recommendations"]:
        assert set(item["matched_ingredients"]) <= {"pollo", "arroz", "jitomate"}
        assert item["extra_ingredients"] >= 0
        assert item["extra_ingredients"] <= len(item["ingredients"])


def test_fewest_extras_puts_best_coverage_first_then_fewest_extras(client):
    body = client.post(
        "/recommendations/by-ingredients",
        json={"ingredients": ["pollo", "arroz", "jitomate"], "top_n": 30, "fewest_extras": True},
    ).json()
    items = body["recommendations"]
    keys = [(-len(i["matched_ingredients"]), i["extra_ingredients"]) for i in items]
    assert keys == sorted(keys)
    assert all(i["matched_ingredients"] for i in items)
    assert len(items[0]["matched_ingredients"]) == body["meta"]["best_match_count"]


def test_without_fewest_extras_order_is_by_similarity_only(client):
    items = client.post(
        "/recommendations/by-ingredients", json={"ingredients": ["pollo", "arroz"], "top_n": 20}
    ).json()["recommendations"]
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)


def test_offset_pages_do_not_overlap_and_continue_the_same_order(client):
    def page(offset: int, top_n: int = 5):
        return client.post(
            "/recommendations/by-ingredients",
            json={"ingredients": ["pollo", "arroz"], "top_n": top_n, "offset": offset, "fewest_extras": True},
        ).json()

    first, second = page(0), page(5)
    ids_first = [i["recipe_id"] for i in first["recommendations"]]
    ids_second = [i["recipe_id"] for i in second["recommendations"]]
    assert not set(ids_first) & set(ids_second)
    assert first["meta"]["has_more"] is True
    assert [i["recipe_id"] for i in page(0, top_n=10)["recommendations"]] == ids_first + ids_second


def test_has_more_is_false_when_results_run_out(client):
    body = client.post(
        "/recommendations/by-ingredients", json={"ingredients": ["pollo"], "top_n": 5, "offset": 600}
    ).json()
    assert body["recommendations"] == []
    assert body["meta"]["has_more"] is False


def test_search_offset_and_total_matches(client):
    first = client.get("/recipes/search", params={"q": "pollo", "top_n": 5}).json()
    second = client.get("/recipes/search", params={"q": "pollo", "top_n": 5, "offset": 5}).json()
    assert first["meta"]["candidates"] == second["meta"]["candidates"] > 10
    assert first["meta"]["has_more"] is True
    assert not {i["recipe_id"] for i in first["recommendations"]} & {i["recipe_id"] for i in second["recommendations"]}


def test_search_last_page_has_no_more(client):
    total = client.get("/recipes/search", params={"q": "pollo", "top_n": 5}).json()["meta"]["candidates"]
    last = client.get("/recipes/search", params={"q": "pollo", "top_n": 5, "offset": total - 2}).json()
    assert len(last["recommendations"]) == 2
    assert last["meta"]["has_more"] is False


def test_by_ingredients_with_only_stopwords_is_a_422(client):
    assert client.post("/recommendations/by-ingredients", json={"ingredients": ["de la"]}).status_code == 422
