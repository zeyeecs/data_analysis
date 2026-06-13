from __future__ import annotations

import pytest

from src.product_format import (
    extract_year,
    format_condition_grade,
    format_fr_record,
    format_import_record,
    format_v_record,
    normalize_brand,
    refine_model_display,
    split_fr_model,
    split_model_other,
    split_v_product_name,
    _fuzzy_equal,
    _strip_color_suffix,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Louis Vuitton", "louis vuitton"),
        ("['Louis Vuitton']", "louis vuitton"),
        ("['Hermes']", "hermes"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_brand(raw: str | None, expected: str | None) -> None:
    assert normalize_brand(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Excellent", "99新/Excellent"),
        ("Shows Wear", "90新/Shows Wear"),
        ("Giftable", "全新/Giftable"),
        ("bc-filter-Great", "98新/Great"),
        ("['Excellent']", "99新/Excellent"),
        ("99新/Excellent", "99新/Excellent"),
        ("Very good condition", "97新/Very good condition"),
        (None, None),
    ],
)
def test_format_condition_grade(raw: str | None, expected: str | None) -> None:
    assert format_condition_grade(raw) == expected


@pytest.mark.parametrize(
    ("model", "color", "material", "clean_model"),
    [
        ("Epi Alma BB Black", "Black", "Epi", "Alma BB"),
        ("Monogram Speedy Bandouliere 25", "Brown", "Monogram", "Speedy Bandouliere 25"),
        (
            "Ophidia Shoulder Bag GG Coated Canvas Mini",
            "Blue",
            "GG Coated Canvas",
            "Ophidia Mini",
        ),
        (
            "Kelly Quartz Watch Plated Metal and Leather 20",
            "Brown",
            "Plated Metal and Leather",
            "Kelly Quartz Watch 20",
        ),
        ("Zip Around Wallet Quilted Patent Long", "Purple", "Quilted Patent", "Zip Around Wallet Long"),
        ("Neonoe MM Black", "Brown/Multicolor", None, "Neonoe MM"),
        ("Graceful MM Rose Ballerine", "Blue/White", None, "Graceful MM"),
        ("Pochette Felicie Rose Ballerine", "Pink", None, "Pochette Felicie"),
        ("Emilie Wallet Black Dune", "Beige/Black", None, "Emilie Wallet"),
        ("Graceful MM Pivoine", "Brown/Pink", None, "Graceful MM"),
        ("Delightful PM Pivoine", "Brown", None, "Delightful PM"),
        ("Neo Neverfull MM Pivoine", "Brown/Pink", None, "Neo Neverfull MM"),
        ("Birkin with Hardware 35", None, None, "Birkin 35"),
        ("Taurillon Birkin 35", None, "Taurillon", "Birkin 35"),
        ("Hermes Taurillon Birkin with Hardware 35", None, "Taurillon", "Birkin 35"),
    ],
)
def test_split_fr_model(
    model: str,
    color: str | None,
    material: str | None,
    clean_model: str,
) -> None:
    assert split_fr_model(model, color)[:2] == (material, clean_model)


def test_split_fr_model_strips_brand_prefix() -> None:
    assert split_fr_model("Hermes Birkin with Hardware 35", None, brand="Hermes")[:2] == (
        None,
        "Birkin 35",
    )


@pytest.mark.parametrize(
    ("input_text", "material", "expected"),
    [
        ("Twist Shoulder Bag MM", "Shearling", "Twist MM"),
        ("Birkin 35", None, "Birkin 35"),
        ("Birkin with Hardware 35", None, "Birkin 35"),
        ("Taurillon Birkin 35", "Taurillon", "Birkin 35"),
        ("Kelly28", None, "Kelly 28"),
        ("Kelly Sellier 28", None, "Kelly Sellier 28"),
        ("Kelly Retourne 25", None, "Kelly Retourne 25"),
        ("Birkin Sellier 30", None, "Birkin Sellier 30"),
        ("Speedy Bandouliere 25", "Monogram", "Speedy Bandouliere 25"),
    ],
)
def test_refine_model_display(input_text: str, material: str | None, expected: str) -> None:
    assert refine_model_display(input_text, material=material) == expected


@pytest.mark.parametrize(
    ("input_text", "expected_model", "expected_other"),
    [
        ("Kelly Sellier 28", "Kelly 28", "sellier"),
        ("Kelly Retourne 25", "Kelly 25", "retourne"),
        ("Birkin Sellier 30", "Birkin 30", "sellier"),
        ("Elsa Sellier", "Elsa Sellier", None),
        ("Kelly 28", "Kelly 28", None),
        ("Cargo Picotin Lock Bag PM", "Picotin Lock Bag PM", "cargo"),
        ("Touch Lindy Bag Swift Mini", "Lindy Bag Swift Mini", "touch"),
        ("So Black Boy Flap Bag Medium", "Boy Flap Bag Medium", "so black"),
        ("Roulis Bag Barenia Faubourg 18", "Roulis Bag Barenia 18", "faubourg"),
    ],
)
def test_split_model_other(
    input_text: str,
    expected_model: str,
    expected_other: str | None,
) -> None:
    model, other = split_model_other(input_text)
    assert model == expected_model
    assert other == expected_other


@pytest.mark.parametrize(
    ("model", "other", "expected_model", "expected_other"),
    [
        ("marmont", "gg", "gg marmont", None),
        ("speedy", "bandouliere", "speedy bandouliere", None),
        ("kelly 28", "sellier", "kelly 28", "sellier"),
        ("gg marmont", "gg", "gg marmont", None),
        ("cc", "top", "cc top handle", None),
        ("spike", "rockstud", "rockstud spike", None),
    ],
)
def test_sanitize_model_other(
    model: str,
    other: str | None,
    expected_model: str,
    expected_other: str | None,
) -> None:
    from src.product_format import _sanitize_model_other

    got_model, got_other = _sanitize_model_other(model, other)
    assert got_model == expected_model
    assert got_other == expected_other


def test_filter_valid_other_drops_gg() -> None:
    from src.product_format import _filter_valid_other

    assert _filter_valid_other("gg") is None
    assert _filter_valid_other("sellier") == "sellier"
    assert _filter_valid_other("sellier/gg") == "sellier"
    assert _filter_valid_other("shadow") is None
    assert _filter_valid_other("touch", model="baguette") is None
    assert _filter_valid_other("touch", model="birkin 25") == "touch"
    assert _filter_valid_other("touch", model="lindy mini") == "touch"
    assert _filter_valid_other("cargo", model="picotin lock pm") == "cargo"
    assert _filter_valid_other("cargo", model="jonathan field") is None
    assert _filter_valid_other("faubourg", model="kelly 28") == "faubourg"
    assert _filter_valid_other("faubourg", model="faubourg loafers") is None
    assert _filter_valid_other("so black") == "so black"


def test_sanitize_rejoins_cargo_ramones() -> None:
    from src.product_format import _sanitize_model_other

    model, other = _sanitize_model_other("drkshdw ramones", "cargo")
    assert model == "cargo drkshdw ramones"
    assert other is None


def test_apply_model_other_so_black_from_source() -> None:
    from src.product_format import _apply_model_other

    record = {"model": "boy flap medium"}
    _apply_model_other(
        record,
        model_key="model",
        source_text="So Black Boy Flap Bag Medium",
    )
    assert record["model"] == "boy flap medium"
    assert record["other"] == "so black"


def test_apply_model_other_rejoins_moncler_cargo() -> None:
    from src.product_format import _apply_model_other

    record = {"model": "jonathan field"}
    _apply_model_other(
        record,
        model_key="model",
        llm_other="cargo",
        source_text="Men's Moncler Jonathan Field Cargo Jacket",
    )
    assert record["model"] == "jonathan field cargo"
    assert record.get("other") is None


def test_format_v_record_rejoins_gg_marmont(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.model_semantics import SemanticParseResult

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(),
            material="leather",
            model="marmont",
            color=None,
            other="gg",
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    record = {
        "brand": "Gucci",
        "product_name": "GG Marmont leather handbag",
        "material": "Leather",
        "condition": None,
        "color": None,
    }
    format_v_record(record)
    assert record["product_name"] == "gg marmont"
    assert record.get("other") is None


def test_format_v_record_rejoins_speedy_bandouliere(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.model_semantics import SemanticParseResult

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(),
            material="leather",
            model="speedy",
            color=None,
            other="bandouliere",
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    record = {
        "brand": "Louis Vuitton",
        "product_name": "Speedy Bandouliere",
        "material": "Leather",
        "condition": None,
        "color": None,
    }
    format_v_record(record)
    assert record["product_name"] == "speedy bandouliere"
    assert record.get("other") is None


def test_format_fr_record_splits_kelly_sellier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "false")
    record = {
        "brand": "Hermes",
        "model": "Kelly Sellier 28 Togo",
        "condition": None,
        "color": None,
        "material": None,
    }
    format_fr_record(record)
    assert record["model"] == "kelly 28"
    assert record["material"] == "togo"
    assert record["other"] == "sellier"


def test_format_v_record_keeps_elsa_sellier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "false")
    record = {
        "brand": "Lancel",
        "product_name": "Elsa Sellier leather handbag",
        "material": "Leather",
        "condition": None,
        "color": None,
    }
    format_v_record(record)
    assert record["product_name"] == "elsa sellier"
    assert record.get("other") is None


@pytest.mark.parametrize(
    ("name", "material", "expected"),
    [
        ("Snapshot leather crossbody bag", "Leather", "Snapshot"),
        ("Sac 16 leather handbag", "Leather", "Sac 16"),
        ("2.55 crossbody bag", "Cotton", "2.55"),
    ],
)
def test_split_v_product_name(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    material: str | None,
    expected: str,
) -> None:
    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "false")
    assert split_v_product_name(name, material)[0] == expected


