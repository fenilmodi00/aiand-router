function mountQuiz(root, questions) {
  questions.forEach((q, qi) => {
    const box = document.createElement("div");
    box.className = "q";
    const title = document.createElement("h3");
    title.textContent = (qi + 1) + ". " + q.prompt;
    box.appendChild(title);
    const fb = document.createElement("p");
    fb.className = "feedback";
    q.options.forEach((opt) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "opt";
      b.textContent = opt.text;
      b.addEventListener("click", () => {
        [...box.querySelectorAll(".opt")].forEach((el) => {
          el.disabled = true;
          if (el.textContent === q.answer) el.classList.add("correct");
        });
        if (opt.text === q.answer) {
          b.classList.add("correct");
          fb.textContent = q.ok;
        } else {
          b.classList.add("wrong");
          fb.textContent = q.no;
        }
      });
      box.appendChild(b);
    });
    box.appendChild(fb);
    root.appendChild(box);
  });
}

function mountRungCheck(root, items, diagnose) {
  const state = {};
  items.forEach((item) => {
    const row = document.createElement("label");
    row.className = "check";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.addEventListener("change", () => {
      state[item.id] = input.checked;
      out.textContent = diagnose(state);
    });
    row.appendChild(input);
    row.appendChild(document.createTextNode(item.label));
    root.appendChild(row);
  });
  const out = document.createElement("p");
  out.className = "verdict";
  out.textContent = diagnose(state);
  root.appendChild(out);
}
