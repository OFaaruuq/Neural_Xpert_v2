(function () {
    var root = document.querySelector("[data-ask-ai]");
    if (!root) return;

    var panel = root.querySelector("#nx-ask-panel");
    var openButton = root.querySelector("[data-ask-open]");
    var form = root.querySelector("[data-ask-form]");
    var input = root.querySelector("[data-ask-input]");
    var log = root.querySelector("[data-ask-log]");
    var send = root.querySelector("[data-ask-send]");
    var prompts = root.querySelector("[data-ask-prompts]");
    var count = root.querySelector("[data-ask-count]");
    var welcome = log.getAttribute("data-welcome") || "";
    var history = [];
    var pending = false;
    var pageOverflow = "";

    function reducedMotion() {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    function scrollLog() {
        log.scrollTo({
            top: log.scrollHeight,
            behavior: reducedMotion() ? "auto" : "smooth"
        });
    }

    function focusable() {
        return Array.prototype.filter.call(
            panel.querySelectorAll("button, textarea, a[href]"),
            function (el) {
                return !el.disabled && el.getAttribute("hidden") === null && el.offsetParent !== null;
            }
        );
    }

    function lockPage(open) {
        var mobile = window.matchMedia("(max-width: 575px)").matches;
        if (open && mobile) {
            pageOverflow = document.body.style.overflow;
            document.body.style.overflow = "hidden";
            return;
        }
        document.body.style.overflow = pageOverflow || "";
    }

    function setOpen(open) {
        panel.hidden = !open;
        root.querySelector(".nx-ask-backdrop").hidden = !open;
        root.classList.toggle("is-open", open);
        openButton.setAttribute("aria-expanded", open ? "true" : "false");
        lockPage(open);
        if (open) {
            window.setTimeout(function () { input.focus(); }, 30);
        } else {
            openButton.focus();
        }
    }

    function avatar() {
        var mark = document.createElement("span");
        mark.className = "nx-ask-avatar";
        mark.setAttribute("aria-hidden", "true");
        mark.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M12 2.4 13.7 8l5.6 1.7-5.6 1.7L12 17.1 10.3 11.4 4.7 9.7 10.3 8 12 2.4Z"/></svg>';
        return mark;
    }

    function addRow(kind) {
        var row = document.createElement("div");
        row.className = "nx-ask-row " + (kind === "user" ? "nx-ask-row-user" : "nx-ask-row-bot");
        if (kind !== "user") row.appendChild(avatar());
        var bubble = document.createElement("div");
        bubble.className = "nx-ask-bubble " + (kind === "user" ? "nx-ask-user nx-ask-plain" : "nx-ask-bot");
        row.appendChild(bubble);
        log.appendChild(row);
        scrollLog();
        return bubble;
    }

    function appendInline(parent, text) {
        var pattern = /(\*\*[^*]+\*\*|https?:\/\/[^\s<]+)/g;
        var last = 0;
        var match;
        while ((match = pattern.exec(text))) {
            if (match.index > last) parent.appendChild(document.createTextNode(text.slice(last, match.index)));
            var token = match[0];
            if (token.charAt(0) === "*") {
                var strong = document.createElement("strong");
                strong.textContent = token.slice(2, -2);
                parent.appendChild(strong);
            } else {
                var link = document.createElement("a");
                link.href = token.replace(/[),.;]+$/, "");
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = link.getAttribute("href");
                parent.appendChild(link);
                var tail = token.slice(link.getAttribute("href").length);
                if (tail) parent.appendChild(document.createTextNode(tail));
            }
            last = match.index + token.length;
        }
        if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
    }

    function appendFormatted(parent, text) {
        var lines = String(text).replace(/\r\n/g, "\n").split("\n");
        var list = null;
        function closeList() {
            if (!list) return;
            parent.appendChild(list);
            list = null;
        }
        lines.forEach(function (line) {
            var bullet = /^\s*[-•]\s+(.*)$/.exec(line);
            var numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
            if (bullet || numbered) {
                var ordered = Boolean(numbered);
                if (!list || (ordered && list.tagName !== "OL") || (!ordered && list.tagName !== "UL")) {
                    closeList();
                    list = document.createElement(ordered ? "ol" : "ul");
                }
                var item = document.createElement("li");
                appendInline(item, (bullet || numbered)[1]);
                list.appendChild(item);
                return;
            }
            closeList();
            if (!line.trim()) return;
            var paragraph = document.createElement("p");
            appendInline(paragraph, line);
            parent.appendChild(paragraph);
        });
        closeList();
    }

    function copyButton(text) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "nx-ask-copy";
        button.textContent = "Copy";
        button.addEventListener("click", function () {
            function done() {
                button.textContent = "Copied";
                window.setTimeout(function () { button.textContent = "Copy"; }, 1400);
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(done).catch(function () {
                    button.textContent = "Copy";
                });
                return;
            }
            button.textContent = "Copy";
        });
        return button;
    }

    function showAnswer(bubble, text) {
        bubble.classList.remove("nx-ask-pending");
        bubble.textContent = "";
        var body = document.createElement("div");
        appendFormatted(body, text);
        bubble.appendChild(body);
        bubble.appendChild(copyButton(text));
    }

    function showError(bubble, message, retryText) {
        bubble.classList.remove("nx-ask-pending");
        bubble.classList.add("nx-ask-error");
        bubble.textContent = "";
        var messageNode = document.createElement("p");
        messageNode.textContent = message;
        bubble.appendChild(messageNode);
        if (!retryText) return;
        var retry = document.createElement("button");
        retry.type = "button";
        retry.className = "nx-ask-retry";
        retry.textContent = "Try again";
        retry.addEventListener("click", function () {
            if (pending) return;
            input.value = retryText;
            fitInput();
            form.requestSubmit();
        });
        bubble.appendChild(retry);
    }

    function showWelcome() {
        if (prompts && prompts.parentNode === log) log.removeChild(prompts);
        while (log.firstChild) log.removeChild(log.firstChild);
        log.classList.remove("is-thread");
        var bubble = addRow("bot");
        bubble.classList.add("nx-ask-plain");
        bubble.textContent = welcome;
        bubble.setAttribute("data-ask-welcome", "");
        if (prompts) {
            prompts.hidden = false;
            log.appendChild(prompts);
        }
    }

    function fitInput() {
        input.style.height = "46px";
        input.style.height = Math.min(input.scrollHeight, 120) + "px";
    }

    function syncComposer() {
        var length = input.value.length;
        send.disabled = pending || !input.value.trim();
        if (count) {
            count.hidden = length < 900;
            count.textContent = (1200 - length) + " characters left";
        }
    }

    function ask(text) {
        if (!text || pending) return;
        pending = true;
        send.disabled = true;
        input.value = "";
        fitInput();
        syncComposer();
        if (prompts) prompts.hidden = true;
        log.classList.add("is-thread");
        addRow("user").textContent = text;
        history.push({ role: "user", content: text });
        var waiting = addRow("bot");
        waiting.classList.add("nx-ask-pending");
        waiting.setAttribute("aria-label", "ASK AI is writing");
        waiting.innerHTML = '<span class="nx-ask-dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="nx-ask-sr">Writing a reply</span>';
        form.setAttribute("aria-busy", "true");

        fetch(root.getAttribute("data-endpoint"), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": root.getAttribute("data-csrf") || ""
            },
            body: JSON.stringify({ messages: history.slice(-8) })
        }).then(function (response) {
            return response.json().then(function (body) {
                return { ok: response.ok, body: body };
            });
        }).then(function (result) {
            var reply = result.body && result.body.reply;
            if (!result.ok || !reply) {
                showError(waiting, (result.body && result.body.error) || "ASK AI could not answer just now.", text);
                history.pop();
                return;
            }
            showAnswer(waiting, reply);
            history.push({ role: "assistant", content: reply });
        }).catch(function () {
            showError(waiting, "ASK AI could not answer just now. Please try again.", text);
            history.pop();
        }).finally(function () {
            pending = false;
            form.removeAttribute("aria-busy");
            syncComposer();
            scrollLog();
            input.focus();
        });
    }

    openButton.addEventListener("click", function () {
        setOpen(panel.hidden);
    });

    Array.prototype.forEach.call(root.querySelectorAll("[data-ask-close]"), function (button) {
        button.addEventListener("click", function () { setOpen(false); });
    });

    root.querySelector("[data-ask-reset]").addEventListener("click", function () {
        if (pending) return;
        history = [];
        showWelcome();
        input.focus();
    });

    Array.prototype.forEach.call(root.querySelectorAll("[data-ask-prompt]"), function (button) {
        button.addEventListener("click", function () {
            input.value = button.textContent;
            fitInput();
            ask(button.textContent.trim());
        });
    });

    document.addEventListener("keydown", function (event) {
        if (panel.hidden) return;
        if (event.key === "Escape") {
            event.preventDefault();
            setOpen(false);
            return;
        }
        if (event.key !== "Tab") return;
        var items = focusable();
        if (!items.length) return;
        var first = items[0];
        var last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });

    input.addEventListener("input", function () {
        fitInput();
        syncComposer();
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            ask(input.value.trim());
        }
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        ask(input.value.trim());
    });

    if (window.location.hash === "#ask-ai") setOpen(true);
    syncComposer();
})();