def test_split_v_product_name_uses_llm_when_enabled(monkeypatch) -> None:
    from src.model_semantics import SemanticParseResult, TokenClassification

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(TokenClassification(text="Birkin", role="model"),),
            material="Taurillon",
            model="Birkin 35",
            color="Noir",
            other=None,
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    model, llm_color, llm_material, used_llm, llm_other = split_v_product_name(
        "Taurillon Birkin with Hardware 35 Noir",
        "Taurillon",
        brand="Hermes",
    )
    assert model == "Birkin 35"
    assert llm_color == "Noir"
    assert llm_material == "Taurillon"
    assert used_llm is True
    assert llm_other is None


def test_split_fr_model_uses_llm_other(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.model_semantics import SemanticParseResult, TokenClassification

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(
                TokenClassification(text="Kelly", role="model"),
                TokenClassification(text="Sellier", role="modifier"),
                TokenClassification(text="28", role="size"),
            ),
            material="togo",
            model="kelly 28",
            color=None,
            other="sellier",
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    material, model, llm_color, used_llm, llm_other = split_fr_model(
        "Kelly Sellier 28 Togo",
        None,
        brand="hermes",
    )
    assert material == "togo"
    assert model == "kelly 28"
    assert used_llm is True
    assert llm_other == "sellier"


def test_format_fr_record_llm_sets_other(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.model_semantics import SemanticParseResult, TokenClassification

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(),
            material="togo",
            model="kelly 28",
            color=None,
            other="sellier",
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    record = {
        "brand": "Hermes",
        "model": "Kelly Sellier 28 Togo",
        "condition": None,
        "color": None,
        "material": None,
    }
    format_fr_record(record)
    assert record["model"] == "kelly 28"
    assert record["material"] == "togo"
    assert record["other"] == "sellier"


def test_format_v_record_llm_keeps_model_and_material(monkeypatch) -> None:
    from src.model_semantics import SemanticParseResult, TokenClassification

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(TokenClassification(text="Bon", role="model"),),
            material="silk",
            model="Bon",
            color=None,
            other=None,
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    record = {
        "brand": "Jimmy Choo",
        "product_name": "Bon silk crossbody bag",
        "material": "Silk",
        "condition": None,
        "color": None,
    }
    format_v_record(record)
    assert record["product_name"] == "bon"
    assert record["material"] == "silk"
    assert record.get("color") is None


def test_format_v_record_trunk_llm(monkeypatch) -> None:
    from src.model_semantics import SemanticParseResult, TokenClassification

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(),
            material="leather",
            model="Trunk",
            color=None,
            other=None,
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    record = {
        "brand": "Marni",
        "product_name": "Trunk leather crossbody bag",
        "material": "Leather",
        "condition": None,
        "color": None,
    }
    format_v_record(record)
    assert record["product_name"] == "trunk"
    assert record["material"] == "leather"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("框Q", "框Q"),
        ("框R/2014", "框R/2014"),
        ("T/2015", "T/2015"),
        ("Z/2021", "Z/2021"),
        ("Acetate Square Sunglasses 6059", None),
        ("Horsebit 1955 Top Handle Flap Bag", None),
        ("Monogram Speedy Bandouliere 25", None),
        ("Kelly Quartz Watch 20", None),
        ("Birkin 35", None),
        (None, None),
    ],
)
def test_extract_year_only_hermes_stamp(text: str | None, expected: str | None) -> None:
    assert extract_year(text) == expected


