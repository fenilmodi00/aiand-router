function mountJsonlCheck(root, starter) {
  const area = document.createElement("textarea");
  area.className = "paste";
  area.spellcheck = false;
  area.value = starter;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "opt";
  btn.textContent = "Validate this JSONL";
  const out = document.createElement("p");
  out.className = "feedback";
  const counts = document.createElement("p");
  counts.className = "counts";

  function run() {
    const lines = area.value.split(/\r?\n/);
    let ok = 0;
    let bad = 0;
    const bins = {};
    const phases = {};
    const problems = [];
    lines.forEach((line, i) => {
      if (!line.trim()) return;
      let row;
      try {
        row = JSON.parse(line);
      } catch (e) {
        bad += 1;
        problems.push("line " + (i + 1) + ": not JSON");
        return;
      }
      const hasPrompt = typeof row.prompt === "string" && row.prompt.trim();
      const msgs = Array.isArray(row.messages) && row.messages.length;
      if (!hasPrompt && !msgs) {
        bad += 1;
        problems.push("line " + (i + 1) + ": need prompt or messages");
        return;
      }
      ok += 1;
      const b = row.hint_bin || "(none)";
      const p = row.phase || "(none)";
      bins[b] = (bins[b] || 0) + 1;
      phases[p] = (phases[p] || 0) + 1;
    });
    if (bad === 0 && ok > 0) {
      out.textContent = ok + " valid quer" + (ok === 1 ? "y" : "ies") + ". This file can be passed to the train CLI.";
      out.style.color = "var(--ok)";
    } else if (ok === 0) {
      out.textContent = "No valid rows. Each line must be one JSON object.";
      out.style.color = "var(--bad)";
    } else {
      out.textContent = bad + " bad line(s). " + problems.slice(0, 4).join("; ");
      out.style.color = "var(--bad)";
    }
    const binTxt = Object.keys(bins).sort().map((k) => k + "=" + bins[k]).join("  ");
    const phTxt = Object.keys(phases).sort().map((k) => k + "=" + phases[k]).join("  ");
    counts.textContent = "hint_bin: " + binTxt + "\nphase: " + phTxt;
  }

  btn.addEventListener("click", run);
  root.appendChild(area);
  root.appendChild(btn);
  root.appendChild(out);
  root.appendChild(counts);
}
