// Photo upload, ordering and staging options for one order.
(function () {
  const root = document.getElementById("photos");
  const orderId = root.dataset.order;
  const max = Number(root.dataset.max);
  const secondsPer = Number(root.dataset.seconds);
  const api = `/api/orders/${orderId}/photos`;

  const grid = document.getElementById("photo-grid");
  const input = document.getElementById("file-input");
  const dropzone = document.getElementById("dropzone");
  const errorBox = document.getElementById("photo-error");
  const count = document.getElementById("photo-count");
  const stagingToggle = document.getElementById("staging-toggle");
  const styles = document.getElementById("styles");
  const total = document.getElementById("total");
  const length = document.getElementById("video-length");
  const payBtn = document.getElementById("pay-btn");

  let photos = [];
  let uploading = 0;

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.hidden = !msg;
  }

  async function request(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      let msg = "Something went wrong. Please try again.";
      try { msg = (await res.json()).detail || msg; } catch { /* not json */ }
      throw new Error(typeof msg === "string" ? msg : "Please check the photo and try again.");
    }
    return res.status === 204 ? null : res.json();
  }

  function eur(cents) {
    return (cents % 100 === 0 ? cents / 100 : (cents / 100).toFixed(2)) + " EUR";
  }

  function update() {
    const staging = stagingToggle.checked;
    styles.hidden = !staging;
    root.classList.toggle("staging-on", staging);
    count.textContent = `${photos.length} / ${max}`;
    length.textContent = String(photos.length * secondsPer);
    total.textContent = eur(Number(total.dataset.base) + (staging ? Number(total.dataset.staging) : 0));
    dropzone.hidden = photos.length + uploading >= max;
    const needsEmpty = staging && !photos.some((p) => p.is_empty_room);
    payBtn.disabled = photos.length === 0 || uploading > 0 || needsEmpty;
    payBtn.textContent = needsEmpty ? 'Mark at least one "Empty room"' : uploading ? "Uploading…" : "Continue to payment";
  }

  function render() {
    grid.innerHTML = "";
    photos.forEach((p, i) => {
      const li = document.createElement("li");
      li.className = "photo";
      li.dataset.id = p.id;
      li.innerHTML = `
        <img src="${p.url}" alt="Photo ${i + 1}" loading="lazy" draggable="false">
        <span class="pos">${i + 1}</span>
        <button type="button" class="handle" aria-label="Drag to reorder" title="Drag to reorder">⠿</button>
        <button type="button" class="remove" aria-label="Remove photo ${i + 1}">×</button>
        <div class="photo-bar">
          <button type="button" class="move" data-dir="-1" aria-label="Move earlier" ${i === 0 ? "disabled" : ""}>‹</button>
          <label class="empty-room"><input type="checkbox" ${p.is_empty_room ? "checked" : ""}> Empty room</label>
          <button type="button" class="move" data-dir="1" aria-label="Move later" ${i === photos.length - 1 ? "disabled" : ""}>›</button>
        </div>`;
      grid.appendChild(li);
    });
    for (let i = 0; i < uploading; i++) {
      const li = document.createElement("li");
      li.className = "photo placeholder";
      li.innerHTML = '<span class="spinner" aria-label="Uploading"></span>';
      grid.appendChild(li);
    }
    update();
  }

  async function saveOrder(ids) {
    try {
      photos = await request(`${api}/order`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
    } catch (e) {
      showError(e.message);
    }
    render();
  }

  async function upload(files) {
    showError("");
    const room = max - photos.length - uploading;
    const list = Array.from(files).filter((f) => f.type.startsWith("image/") || f.name.match(/\.(jpe?g|png|webp|heic)$/i));
    if (list.length > room) showError(`Only ${max} photos fit. The first ${room} were added.`);
    const take = list.slice(0, Math.max(room, 0));
    uploading += take.length;
    render();
    for (const file of take) {  // one at a time: kinder to phone connections
      const body = new FormData();
      body.append("file", file);
      try {
        photos.push(await request(api, { method: "POST", body }));
      } catch (e) {
        showError(`${file.name}: ${e.message}`);
      }
      uploading -= 1;
      render();
    }
  }

  input.addEventListener("change", () => { upload(input.files); input.value = ""; });
  ["dragover", "dragenter"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => dropzone.addEventListener(ev, () => dropzone.classList.remove("over")));
  dropzone.addEventListener("drop", (e) => { e.preventDefault(); upload(e.dataTransfer.files); });

  grid.addEventListener("click", async (e) => {
    const li = e.target.closest(".photo");
    if (!li || li.classList.contains("placeholder")) return;
    const id = Number(li.dataset.id);
    if (e.target.closest(".remove")) {
      try {
        await request(`${api}/${id}`, { method: "DELETE" });
        photos = photos.filter((p) => p.id !== id);
        render();
      } catch (err) { showError(err.message); }
    } else if (e.target.closest(".move")) {
      const i = photos.findIndex((p) => p.id === id);
      const j = i + Number(e.target.closest(".move").dataset.dir);
      if (j < 0 || j >= photos.length) return;
      const ids = photos.map((p) => p.id);
      [ids[i], ids[j]] = [ids[j], ids[i]];
      saveOrder(ids);
    }
  });

  grid.addEventListener("change", async (e) => {
    if (!e.target.matches(".empty-room input")) return;
    const id = Number(e.target.closest(".photo").dataset.id);
    try {
      const p = await request(`${api}/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_empty_room: e.target.checked }),
      });
      photos = photos.map((x) => (x.id === id ? p : x));
      update();
    } catch (err) { showError(err.message); }
  });

  // Drag to reorder with pointer events: works with mouse, touch and pen.
  // On touch, dragging starts from the handle so the page still scrolls normally.
  let drag = null;
  grid.addEventListener("pointerdown", (e) => {
    const li = e.target.closest(".photo:not(.placeholder)");
    if (!li || e.target.closest("button:not(.handle), input, label")) return;
    if (e.pointerType !== "mouse" && !e.target.closest(".handle")) return;
    e.preventDefault();
    drag = { li, id: Number(li.dataset.id), startIds: photos.map((p) => p.id) };
    li.classList.add("dragging");
    li.setPointerCapture(e.pointerId);
  });
  grid.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const over = document.elementFromPoint(e.clientX, e.clientY);
    const target = over && over.closest(".photo:not(.placeholder)");
    if (!target || target === drag.li) return;
    const items = [...grid.children];
    const from = items.indexOf(drag.li);
    const to = items.indexOf(target);
    grid.insertBefore(drag.li, from < to ? target.nextSibling : target);
  });
  function endDrag() {
    if (!drag) return;
    drag.li.classList.remove("dragging");
    const ids = [...grid.querySelectorAll(".photo:not(.placeholder)")].map((li) => Number(li.dataset.id));
    const changed = ids.join() !== drag.startIds.join();
    drag = null;
    if (changed) saveOrder(ids); else render();
  }
  grid.addEventListener("pointerup", endDrag);
  grid.addEventListener("pointercancel", endDrag);

  stagingToggle.addEventListener("change", update);

  request(api).then((list) => { photos = list; render(); }).catch((e) => showError(e.message));
})();
