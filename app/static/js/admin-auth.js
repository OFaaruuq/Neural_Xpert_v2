document.querySelectorAll("[data-reveal]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = button.parentElement.querySelector("input");
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.textContent = showing ? "Show" : "Hide";
    });
});

document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(button.getAttribute("data-copy") || "");
            button.textContent = "Copied";
        } catch (error) {
            button.textContent = "Copy failed";
        }
    });
});

document.querySelectorAll("[data-otp]").forEach((group) => {
    const hidden = group.querySelector('input[type="hidden"]');
    const digits = Array.from(group.querySelectorAll(".otp-digit"));
    const sync = () => {
        hidden.value = digits.map((digit) => digit.value).join("");
    };
    digits.forEach((input, index) => {
        input.addEventListener("input", () => {
            input.value = (input.value || "").replace(/\D/g, "").slice(-1);
            if (input.value && digits[index + 1]) {
                digits[index + 1].focus();
            }
            sync();
        });
        input.addEventListener("keydown", (event) => {
            if (event.key === "Backspace" && !input.value && digits[index - 1]) {
                digits[index - 1].focus();
            }
        });
        input.addEventListener("paste", (event) => {
            const text = (event.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, digits.length);
            if (!text) {
                return;
            }
            event.preventDefault();
            text.split("").forEach((character, offset) => {
                digits[offset].value = character;
            });
            const next = digits[Math.min(text.length, digits.length - 1)];
            next.focus();
            sync();
        });
    });
    group.closest("form").addEventListener("submit", sync);
});
