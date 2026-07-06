from pathlib import Path

from src.standards.compilation_guardrails import (
    get_compilation_guardrails,
    load_compilation_guardrail_manifest,
    load_compilation_guardrails,
)
from src.standards.gri import GRIAdapter


def test_compilation_guardrails_load_reviewed_non_removed_rows():
    guardrails = load_compilation_guardrails()

    assert len(guardrails) == 64
    assert all(guardrail.target_requirement_ids for guardrail in guardrails)
    assert all("2.2" not in guardrail.compilation_requirement_id or guardrail.missing_item_templates for guardrail in guardrails)


def test_compilation_guardrails_map_to_leaf_requirements_only():
    guardrails = get_compilation_guardrails("GRI 207-4-b-iv")

    assert any(guardrail.compilation_requirement_id == "GRI 207-4-2.2.1" for guardrail in guardrails)
    assert any("requires_reconciliation" in guardrail.facets for guardrail in guardrails)
    assert get_compilation_guardrails("GRI 207-4-2.2") == ()


def test_compilation_guardrails_keep_zero_event_rules_as_guardrails():
    guardrails = get_compilation_guardrails("GRI 416-2-a-i")

    assert any(guardrail.compilation_requirement_id.startswith("GRI 416-2") for guardrail in guardrails)
    assert any("requires_fault_exclusion" in guardrail.facets for guardrail in guardrails)
    assert any("fault" in item.lower() or "无过错" in item for guardrail in guardrails for item in guardrail.guardrail_effects)


def test_compilation_guardrail_manifest_loads_non_removed_rules():
    manifest = load_compilation_guardrail_manifest(Path("data/manifests/compilation_guardrails.json"))

    assert len(manifest.rules) == 64
    assert all(rule.target_requirement_ids for rule in manifest.rules)
    assert all(rule.facets for rule in manifest.rules)
    assert not any(rule.compilation_requirement_id == "GRI 207-4-2.2" for rule in manifest.rules)


def test_compilation_guardrail_manifest_ids_do_not_enter_main_assessment_requirements():
    manifest = load_compilation_guardrail_manifest(Path("data/manifests/compilation_guardrails.json"))
    assessment_ids = {
        requirement.requirement_id
        for requirement in GRIAdapter(Path("data/manifests/gri_requirement_checklist.json")).load_requirements()
    }

    assert len(assessment_ids) == 577
    assert not {rule.compilation_requirement_id for rule in manifest.rules}.intersection(assessment_ids)
