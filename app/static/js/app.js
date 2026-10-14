/* PrintWise front-end behaviour.
   Plain JavaScript, no inline scripts (the site's security policy blocks those).
   1. Client-side form validation   2. Password show/hide + strength
   3. Confirm dialogs               4. Order form (filtered options, file check, live summary)
   5. Small helpers (auto-submit filters, copy to clipboard) */
(function () {
  "use strict";

  const qs = (sel, root) => (root || document).querySelector(sel);
  const qsa = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /* ---------- 1. Client-side validation ---------- */
  function messageFor(field) {
    if (field.dataset.msg) return field.dataset.msg;
    return field.validationMessage;
  }

  function showFieldError(field) {
    const holder = field.closest(".mb-3, .col, [class*='col-']") || field.parentElement;
    let feedback = qs(".invalid-feedback[data-client]", holder);
    if (!feedback) {
      feedback = document.createElement("div");
      feedback.className = "invalid-feedback";
      feedback.dataset.client = "1";
      (field.closest(".input-group") || field).after(feedback);
    }
    feedback.textContent = messageFor(field);
  }

  function checkPasswordMatch(form) {
    const first = qs("[data-password-main]", form);
    const second = qs("[data-password-confirm]", form);
    if (first && second) {
      second.setCustomValidity(second.value && first.value !== second.value ? "The two passwords do not match." : "");
    }
  }

  qsa("form.needs-validation").forEach(function (form) {
    form.setAttribute("novalidate", "");
    form.addEventListener("input", function (event) {
      checkPasswordMatch(form);
      if (event.target.classList && event.target.classList.contains("is-invalid") && event.target.checkValidity()) {
        event.target.classList.remove("is-invalid");
      }
    });
    form.addEventListener("submit", function (event) {
      checkPasswordMatch(form);
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
        qsa(":invalid", form).forEach(function (field) {
          field.classList.add("is-invalid");
          showFieldError(field);
        });
        const first = qs(":invalid", form);
        if (first) first.focus();
        return;
      }
      /* Stop double clicks: lock the submit button once the form is valid. */
      qsa("button[type=submit]", form).forEach(function (button) {
        if (button.dataset.noLock !== undefined) return;
        window.setTimeout(function () {
          button.disabled = true;
          button.dataset.originalText = button.textContent;
          button.textContent = "Please wait";
        }, 0);
      });
    });
  });

  /* ---------- 2. Password show/hide and strength ---------- */
  qsa("[data-toggle-password]").forEach(function (button) {
    button.addEventListener("click", function () {
      const input = qs("#" + button.dataset.togglePassword);
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
      button.querySelector(".bi").className = "bi " + (show ? "bi-eye-slash" : "bi-eye");
    });
  });

  qsa("[data-strength-input]").forEach(function (input) {
    const meter = qs("#" + input.dataset.strengthInput);
    if (!meter) return;
    const bar = meter.firstElementChild;
    const label = qs("#" + input.dataset.strengthInput + "-text");
    input.addEventListener("input", function () {
      const value = input.value;
      let score = 0;
      if (value.length >= 8) score++;
      if (/[A-Za-z]/.test(value) && /\d/.test(value)) score++;
      if (value.length >= 12) score++;
      if (/[^A-Za-z0-9]/.test(value)) score++;
      const colors = ["#e5197f", "#e5197f", "#ffb400", "#2fa36b", "#2fa36b"];
      const words = ["", "Too weak", "Okay", "Good", "Strong"];
      if (!value) { bar.style.width = "0"; if (label) label.textContent = ""; return; }
      bar.style.width = (score * 25 || 10) + "%";
      bar.style.background = colors[score];
      if (label) label.textContent = words[Math.max(score, 1)];
    });
  });

  /* ---------- 3. Confirm dialogs ---------- */
  const modalElement = qs("#confirmModal");
  if (modalElement && window.bootstrap) {
    const modal = new window.bootstrap.Modal(modalElement);
    let pendingForm = null;
    qsa("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.confirmed === "1") return;
        event.preventDefault();
        pendingForm = form;
        qs("#confirmModalText").textContent = form.dataset.confirm;
        const okButton = qs("#confirmModalOk");
        okButton.textContent = form.dataset.confirmLabel || "Yes, continue";
        modal.show();
      });
    });
    qs("#confirmModalOk").addEventListener("click", function () {
      if (!pendingForm) return;
      pendingForm.dataset.confirmed = "1";
      modal.hide();
      pendingForm.submit();
    });
  }

  /* ---------- 4. Order form ---------- */
  const orderForm = qs("#order-form");
  if (orderForm) {
    const optionsData = JSON.parse((qs("#service-options") || { textContent: "{}" }).textContent || "{}");
    const service = qs("#f-service_id", orderForm);
    const size = qs("#f-paper_size", orderForm);
    const type = qs("#f-paper_type", orderForm);
    const customSize = qs("#custom-size-group", orderForm);
    const customType = qs("#custom-type-group", orderForm);
    const copies = qs("#f-copies", orderForm);
    const fileInput = qs("#f-file", orderForm);
    const drop = qs("#file-drop", orderForm);
    const maxBytes = 25 * 1024 * 1024;
    const allowed = (orderForm.dataset.extensions || "").split(",");

    function filterSelect(select, allowedValues) {
      let firstAllowed = null;
      Array.from(select.options).forEach(function (option) {
        if (!option.value) return;
        const ok = !allowedValues || allowedValues.indexOf(option.value) !== -1;
        option.hidden = !ok;
        option.disabled = !ok;
        if (ok && firstAllowed === null) firstAllowed = option.value;
      });
      const current = select.options[select.selectedIndex];
      if (!current || current.disabled) select.value = firstAllowed || "";
    }

    function applyService() {
      const data = optionsData[service.value];
      filterSelect(size, data ? data.sizes : null);
      filterSelect(type, data ? data.types : null);
      qsa("input[name=color_mode]", orderForm).forEach(function (radio) {
        const ok = !data || data.colors.indexOf(radio.value) !== -1;
        radio.disabled = !ok;
        radio.closest(".form-check").classList.toggle("pw-option-hidden", !ok);
      });
      const enabled = qsa("input[name=color_mode]:not(:disabled)", orderForm);
      if (enabled.length && !enabled.some(function (r) { return r.checked; })) enabled[0].checked = true;
      toggleCustom();
      updateSummary();
    }

    function toggleCustom() {
      const showSize = size.value === "Custom size";
      const showType = type.value === "Other (specify)";
      customSize.classList.toggle("d-none", !showSize);
      customType.classList.toggle("d-none", !showType);
      qs("input", customSize).required = showSize;
      qs("input", customType).required = showType;
    }

    function updateSummary() {
      const set = function (id, text) { const el = qs("#" + id); if (el) el.textContent = text || "Not chosen yet"; };
      set("sum-service", service.options[service.selectedIndex] && service.value ? service.options[service.selectedIndex].text : "");
      const sizeText = size.value === "Custom size" ? "Custom: " + (qs("input", customSize).value || "...") : size.value;
      const typeText = type.value === "Other (specify)" ? "Other: " + (qs("input", customType).value || "...") : type.value;
      set("sum-size", sizeText);
      set("sum-type", typeText);
      const color = qs("input[name=color_mode]:checked", orderForm);
      set("sum-color", color ? color.dataset.label : "");
      const sides = qs("input[name=sides]:checked", orderForm);
      set("sum-sides", sides ? sides.dataset.label : "");
      set("sum-copies", copies.value);
      const file = fileInput.files && fileInput.files[0];
      set("sum-file", file ? file.name : "");
    }

    function checkFile() {
      const file = fileInput.files && fileInput.files[0];
      fileInput.setCustomValidity("");
      drop.classList.remove("is-invalid");
      const note = qs("#file-note");
      if (!file) { note.textContent = "No file chosen yet."; return; }
      const ext = file.name.split(".").pop().toLowerCase();
      if (allowed.indexOf(ext) === -1) {
        fileInput.setCustomValidity("That file type is not allowed. Use " + allowed.join(", ").toUpperCase() + ".");
      } else if (file.size > maxBytes) {
        fileInput.setCustomValidity("That file is larger than 25 MB.");
      }
      note.textContent = file.name + " (" + (file.size / 1048576).toFixed(2) + " MB)";
      if (!fileInput.checkValidity()) {
        drop.classList.add("is-invalid");
        note.textContent = fileInput.validationMessage;
      }
    }

    service.addEventListener("change", applyService);
    [size, type].forEach(function (el) { el.addEventListener("change", function () { toggleCustom(); updateSummary(); }); });
    orderForm.addEventListener("input", updateSummary);
    orderForm.addEventListener("change", updateSummary);
    fileInput.addEventListener("change", function () { checkFile(); updateSummary(); });

    qsa("[data-step]", orderForm).forEach(function (button) {
      button.addEventListener("click", function () {
        const next = (parseInt(copies.value, 10) || 1) + parseInt(button.dataset.step, 10);
        copies.value = Math.min(500, Math.max(1, next));
        updateSummary();
      });
    });

    ["dragenter", "dragover"].forEach(function (name) {
      drop.addEventListener(name, function (event) { event.preventDefault(); drop.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (name) {
      drop.addEventListener(name, function (event) { event.preventDefault(); drop.classList.remove("is-over"); });
    });
    drop.addEventListener("drop", function (event) {
      if (event.dataTransfer && event.dataTransfer.files.length) {
        fileInput.files = event.dataTransfer.files;
        checkFile();
        updateSummary();
      }
    });

    applyService();
    checkFile();
  }

  /* ---------- 5. Small helpers ---------- */
  qsa("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });

  qsa("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      const source = qs("#" + button.dataset.copy);
      if (!source || !navigator.clipboard) return;
      navigator.clipboard.writeText(source.textContent.trim()).then(function () {
        const original = button.textContent;
        button.textContent = "Copied";
        window.setTimeout(function () { button.textContent = original; }, 1500);
      });
    });
  });
})();
