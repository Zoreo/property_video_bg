// Saved agent profiles, kept in this browser only (no accounts in v1).
(function () {
  const KEY = "agentProfiles";
  const FIELDS = ["agent_name", "agency", "agent_phone", "agent_email"];
  const form = document.querySelector("form.form");
  const picker = document.getElementById("saved-profiles");
  const save = document.getElementById("save-profile");
  if (!form || !picker) return;

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
  }
  function store(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* private mode */ }
  }

  const profiles = load();
  if (profiles.length) {
    profiles.forEach((p, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = p.agent_name + (p.agency ? " · " + p.agency : "");
      picker.appendChild(opt);
    });
    picker.hidden = false;
    // A new order with empty agent fields starts from the last used profile.
    if (!form.agent_name.value) fill(profiles[0]);
  }

  function fill(p) {
    FIELDS.forEach((f) => { if (p[f] !== undefined) form[f].value = p[f]; });
  }

  picker.addEventListener("change", () => {
    const p = profiles[Number(picker.value)];
    if (p) fill(p);
  });

  form.addEventListener("submit", () => {
    if (!save.checked) return;
    const p = Object.fromEntries(FIELDS.map((f) => [f, form[f].value.trim()]));
    if (!p.agent_name) return;
    const rest = profiles.filter((x) => x.agent_email !== p.agent_email || x.agent_name !== p.agent_name);
    store([p, ...rest].slice(0, 5));
  });
})();
