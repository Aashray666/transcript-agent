"""Residual Risk Calculator — runs AFTER the inherent scoring pipeline.

Maps controls from the client RCM to scored risks and computes residual scores.

Three scenarios:
1. DIRECT MATCH: Asset risk maps to a client risk that maps to an RCM risk → pick up D, OE directly
2. CROSS-MAPPED: No direct match but an expert agent finds an applicable control → LLM evaluates
3. NO CONTROL: No control found → residual = inherent, flagged as uncontrolled

Residual formula (from ERM_RCM_Residual_Risk_Guide.docx):
  Composite = Design Adequacy × Operating Effectiveness (1-25)
  20-25 (Strong):            Likelihood -2, Impact -2
  12-19 (Satisfactory):      Likelihood -1, Impact -1
  6-11  (Needs Improvement): Likelihood -1, Impact stays
  1-5   (Unsatisfactory):    No reduction, residual = inherent
"""

import json
import logging
import os

import openpyxl

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("residual")

# Paths
SCORED_DIR = "output_auto_scored_v2"
SCORED_UNIVERSE = os.path.join(SCORED_DIR, "scored_risk_universe.json")
ASSET_UNIVERSE = "data/asset_risk_universe.json"
CLIENT_UNIVERSE = "output_auto/risk_universe.json"
RCM_PATH = "data/VelocityAuto_RCM.xlsx"
OUTPUT_DIR = "output_residual"


# ---------------------------------------------------------------------------
# Step 1: Parse the RCM — extract controls keyed by risk title
# ---------------------------------------------------------------------------

