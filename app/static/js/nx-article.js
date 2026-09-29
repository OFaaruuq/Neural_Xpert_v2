(function () {
    var button = document.querySelector(".nx-copy");
    if (button) {
        button.addEventListener("click", function () {
            var url = button.getAttribute("data-url") || window.location.href;
            var done = function () {
                button.textContent = "Link copied";
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url).then(done);
            } else {
                done();
            }
        });
    }

    var links = Array.prototype.slice.call(document.querySelectorAll(".nx-toc a"));
    if (!links.length || !("IntersectionObserver" in window)) {
        return;
    }
    var sections = links.map(function (link) {
        return document.getElementById(link.getAttribute("href").slice(1));
    }).filter(Boolean);
    var setCurrent = function (id) {
        links.forEach(function (link) {
            link.classList.toggle("is-current", link.getAttribute("href") === "#" + id);
        });
    };
    links.forEach(function (link) {
        link.addEventListener("click", function () {
            setCurrent(link.getAttribute("href").slice(1));
        });
    });
    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                setCurrent(entry.target.id);
            }
        });
    }, { rootMargin: "-100px 0px -60% 0px", threshold: 0.1 });
    sections.forEach(function (section) {
        observer.observe(section);
    });
})();
