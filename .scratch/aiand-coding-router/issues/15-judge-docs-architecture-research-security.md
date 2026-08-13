# 15 — Judge docs: architecture, research, security, credits

**What to build:** A judge or future owner can read how the gateway works, what was researched vs assumed, how keys and logs are handled, and how much credit a demo is planned to use — without treating AA priors as aiand measurements.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Short `ARCHITECTURE.md` explains gateway vs flashlight, per-step routing, and fake-upstream tests
- [x] Short `RESEARCH.md` after the proxy works (not a blocker literature review): Pioneer/FireRouter inspiration vs what we actually shipped
- [x] Security note: gateway holds `AIAND_API_KEY`, clients send `ROUTER_API_KEY`, nothing in logs/replay/frontend
- [x] Credit note: rehearsal / 3×5 matrix / reserve; demo spend labeled plan vs measured
- [x] README links these files and still refuses an invented savings percentage
