document.addEventListener("DOMContentLoaded", function () {
    var menu = document.getElementById("nxMenu");
    var app = document.getElementById("nxApp");
    var search = document.getElementById("nxSearch");
    var drawer = document.getElementById("adminNav");
    var desktop = window.matchMedia("(min-width: 768px)");

    function collapsed() {
        return document.documentElement.classList.contains("nx-collapsed");
    }

    function setCollapsed(next) {
        document.documentElement.classList.toggle("nx-collapsed", next);
        if (app) app.classList.toggle("is-collapsed", next);
        if (menu) menu.setAttribute("aria-expanded", next ? "false" : "true");
        document.querySelectorAll("aside.nx-side .nav-link").forEach(function (link) {
            if (next) link.setAttribute("title", link.textContent.replace(/\s+/g, " ").trim());
            else link.removeAttribute("title");
        });
        try {
            localStorage.setItem("nx-side", next ? "collapsed" : "open");
        } catch (e) {}
    }

    if (collapsed()) setCollapsed(true);

    if (menu && app && window.bootstrap) {
        menu.addEventListener("click", function () {
            if (!desktop.matches && drawer) {
                window.bootstrap.Offcanvas.getOrCreateInstance(drawer).toggle();
                return;
            }
            setCollapsed(!collapsed());
        });
    }

    if (drawer) {
        drawer.querySelectorAll("a.nav-link").forEach(function (link) {
            link.addEventListener("click", function () {
                if (desktop.matches) return;
                var instance = window.bootstrap && window.bootstrap.Offcanvas.getInstance(drawer);
                if (instance) instance.hide();
            });
        });
    }

    var current = document.querySelector("aside.nx-side .nav-link.active");
    if (current && current.scrollIntoView) current.scrollIntoView({ block: "nearest" });

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.confirm(form.getAttribute("data-confirm"))) event.preventDefault();
        });
    });

    if (search) {
        var shortcut = search.parentElement && search.parentElement.querySelector("kbd");
        var platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
        if (shortcut && !/mac/i.test(platform)) shortcut.textContent = "Ctrl K";
        document.addEventListener("keydown", function (event) {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                search.focus();
            }
        });
    }
});