def test_fuzzy_condition_typo() -> None:
    assert format_condition_grade("Excelent") == "99新/Excellent"


def test_fuzzy_color_suffix() -> None:
    assert _fuzzy_equal("Blak", "Black")
    assert _strip_color_suffix("Alma BB Blak", "Black") == "Alma BB"


def test_format_import_record_defers_model_split_when_llm_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")
    record = {
        "brand": "Louis Vuitton",
        "model": "Louis Vuitton Speedy Bandouliere 25 Monogram Canvas",
        "color": None,
        "condition": "Excellent",
        "material": None,
        "year": None,
        "other": None,
    }
    format_import_record(record, table_kind="F")
    assert record["brand"] == "louis vuitton"
    assert "Speedy Bandouliere" in record["model"]
    assert record["material"] is None


def test_format_record_from_old_data_fr() -> None:
    from src.product_format import format_record_from_old_data

    record = {
        "brand": "louis vuitton",
        "model": None,
        "condition": "99新/Excellent",
        "color": "brown",
        "material": None,
        "year": None,
        "other": None,
    }
    old_data = {
        "brand": "Louis Vuitton",
        "model": "Epi Alma BB Black",
        "condition": "Excellent",
        "color": "Black",
    }
    format_record_from_old_data(record, old_data, table_kind="F")
    assert record["model"] == "alma bb"
    assert record["material"] == "epi"