def parse_rcm(rcm_path: str) -> dict[str, dict]:
    """Parse the RCM Excel and return controls keyed by risk title."""
    wb = openpyxl.load_workbook(rcm_path, read_only=True, data_only=True)
    ws = wb["Risk Control Matrix"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    controls = {}
    for row in rows[2:]:  # Skip header rows
        if not row[0]:
            continue
        risk_id = str(row[0]).strip()
        title = str(row[3] or "").strip()
        if not title:
            continue

        controls[risk_id] = {
            "rcm_risk_id": risk_id,
            "rcm_risk_title": title,
            "control_description": str(row[6] or ""),
            "control_type": str(row[7] or ""),
            "control_owner": str(row[11] or ""),
            "inherent_likelihood": row[12],
            "inherent_impact": row[13],
            "inherent_score": row[14],
            "design_adequacy": row[15],
            "operating_effectiveness": row[16],
            "composite_score": row[17],
            "control_rating": str(row[18] or ""),
        }

    logger.info("Parsed RCM: %d controls", len(controls))
    return controls


# ---------------------------------------------------------------------------
# Step 2: Build the mapping chain
# Asset risk → client risk (via _matched_client_risks) → RCM risk (via title similarity)
# ---------------------------------------------------------------------------

def build_control_mapping(
    asset_universe: list[dict],
    rcm_controls: dict[str, dict],
    llm=None,
) -> dict[str, dict]:
    """Map each asset risk to its RCM control using per-risk LLM matching + verification.

    Two-stage approach:
    Stage 1: For each risk, one LLM call picks the best control (or NONE)
    Stage 2: For each match, one LLM call verifies the match is correct
    Rejected matches → residual = inherent
    """
    from pydantic import BaseModel

    class _MatchResult(BaseModel):
        rcm_risk_id: str  # "R-01" or "NONE"
        reason: str

    class _VerifyResult(BaseModel):
        is_valid: bool
        reason: str

    if llm is None:
        from riskmapper.llm_wrapper import LLMWrapper
        llm = LLMWrapper()

    # Build control list once (used in every call)
    ctrl_list = "\n".join(
        f"  {rid}: {ctrl['rcm_risk_title']}"
        for rid, ctrl in rcm_controls.items()
    )

    mapping = {}

    for asset in asset_universe:
        asset_id = asset["risk_id"]
        asset_name = asset.get("_asset_risk_name", asset.get("client_description", ""))

        # --- Stage 1: Match ---
        match_prompt = f"""You are an ERM control mapping expert.

Which ONE control from the list below DIRECTLY addresses this risk?
A direct match means the control was designed to mitigate this exact type of risk.

RISK: {asset_name}

CONTROLS:
{ctrl_list}

If one control directly addresses this risk, return its ID (e.g., "R-01").
If NO control directly addresses this risk, return "NONE".
Prefer "NONE" over a weak or tangential match."""

        try:
            match = llm.call(
                prompt=match_prompt,
                response_model=_MatchResult,
                temperature=0.0,
                step_name=f"match_{asset_id}",
            )

            if match.rcm_risk_id == "NONE" or match.rcm_risk_id not in rcm_controls:
                mapping[asset_id] = {
                    "match_type": "none",
                    "control": None,
                    "match_reason": f"No direct match: {match.reason}",
                }
                logger.info("  %s: no match — %s", asset_id, match.reason[:60])
                continue

            ctrl = rcm_controls[match.rcm_risk_id]

            # --- Stage 2: Verify ---
            verify_prompt = f"""You are verifying a control-to-risk mapping.

RISK: {asset_name}
MATCHED CONTROL: {ctrl['rcm_risk_title']}
CONTROL DESCRIPTION: {ctrl['control_description'][:200]}

Question: Does this control DIRECTLY reduce the likelihood or impact of "{asset_name}"?

Answer YES only if the control was designed for this type of risk.
Answer NO if the control is for a different risk domain (e.g., financial controls for a product safety risk, or competition controls for a credit risk)."""

            verify = llm.call(
                prompt=verify_prompt,
                response_model=_VerifyResult,
                temperature=0.0,
                step_name=f"verify_{asset_id}",
            )

            if verify.is_valid:
                mapping[asset_id] = {
                    "match_type": "direct",
                    "control": ctrl,
                    "match_reason": f"Matched to {match.rcm_risk_id} and verified: {match.reason}",
                }
                logger.info("  %s → %s ✓ verified", asset_id, match.rcm_risk_id)
            else:
                mapping[asset_id] = {
                    "match_type": "none",
                    "control": None,
                    "match_reason": f"Matched to {match.rcm_risk_id} but REJECTED by verifier: {verify.reason}",
                }
                logger.info("  %s → %s ✗ rejected: %s", asset_id, match.rcm_risk_id, verify.reason[:60])

        except Exception as exc:
            logger.warning("  %s: matching failed: %s", asset_id, exc)
            mapping[asset_id] = {
                "match_type": "none",
                "control": None,
                "match_reason": f"Matching failed: {exc}",
            }

    direct = sum(1 for v in mapping.values() if v["match_type"] == "direct")
    none_ = sum(1 for v in mapping.values() if v["match_type"] == "none")
    logger.info("Control mapping: %d direct, %d unmatched (after verification)", direct, none_)
    return mapping


def _keyword_fallback_mapping(asset_universe, rcm_controls):
    """Fallback keyword-based matching if LLM fails."""
    mapping = {}
    for asset in asset_universe:
        asset_id = asset["risk_id"]
        asset_name = asset.get("_asset_risk_name", asset.get("client_description", ""))
        matched_clients = asset.get("_matched_client_risks", [])
        best_match = _find_best_rcm_match(asset_name, matched_clients, rcm_controls)
        if best_match:
            mapping[asset_id] = {"match_type": "direct", "control": best_match,
                                  "match_reason": f"Keyword fallback: '{asset_name[:50]}' → '{best_match['rcm_risk_title'][:50]}'"}
        else:
            mapping[asset_id] = {"match_type": "none", "control": None, "match_reason": "No match (keyword fallback)"}
    return mapping


def _find_best_rcm_match(
    asset_name: str,
    matched_clients: list[dict],
    rcm_controls: dict[str, dict],
) -> dict | None:
    """Find the best RCM control for an asset risk.

    Strategy: check if any RCM risk title shares significant keywords
    with the asset risk name or its matched client risk descriptions.
    """
    # Collect all relevant terms from the asset risk and its client matches
    search_terms = set()
    for word in asset_name.lower().split():
        if len(word) > 3 and word not in {"with", "that", "this", "from", "into", "have", "been", "their", "they", "will", "also", "more", "than", "each", "such"}:
            search_terms.add(word)

    for client in matched_clients:
        for word in client.get("description", "").lower().split():
            if len(word) > 3 and word not in {"with", "that", "this", "from", "into", "have", "been", "their", "risk"}:
                search_terms.add(word)

    if not search_terms:
        return None

    # Score each RCM control by keyword overlap
    best_score = 0
    best_control = None

    for rcm_id, ctrl in rcm_controls.items():
        title_words = set(ctrl["rcm_risk_title"].lower().split())
        desc_words = set(ctrl["control_description"].lower()[:200].split())
        all_words = title_words | desc_words

        overlap = len(search_terms & all_words)
        if overlap > best_score and overlap >= 2:  # Need at least 2 keyword matches
            best_score = overlap
            best_control = ctrl

    return best_control


# ---------------------------------------------------------------------------
# Step 3: Cross-mapping agent — for unmatched risks, ask LLM if any control applies
# ---------------------------------------------------------------------------

def cross_map_controls(
    unmatched_risks: list[dict],
    rcm_controls: dict[str, dict],
    llm,
) -> dict[str, dict]:
    """For risks with no direct match, ask the LLM if any RCM control applies."""
    from pydantic import BaseModel
    from typing import Literal

    class _LLMControlMatch(BaseModel):
        applicable_rcm_risk_id: str  # "R-01", "R-02", ... or "NONE"
        reasoning: str
        adjusted_design: int  # 1-5, may be lower than original if partial fit
        adjusted_effectiveness: int  # 1-5

    # Build a summary of all RCM controls for the prompt
    ctrl_summary = "\n".join(
        f"  {rid}: {ctrl['rcm_risk_title'][:60]} — {ctrl['control_description'][:100]}"
        for rid, ctrl in rcm_controls.items()
    )

    results = {}

    for risk in unmatched_risks:
        risk_id = risk["risk_id"]
        risk_name = risk.get("_asset_risk_name", risk.get("client_description", ""))

        prompt = f"""You are an ERM control mapping expert.

TASK: Determine if any of the following controls from the client's Risk Control Matrix
are DIRECTLY applicable to this risk. A control is applicable ONLY if it would meaningfully
reduce the likelihood or impact of this risk.

RISK TO MAP: {risk_name}

AVAILABLE CONTROLS IN THE RCM:
{ctrl_summary}

STRICT RULES:
- The control must DIRECTLY address this risk, not just be tangentially related
- The control and the risk must be in the SAME risk domain (e.g., financial controls for financial risks, operational controls for operational risks)
- If the connection requires more than one logical step to explain, it's NOT a direct match
- When in doubt, return "NONE" — it's better to leave a risk uncontrolled than to force a weak match

If a control applies:
- Set applicable_rcm_risk_id to the RCM risk ID (e.g., "R-01")
- Explain the DIRECT connection in reasoning
- Set adjusted_design (1-5): how well designed is this control FOR THIS SPECIFIC RISK?
- Set adjusted_effectiveness (1-5): how effective is it FOR THIS SPECIFIC RISK?

If NO control DIRECTLY applies:
- Set applicable_rcm_risk_id to "NONE"
- Set adjusted_design and adjusted_effectiveness to 0"""

        try:
            result = llm.call(
                prompt=prompt,
                response_model=_LLMControlMatch,
                temperature=0.0,
                step_name=f"cross_map_{risk_id}",
            )

            if result.applicable_rcm_risk_id != "NONE" and result.applicable_rcm_risk_id in rcm_controls:
                adj_d = max(1, min(5, result.adjusted_design))
                adj_oe = max(1, min(5, result.adjusted_effectiveness))
                adj_composite = adj_d * adj_oe

                # Reject weak cross-maps — if adjusted composite < 6, it's not a meaningful control
                if adj_composite < 6:
                    results[risk_id] = {
                        "match_type": "none",
                        "control": None,
                        "match_reason": f"Expert agent found {result.applicable_rcm_risk_id} but adjusted composite={adj_composite} < 6 (too weak). Rejected. Reason: {result.reasoning}",
                    }
                    logger.info("  %s: cross-match rejected (composite=%d < 6) — %s",
                                risk_id, adj_composite, result.reasoning[:80])
                else:
                    ctrl = rcm_controls[result.applicable_rcm_risk_id]
                    results[risk_id] = {
                        "match_type": "cross_mapped",
                        "control": {
                            **ctrl,
                            "design_adequacy": adj_d,
                            "operating_effectiveness": adj_oe,
                            "composite_score": adj_composite,
                        },
                        "match_reason": f"Cross-mapped by expert agent: {result.reasoning}",
                        "original_rcm_risk_id": result.applicable_rcm_risk_id,
                    }
                    logger.info("  %s: cross-mapped to %s (D=%d, OE=%d, C=%d) — %s",
                                risk_id, result.applicable_rcm_risk_id,
                                adj_d, adj_oe, adj_composite, result.reasoning[:80])
            else:
                results[risk_id] = {
                    "match_type": "none",
                    "control": None,
                    "match_reason": f"Expert agent: no applicable control — {result.reasoning}",
                }
                logger.info("  %s: no cross-match — %s", risk_id, result.reasoning[:80])

        except Exception as exc:
            logger.warning("  %s: cross-mapping failed: %s", risk_id, exc)
            results[risk_id] = {
                "match_type": "none",
                "control": None,
                "match_reason": f"Cross-mapping failed: {exc}",
            }

    return results


# ---------------------------------------------------------------------------
# Step 4: Compute residual scores
# ---------------------------------------------------------------------------

def compute_residual(inherent_l: int, inherent_i: int, composite: int | None) -> dict:
    """Apply the residual formula from the ERM guide."""
    if composite is None or composite <= 5:
        # Unsatisfactory or no control
        return {
            "residual_likelihood": inherent_l,
            "residual_impact": inherent_i,
            "residual_score": inherent_l * inherent_i,
            "reduction_applied": "None — no effective control",
            "control_rating": "Unsatisfactory" if composite else "No Control",
        }

    if composite >= 20:
        rl = max(1, inherent_l - 2)
        ri = max(1, inherent_i - 2)
        reduction = "Strong: L-2, I-2"
        rating = "Strong"
    elif composite >= 12:
        rl = max(1, inherent_l - 1)
        ri = max(1, inherent_i - 1)
        reduction = "Satisfactory: L-1, I-1"
        rating = "Satisfactory"
    else:  # 6-11
        rl = max(1, inherent_l - 1)
        ri = inherent_i
        reduction = "Needs Improvement: L-1, I unchanged"
        rating = "Needs Improvement"

    return {
        "residual_likelihood": rl,
        "residual_impact": ri,
        "residual_score": rl * ri,
        "reduction_applied": reduction,
        "control_rating": rating,
    }


def _risk_level(score: int) -> str:
    if score <= 4: return "Low"
    if score <= 9: return "Medium"
    if score <= 15: return "High"
    return "Critical"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load scored risks
    if not os.path.isfile(SCORED_UNIVERSE):
        print(f"Error: {SCORED_UNIVERSE} not found. Run the scoring pipeline first.")
        return

    with open(SCORED_UNIVERSE) as f:
        scored_risks = json.load(f)
    logger.info("Loaded %d scored risks", len(scored_risks))

    # Load asset universe (has the _matched_client_risks metadata)
    with open(ASSET_UNIVERSE) as f:
        asset_risks = json.load(f)
    asset_lookup = {r["risk_id"]: r for r in asset_risks}

    # Parse RCM
    rcm_controls = parse_rcm(RCM_PATH)

    # Initialize LLM (used for both direct mapping and cross-mapping)
    from riskmapper.llm_wrapper import LLMWrapper
    llm = LLMWrapper()

    # Build direct control mapping (LLM-based semantic matching)
    control_mapping = build_control_mapping(asset_risks, rcm_controls, llm)

    # Find unmatched risks for cross-mapping
    unmatched = [
        asset_lookup[rid]
        for rid, m in control_mapping.items()
        if m["match_type"] == "none" and rid in asset_lookup
    ]

    if unmatched:
        logger.info("Cross-mapping %d unmatched risks via expert agent...", len(unmatched))
        cross_results = cross_map_controls(unmatched, rcm_controls, llm)
        # Merge cross-mapping results
        for rid, result in cross_results.items():
            if result["match_type"] == "cross_mapped":
                control_mapping[rid] = result

    # Compute residual scores
    residual_risks = []

    for scored in scored_risks:
        rid = scored["risk_id"]
        inh_l = scored["likelihood_assessment"]["score"]
        inh_i = scored["impact_assessment"]["score"]
        inh_score = scored["inherent_risk_score"]

        mapping = control_mapping.get(rid, {"match_type": "none", "control": None, "match_reason": "Risk not in asset universe"})
        ctrl = mapping.get("control")
        composite = ctrl["composite_score"] if ctrl else None

        residual = compute_residual(inh_l, inh_i, composite)

        residual_risk = {
            "risk_id": rid,
            "client_description": scored["client_description"],
            # Inherent
            "inherent_likelihood": inh_l,
            "inherent_impact": inh_i,
            "inherent_score": inh_score,
            "inherent_rating": scored["risk_rating"],
            # Control
            "control_match_type": mapping["match_type"],
            "control_match_reason": mapping["match_reason"],
            "control_description": ctrl["control_description"][:300] if ctrl else "No control mapped",
            "control_owner": ctrl["control_owner"] if ctrl else "N/A",
            "design_adequacy": ctrl["design_adequacy"] if ctrl else None,
            "operating_effectiveness": ctrl["operating_effectiveness"] if ctrl else None,
            "composite_control_score": composite,
            "control_rating": residual["control_rating"],
            # Residual
            "residual_likelihood": residual["residual_likelihood"],
            "residual_impact": residual["residual_impact"],
            "residual_score": residual["residual_score"],
            "residual_rating": _risk_level(residual["residual_score"]),
            "reduction_applied": residual["reduction_applied"],
            # Audit
            "audit_trail": {
                "inherent_source": "scoring_pipeline",
                "control_source": f"RCM ({ctrl['rcm_risk_id']})" if ctrl else "none",
                "match_method": mapping["match_type"],
                "match_detail": mapping["match_reason"],
                "formula": f"Composite={composite} → {residual['reduction_applied']}" if composite else "No control → residual = inherent",
            },
        }
        residual_risks.append(residual_risk)

    # Sort by residual score descending
    residual_risks.sort(key=lambda r: r["residual_score"], reverse=True)

    # Write output
    output_path = os.path.join(OUTPUT_DIR, "residual_risk_universe.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(residual_risks, f, indent=2, ensure_ascii=False)
    logger.info("Written: %s", output_path)

    # Print summary
    print(f"\n{'='*80}")
    print(f"RESIDUAL RISK SCORING COMPLETE — {len(residual_risks)} risks")
    print(f"{'='*80}")
    print(f"{'ID':<12} {'Description':<40} {'Inh':>4} {'Ctrl':>5} {'Res':>4} {'Inh Lvl':<9} {'Res Lvl':<9} {'Match':<12}")
    print("-" * 100)

    for r in residual_risks:
        rid = r["risk_id"]
        desc = r["client_description"][:38]
        inh = r["inherent_score"]
        ctrl = r["composite_control_score"] or 0
        res = r["residual_score"]
        inh_lvl = r["inherent_rating"]
        res_lvl = r["residual_rating"]
        match = r["control_match_type"]
        print(f"{rid:<12} {desc:<40} {inh:>4} {ctrl:>5} {res:>4} {inh_lvl:<9} {res_lvl:<9} {match:<12}")

    # Summary stats
    inh_crit = sum(1 for r in residual_risks if r["inherent_rating"] == "Critical")
    res_crit = sum(1 for r in residual_risks if r["residual_rating"] == "Critical")
    direct = sum(1 for r in residual_risks if r["control_match_type"] == "direct")
    cross = sum(1 for r in residual_risks if r["control_match_type"] == "cross_mapped")
    none_ = sum(1 for r in residual_risks if r["control_match_type"] == "none")

    print(f"\nInherent Critical: {inh_crit} → Residual Critical: {res_crit}")
    print(f"Controls: {direct} direct, {cross} cross-mapped, {none_} uncontrolled")
    print(f"\nOutput: {output_path}")


if __name__ == "__main__":
    main()
