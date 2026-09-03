#!/usr/bin/env python3
"""Regression tests for the blend-aware overlay tool.

Pins the process bug from issue #16 on the incident fixture (v0.78's own
numbers, all read from the committed v0.77/v0.78 artifacts — no network):

  (a) v0.77 tables + v0.78 measured rates  ->  the tool's scaling recipe
      (new_q = parent_q * scale, scale = clamped rate/pool-max) reproduces
      the committed v0.78 quality_means tables.
  (b) the blend-derived winner map (alpha*qNorm + (1-alpha)*(1-cNorm), the
      blendScoresV2 per-cluster term) DIFFERS from the raw quality argmax map
      on the same fixture — the raw rule orphaned 7 clusters (2,9,10,11,15 +
      0,13 shifts) to the expensive kimi-k3, which the runtime blend never
      routes there.
  (c) the blend map for v0.78 equals the verified v0.78 map from
      SHARED_FACTS (glm-5.3/motif-3/kimi-k2.7-code distribution), and the
      v0.77 blend map equals the verified diverse v0.77 map.

Run: python3 scripts/scorer_sim/overlay_test.py
"""

import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay  # noqa: E402

ART = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "internal", "router", "cluster", "artifacts")
ART = os.path.normpath(ART)

MODELS = [
    "zai-org/glm-5.3",
    "deepseek-ai/deepseek-v4-flash",
    "moonshotai/kimi-k2.7-code",
    "moonshotai/kimi-k3",
    "motif-technologies/motif-3",
    "qwen/qwen3.8-27b",
]

# v0.78 changelog measured rates (rounded to 4dp there; tolerance covers it).
V078_RATES = {
    "zai-org/glm-5.3": 0.8707,
    "deepseek-ai/deepseek-v4-flash": 0.5267,
    "moonshotai/kimi-k2.7-code": 0.8707,
    "moonshotai/kimi-k3": 0.8710,
    "motif-technologies/motif-3": 0.8617,
    "qwen/qwen3.8-27b": 0.8537,
}

# Verified blend winner maps (SHARED_FACTS, root-replicated through the exact
# runtime blend). Short names: glm, flash, k2.7, kimi-k3, motif, qwen.
V077_BLEND_MAP = ["moonshotai/kimi-k3", "motif-technologies/motif-3",
                  "deepseek-ai/deepseek-v4-flash",
                  "motif-technologies/motif-3", "motif-technologies/motif-3",
                  "motif-technologies/motif-3", "motif-technologies/motif-3",
                  "motif-technologies/motif-3", "motif-technologies/motif-3",
                  "deepseek-ai/deepseek-v4-flash",
                  "deepseek-ai/deepseek-v4-flash",
                  "deepseek-ai/deepseek-v4-flash",
                  "motif-technologies/motif-3", "moonshotai/kimi-k3",
                  "motif-technologies/motif-3",
                  "deepseek-ai/deepseek-v4-flash"]
V078_BLEND_MAP = ["zai-org/glm-5.3", "motif-technologies/motif-3",
                  "moonshotai/kimi-k2.7-code", "motif-technologies/motif-3",
                  "motif-technologies/motif-3", "motif-technologies/motif-3",
                  "motif-technologies/motif-3", "motif-technologies/motif-3",
                  "motif-technologies/motif-3",
                  "motif-technologies/motif-3",
                  "motif-technologies/motif-3",
                  "moonshotai/kimi-k2.7-code",
                  "motif-technologies/motif-3", "zai-org/glm-5.3",
                  "motif-technologies/motif-3",
                  "motif-technologies/motif-3"]


def load_q(ver):
    with open(os.path.join(ART, ver, "quality_means.json")) as f:
        return json.load(f)["quality_means"]


def load_axes(ver):
    with open(os.path.join(ART, ver, "model_axes.json")) as f:
        return json.load(f)["axes"]


def load_alpha(ver):
    with open(os.path.join(ART, ver, "metadata.yaml")) as f:
        return overlay.parse_alpha(f.read())


def costs_from_axes(axes):
    return {m: axes[m]["input_per_1k_usd"] for m in MODELS}


