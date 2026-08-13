# 05 — Learned router stays dark

**What to build:** A second router sits behind the same decision interface as the rules router. The gateway keeps using rules unless an explicit comparison on the held-out slice of the 3×5 cache says the learned router wins. The demo ships if it is untrained or loses.

**Blocked by:** 04 — Measured comparison

**Status:** resolved

- [x] Rules and learned selection share one decision interface (`Decision`: model, phase, threshold, reason, candidates)
- [x] Default path consults only the rules router
- [x] A comparison command can score learned vs rules on the held-out slice of the existing cache
- [x] Learned is consulted in the gateway only after that comparison says it wins
- [x] No embedding or training pipeline is required for the demo to run
