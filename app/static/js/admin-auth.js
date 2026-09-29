document.querySelectorAll("[data-reveal]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = button.parentElement.querySelector("input");
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.textContent = showing ? "Show" : "Hide";
        button.setAttribute("aria-pressed", showing ? "false" : "true");
    });
});

document.querySelectorAll("[data-copy]").forEach((button) => {
    const label = button.textContent;
    button.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(button.getAttribute("data-copy") || "");
            button.textContent = "Copied";
        } catch (error) {
            button.textContent = "Copy failed";
        }
        window.setTimeout(() => {
            button.textContent = label;
        }, 1600);
    });
});

function fillDigits(digits, start, text) {
    const clean = (text || "").replace(/\D/g, "");
    if (!clean) {
        return;
    }
    clean.split("").forEach((character, offset) => {
        if (digits[start + offset]) {
            digits[start + offset].value = character;
        }
    });
    const next = digits[Math.min(start + clean.length, digits.length - 1)];
    if (next) {
        next.focus();
    }
}

document.querySelectorAll("[data-otp]").forEach((group) => {
    const hidden = group.querySelector('input[type="hidden"]');
    const digits = Array.from(group.querySelectorAll(".otp-digit"));
    const sync = () => {
        hidden.value = digits.map((digit) => digit.value).join("");
    };
    digits.forEach((input, index) => {
        input.addEventListener("input", () => {
            const clean = (input.value || "").replace(/\D/g, "");
            if (clean.length > 1) {
                fillDigits(digits, index, clean);
            } else {
                input.value = clean.slice(0, 1);
                if (input.value && digits[index + 1]) {
                    digits[index + 1].focus();
                }
            }
            sync();
        });
        input.addEventListener("keydown", (event) => {
            if (event.key === "Backspace" && !input.value && digits[index - 1]) {
                digits[index - 1].focus();
            }
            if (event.key === "ArrowLeft" && digits[index - 1]) {
                digits[index - 1].focus();
            }
            if (event.key === "ArrowRight" && digits[index + 1]) {
                digits[index + 1].focus();
            }
        });
        input.addEventListener("paste", (event) => {
            const text = event.clipboardData.getData("text") || "";
            if (!/\d/.test(text)) {
                return;
            }
            event.preventDefault();
            fillDigits(digits, index, text);
            sync();
        });
    });
    group.closest("form").addEventListener("submit", sync);
});

document.querySelectorAll("form.auth-card").forEach((form) => {
    form.addEventListener("submit", (event) => {
        const notice = form.querySelector("[data-form-error]");
        const recovery = form.querySelector('[name="recovery_code"]');
        const usingRecovery = recovery && recovery.value.trim();
        let missing = false;
        form.querySelectorAll("[data-otp]").forEach((group) => {
            const hidden = group.querySelector('input[type="hidden"]');
            const expected = group.querySelectorAll(".otp-digit").length;
            if (usingRecovery && hidden && hidden.name === "totp_code") {
                return;
            }
            if (hidden && hidden.value.length < expected) {
                missing = true;
            }
        });
        if (missing) {
            event.preventDefault();
            if (notice) {
                notice.hidden = false;
                notice.textContent = "Enter every digit of the code.";
            }
            return;
        }
        const button = form.querySelector(".auth-submit");
        if (button) {
            button.disabled = true;
            button.textContent = "Please wait…";
        }
    });
});
