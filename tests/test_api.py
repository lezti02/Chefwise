"""Pruebas de la API contra los dos CSV y los artefactos reales."""

from __future__ import annotations


def _tags(value: str) -> set[str]:
    return {tag.strip() for tag in value.split("|") if tag.strip()}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_metadata_matches_model_csv_exactly(client, model_df):
    response = client.get("/metadata")
    assert response.status_code == 200
    body = response.json()
    expected_tags = sorted({tag for value in model_df["tags"].dropna() for tag in _tags(value)})
    expected_countries = sorted(model_df["country"].dropna().unique().tolist())
    assert body == {"tags": expected_tags, "countries": expected_countries}


def test_default_recommendations_use_tfidf_and_return_five(client, csv_df):
    response = client.post("/recommendations", json={})
    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) == 5
    assert body["meta"]["query_text"] == "receta"
    assert body["meta"]["relaxed"] == []
    assert all(item["similarity"] is not None for item in body["recommendations"])
    assert {item["recipe_id"] for item in body["recommendations"]} <= set(csv_df["recipe_id"])


def test_responses_have_no_rating_keys(client, csv_df):
    recommendation = client.post("/recommendations", json={"tags": ["Comida"]}).json()["recommendations"][0]
    detail = client.get(f"/recipes/{int(csv_df.iloc[0]['recipe_id'])}").json()
    assert "rating" not in recommendation and "rating_votes" not in recommendation
    assert "rating" not in detail and "rating_votes" not in detail


def test_recommendations_respect_exact_tag_country_and_structural_filters(client, model_df):
    response = client.post(
        "/recommendations",
        json={
            "tags": ["Comida", "Pollo"],
            "countries": ["México"],
            "difficulty": "facil",
            "max_time": 60,
            "top_n": 20,
        },
    )
    assert response.status_code == 200
    body = response.json()
    by_id = model_df.set_index("recipe_id")
    assert body["meta"]["relaxed"] == []
    for item in body["recommendations"]:
        row = by_id.loc[item["recipe_id"]]
        assert {"Comida", "Pollo"} <= _tags(row["tags"])
        assert row["country"] == "México"
        assert row["difficulty"] == "facil"
        assert row["total_time_min"] <= 60


def test_recommendations_prioritize_all_tags_and_fallback_to_partial(client, model_df):
    by_id = model_df.set_index("recipe_id")

    # Caso 1: Hay 2 recetas con ambos tags (Desayuno y Alcohol) y se piden 5.
    # Las 2 primeras deben cumplir ambos tags; las siguientes 3 deben cumplir al menos uno.
    partial_resp = client.post(
        "/recommendations",
        json={"tags": ["Desayuno", "Alcohol"], "top_n": 5},
    )
    assert partial_resp.status_code == 200
    partial_body = partial_resp.json()
    assert len(partial_body["recommendations"]) == 5
    assert len(partial_body["meta"]["relaxed"]) > 0

    first_two = partial_body["recommendations"][:2]
    for item in first_two:
        row = by_id.loc[item["recipe_id"]]
        assert {"Desayuno", "Alcohol"} <= _tags(row["tags"])

    remaining = partial_body["recommendations"][2:]
    for item in remaining:
        row = by_id.loc[item["recipe_id"]]
        assert bool({"Desayuno", "Alcohol"} & _tags(row["tags"]))

    # Caso 2: Cero recetas cumplen todos los tags (Pavo y Vegana).
    # Debe retornar recetas que cumplan al menos uno y reportarlo en relaxed.
    zero_all_resp = client.post(
        "/recommendations",
        json={"tags": ["Pavo", "Vegana"], "top_n": 5},
    )
    assert zero_all_resp.status_code == 200
    zero_body = zero_all_resp.json()
    assert len(zero_body["recommendations"]) == 5
    assert len(zero_body["meta"]["relaxed"]) > 0
    for item in zero_body["recommendations"]:
        row = by_id.loc[item["recipe_id"]]
        tags_set = _tags(row["tags"])
        assert "Pavo" in tags_set or "Vegana" in tags_set


def test_invalid_exact_tag_and_country_are_rejected(client):
    assert client.post("/recommendations", json={"tags": ["comida"]}).status_code == 422
    assert client.post("/recommendations", json={"countries": ["mexico"]}).status_code == 422


def test_exclusions_are_hard_before_ranking(client):
    first = client.post("/recommendations", json={"tags": ["Comida"], "top_n": 5}).json()
    excluded = [item["recipe_id"] for item in first["recommendations"]]
    second = client.post(
        "/recommendations",
        json={"tags": ["Comida"], "exclude_ids": excluded, "top_n": 5},
    ).json()
    assert not set(excluded) & {item["recipe_id"] for item in second["recommendations"]}