class TestV078RecipeReproduction(unittest.TestCase):
    """The scaling recipe must reproduce the committed v0.78 tables from
    v0.77 tables + v0.78 rates."""

    def test_scales_match_changelog(self):
        # Uniform per-tier rates keep the weighted combined rate equal to
        # each model's changelog rate (weights sum to 1.0).
        rates = {tier: {m: V078_RATES[m] for m in MODELS}
                 for tier, _w in overlay.TIERS}
        scales, combined, pool_max = overlay.compute_scales(
            rates, overlay.DEFAULT_TIER_LEADERS)
        self.assertAlmostEqual(pool_max, 0.8710, places=6)
        expected = {"zai-org/glm-5.3": 0.9996,
                    "deepseek-ai/deepseek-v4-flash": 0.6047,
                    "moonshotai/kimi-k2.7-code": 0.9996,
                    "moonshotai/kimi-k3": 1.0000,
                    "motif-technologies/motif-3": 0.9893,
                    "qwen/qwen3.8-27b": 0.9801}
        for m, want in expected.items():
            self.assertAlmostEqual(scales[m], want, delta=2e-4,
                                   msg=f"scale for {m}")
            self.assertAlmostEqual(combined[m], V078_RATES[m], places=6)

    def test_v078_tables_reproduced(self):
        q77 = load_q("v0.77")
        q78 = load_q("v0.78")
        axes = load_axes("v0.78")
        alpha = load_alpha("v0.78")
        self.assertEqual(len(alpha), 16)
        # Combined rates = plain V078_RATES (each tier weighted 0.4/0.2/...)
        # Reconstruct per-tier files whose weighted sum equals the changelog
        # combined rate: split combined across tiers by weight share.
        rates = {tier: {m: V078_RATES[m] for m in MODELS}
                 for tier, _w in overlay.TIERS}
        scales, _combined, _pool = overlay.compute_scales(
            rates, overlay.DEFAULT_TIER_LEADERS)
        # uniform split keeps combined == V078_RATES since weights sum to 1
        for m in MODELS:
            self.assertAlmostEqual(scales[m], V078_RATES[m] / 0.8710,
                                   places=6)
        new_q = overlay.scale_quality(q77, scales)
        max_abs = 0.0
        for k, row in q78.items():
            for m, want in row.items():
                got = new_q[k][m]
                max_abs = max(max_abs, abs(got - want))
        # v0.78 changelog recorded rates at 4dp; rounding there bounds the
        # reproduction error (~1e-5 relative on the scale, ~6e-5 absolute).
        self.assertLess(max_abs, 1e-3,
                        f"v0.78 tables not reproduced, max abs err {max_abs}")
        # tightness: per-model scale rel err bounded by 4dp rate rounding
        for m in MODELS:
            want_scale = V078_RATES[m] / 0.8710
            self.assertLess(
                abs(scales[m] - want_scale) / want_scale, 1e-4, m)
        del axes, alpha  # axes/alpha exercised in blend tests below


class TestBlendVsRawArgmaxIncident(unittest.TestCase):
    """The process bug: raw quality argmax != runtime blend winner map."""

    def test_blend_map_differs_from_raw_argmax_v078(self):
        q = load_q("v0.78")
        alpha = load_alpha("v0.78")
        costs = costs_from_axes(load_axes("v0.78"))
        blend = overlay.derive_blend_winners(q, costs, alpha)
        raw = overlay.raw_argmax_winners(q)
        blend_map = [blend[k] for k in range(16)]
        raw_map = [raw[k] for k in range(16)]
        self.assertNotEqual(
            blend_map, raw_map,
            "blend map unexpectedly equals raw-argmax map; the incident "
            "fixture no longer discriminates")
        # The incident: raw argmax handed kimi-k3 7 clusters...
        k3_raw = overlay.fmt_winset(raw, "moonshotai/kimi-k3")
        self.assertEqual(sorted(k3_raw), [0, 2, 9, 10, 11, 13, 15])
        # ...while the blend matches the verified v0.78 map on every
        # diverging cluster (conversational 2,11 -> cheap kimi-k2.7-code;
        # 9,10,15 -> motif-3) — never the expensive kimi-k3.
        for k in range(16):
            self.assertEqual(
                blend_map[k], V078_BLEND_MAP[k],
                f"cluster {k}: blend picked {blend_map[k]!r}, verified v0.78 "
                f"map says {V078_BLEND_MAP[k]!r}")
        for k in (2, 9, 10, 11, 15):
            self.assertNotEqual(
                blend_map[k], "moonshotai/kimi-k3",
                f"cluster {k}: blend must not orphan conversational clusters "
                f"to the expensive kimi-k3")

    def test_v078_blend_map_matches_facts(self):
        q = load_q("v0.78")
        alpha = load_alpha("v0.78")
        costs = costs_from_axes(load_axes("v0.78"))
        blend = overlay.derive_blend_winners(q, costs, alpha)
        self.assertEqual([blend[k] for k in range(16)], V078_BLEND_MAP)

    def test_v077_blend_map_matches_facts(self):
        q = load_q("v0.77")
        alpha = load_alpha("v0.77")
        costs = costs_from_axes(load_axes("v0.77"))
        blend = overlay.derive_blend_winners(q, costs, alpha)
        self.assertEqual([blend[k] for k in range(16)], V077_BLEND_MAP)


class TestToolValidation(unittest.TestCase):
    def test_refuses_existing_version_dir(self):
        out = os.path.join(ART, "v0.78")
        with self.assertRaisesRegex(overlay.OverlayError,
                                    "refusing to overwrite"):
            overlay.build_bundle(
                "v0.77", ART, "v0.78",
                rates_dir=os.path.join(ART, "..", "..", "..", "nonexistent"),
                rates_prefix="zz", tier_leaders=overlay.DEFAULT_TIER_LEADERS,
                test_dates="2026-09-03")
        del out  # existence checked via exception above

    def test_missing_rates_file_fails_loudly(self):
        with self.assertRaisesRegex(overlay.OverlayError, "missing rates file"):
            overlay.build_bundle(
                "v0.78", ART, "v0.99-test",
                rates_dir="/nonexistent-rates", rates_prefix="zz",
                tier_leaders=overlay.DEFAULT_TIER_LEADERS,
                test_dates="2026-09-03")

    def test_alpha_parse(self):
        alpha = load_alpha("v0.78")
        self.assertEqual(len(alpha), 16)
        self.assertEqual(alpha[2], 0.8)
        self.assertEqual(alpha[0], 0.96)

    def test_version_bump(self):
        self.assertEqual(overlay.bump_version("v0.78"), "v0.79")
        with self.assertRaisesRegex(overlay.OverlayError, "auto-bump"):
            overlay.bump_version("latest")

    def test_centroids_header(self):
        k, dim = overlay.read_centroids_header(
            os.path.join(ART, "v0.78", "centroids.bin"))
        self.assertEqual((k, dim), (16, 768))


if __name__ == "__main__":
    unittest.main(verbosity=2)
