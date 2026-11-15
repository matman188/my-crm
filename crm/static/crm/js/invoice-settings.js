(() => {
    "use strict";
    const form = document.querySelector("[data-invoice-settings]");
    if (!form) return;
    const trigger = form.querySelector("[data-preview-invoice]");
    const dialog = document.querySelector("[data-invoice-preview]");
    const frame = dialog.querySelector("[data-preview-frame]");
    const download = dialog.querySelector("[data-download-invoice-preview]");
    const status = dialog.querySelector("[data-preview-status]");
    const errors = form.querySelector("[data-preview-errors]");
    const sample = form.querySelector("[data-invoice-sample]");
    let controller = null;
    let objectUrl = null;
    function release() {
        frame.src = "about:blank";
        frame.hidden = true;
        download.hidden = true;
        download.removeAttribute("href");
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = null;
    }
    dialog.querySelector("[data-close-invoice-preview]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
        if (dialog.open) return;
        controller?.abort();
        release();
        trigger.focus();
    });
    trigger.addEventListener("click", async () => {
        if (controller || !form.reportValidity()) return;
        errors.hidden = true;
        release();
        const request = new AbortController();
        controller = request;
        trigger.disabled = true;
        status.textContent = "Preparing preview...";
        dialog.showModal();
        try {
            const body = new FormData(form);
            body.set("sample", sample.value);
            const response = await fetch(form.dataset.previewUrl, {
                method: "POST", body, credentials: "same-origin", signal: request.signal,
                headers: { "X-CSRFToken": form.elements.namedItem("csrfmiddlewaretoken").value },
            });
            if (!response.ok || !response.headers.get("Content-Type")?.startsWith("application/pdf")) {
                let message = "Could not prepare the preview. Check your settings or reload the page and try again.";
                if (response.headers.get("Content-Type")?.includes("application/json")) {
                    const result = await response.json();
                    message = result.message || Object.entries(result.errors || {}).flatMap(([name, entries]) => {
                        const field = form.elements.namedItem(name);
                        const label = field?.labels?.[0]?.textContent.replace(/\s*\*\s*$/, "").trim() || name.replaceAll("_", " ");
                        return entries.map(error => `${label}: ${error.message}`);
                    }).join("\n") || message;
                }
                throw new Error(message);
            }
            const blob = await response.blob();
            if (request.signal.aborted || !dialog.open) return;
            objectUrl = URL.createObjectURL(blob);
            frame.src = objectUrl;
            frame.hidden = false;
            download.href = objectUrl;
            download.hidden = false;
            status.textContent = "Preview ready. Settings have not been saved.";
        } catch (error) {
            if (!request.signal.aborted) {
                errors.textContent = error.message || "Could not prepare the preview. Please try again.";
                errors.hidden = false;
                dialog.close();
                errors.scrollIntoView({ block: "nearest" });
            }
        } finally {
            if (controller === request) controller = null;
            trigger.disabled = false;
        }
    });
})();