def test_format_fr_record() -> None:
    record = {
        "brand": "['Louis Vuitton']",
        "model": "Epi Alma BB Black",
        "condition": "Excellent",
        "color": "['Black']",
        "price": 100,
    }
    format_fr_record(record)
    assert record["brand"] == "louis vuitton"
    assert record["model"] == "alma bb"
    assert record["material"] == "epi"
    assert record["color"] == "black"
    assert record["condition"] == "99新/Excellent"


def test_strip_color_when_column_empty() -> None:
    from src.product_format import strip_color_condition_from_model

    model, color, cond = strip_color_condition_from_model(
        "Neonoe MM Black", color=None, condition=None
    )
    assert model == "Neonoe MM"
    assert color == "black"
    assert cond is None


def test_format_fr_record_merges_extracted_material_with_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.model_semantics import SemanticParseResult

    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "true")

    def fake_parse(text, *, brand=None, color=None, condition=None, use_cache=True, error_out=None):
        return SemanticParseResult(
            tokens=(),
            material=None,
            model="clemence",
            color=None,
            other=None,
        )

    monkeypatch.setattr("src.model_semantics.semantic_parse_model", fake_parse)
    record = {
        "brand": "Louis Vuitton",
        "model": "clemence",
        "condition": "99新/Excellent",
        "color": "brown/red",
        "material": "clemence",
    }
    format_fr_record(record)
    assert record["model"] == "clemence"
    assert record["material"] == "clemence"


def test_format_fr_record_merges_extracted_color_with_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "false")
    record = {
        "brand": "Louis Vuitton",
        "model": "Graceful MM Pivoine",
        "condition": "Excellent",
        "color": "brown/pink",
        "material": None,
    }
    format_fr_record(record)
    assert record["model"] == "graceful mm"
    assert record["color"] == "brown/pink/pivoine"


def test_format_fr_record_merges_rule_extracted_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCT_FORMAT_USE_LLM", "false")
    record = {
        "brand": "Louis Vuitton",
        "model": "Epi Alma BB Black",
        "condition": "Excellent",
        "color": "black",
        "material": "leather",
    }
    format_fr_record(record)
    assert record["model"] == "alma bb"
    assert record["material"] == "leather/epi"


def test_new_wave_keeps_new() -> None:
    assert refine_model_display("New Wave Bumbag Porcelain", color="Blue") == "New Wave Bumbag"


def test_format_v_record() -> None:
    record = {
        "brand": "Chanel",
        "product_name": "2.55 crossbody bag",
        "material": "Cotton",
        "condition": "Never worn",
        "color": None,
    }
    format_v_record(record)
    assert record["product_name"] == "2.55"
    assert record["condition"] == "全新/Never worn"