def test_ingredient_recommendations_are_positive_and_exclude_ids(client):
    first = client.post(
        "/recommendations/by-ingredients",
        json={"ingredients": ["pollo", "jitomate"], "top_n": 5},
    ).json()
    assert len(first["recommendations"]) == 5
    assert all(item["similarity"] > 0 for item in first["recommendations"])
    excluded = [item["recipe_id"] for item in first["recommendations"]]
    second = client.post(
        "/recommendations/by-ingredients",
        json={"ingredients": ["pollo", "jitomate"], "exclude_ids": excluded, "top_n": 5},
    ).json()
    assert not set(excluded) & {item["recipe_id"] for item in second["recommendations"]}


def test_catalog_search_and_exact_tag_filter(client, model_df):
    response = client.get("/recipes/search", params={"q": "pollo con arroz", "tag": "Pollo"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) <= 5
    by_id = model_df.set_index("recipe_id")
    assert all("Pollo" in _tags(by_id.loc[item["recipe_id"], "tags"]) for item in body["recommendations"])
    assert client.get("/recipes/search", params={"q": "zzzzterminoinexistentezzzz"}).json()["recommendations"] == []
    assert client.get("/recipes/search", params={"q": "   "}).status_code == 422
    assert client.get("/recipes/search", params={"q": "pollo", "tag": "pollo"}).status_code == 422


def test_search_path_precedes_dynamic_recipe_path(client):
    response = client.get("/recipes/search", params={"q": "tacos"})
    assert response.status_code == 200


def test_get_recipe_joins_display_fields(client, csv_df):
    row = csv_df.iloc[0]
    response = client.get(f"/recipes/{int(row['recipe_id'])}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == row["name"]
    assert body["source_url"] == row["url"]
    assert body["ingredients"][0] == row["ingredients"].split(" | ")[0]


def test_unknown_recipe_and_invalid_requests(client):
    assert client.get("/recipes/99999999").status_code == 404
    assert client.get("/recipes/abc").status_code == 422
    assert client.post("/recommendations", json={"difficulty": "imposible"}).status_code == 422
    assert client.post("/recommendations", json={"top_n": 0}).status_code == 422
    assert client.post("/recommendations", json={"antojos": ["dulce"]}).status_code == 422
    assert client.post("/recommendations/by-ingredients", json={"ingredients": []}).status_code == 422


def test_empty_or_unknown_interactions_do_not_change_cold_start(client):
    cold = client.post("/recommendations", json={"tags": ["Comida"], "top_n": 5}).json()
    empty = client.post(
        "/recommendations",
        json={"tags": ["Comida"], "favorite_ids": [], "viewed_ids": [], "top_n": 5},
    ).json()
    unknown = client.post(
        "/recommendations",
        json={"tags": ["Comida"], "favorite_ids": [99_999_999], "top_n": 5},
    ).json()
    cold_ids = [item["recipe_id"] for item in cold["recommendations"]]
    assert [item["recipe_id"] for item in empty["recommendations"]] == cold_ids
    assert [item["recipe_id"] for item in unknown["recommendations"]] == cold_ids
    assert cold["meta"]["personalized"] is False
    assert empty["meta"]["personalized"] is False
    assert unknown["meta"]["personalized"] is False


def test_favorites_shift_recommendations_toward_similar_recipes(client):
    import numpy as np

    recommender = client.app.state.recommender
    seed_id = int(
        recommender.store.df.loc[recommender.store.df["tags"].str.contains("Postre", na=False), "recipe_id"].iloc[0]
    )
    payload = {"exclude_ids": [seed_id], "top_n": 10}
    cold_ids = [item["recipe_id"] for item in client.post("/recommendations", json=payload).json()["recommendations"]]
    warm = client.post("/recommendations", json={**payload, "favorite_ids": [seed_id]}).json()
    warm_ids = [item["recipe_id"] for item in warm["recommendations"]]
    assert warm["meta"]["personalized"] is True
    assert cold_ids != warm_ids

    space = recommender.embeddings or recommender.artifacts
    seed_pos = recommender.store.id_to_pos[seed_id]
    if recommender.embeddings is not None:
        neighbor = space.similarities_to_row(seed_pos)
    else:
        neighbor = np.asarray(space.matrix.dot(space.matrix[seed_pos].T).todense()).ravel()

    def mean_to_seed(ids: list[int]) -> float:
        return float(np.mean(neighbor[recommender.store.positions_of(ids)]))

    assert mean_to_seed(warm_ids) > mean_to_seed(cold_ids)


def test_ingredient_recommendations_can_use_a_taste_profile(client):
    seed = client.post(
        "/recommendations/by-ingredients", json={"ingredients": ["chocolate"], "top_n": 1}
    ).json()["recommendations"][0]["recipe_id"]
    warm = client.post(
        "/recommendations/by-ingredients",
        json={"ingredients": ["chocolate"], "favorite_ids": [seed], "top_n": 5},
    ).json()
    assert warm["meta"]["personalized"] is True
    assert len(warm["recommendations"]) == 5


def test_cors_allows_the_angular_dev_origin(client):
    response = client.options(
        "/recommendations",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4200"
