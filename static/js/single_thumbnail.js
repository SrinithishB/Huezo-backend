document.addEventListener("DOMContentLoaded", function () {
    // Listen for changes on is_thumbnail checkboxes
    document.addEventListener("change", function (event) {
        const target = event.target;
        if (target && target.type === "checkbox" && target.name && target.name.endsWith("-is_thumbnail")) {
            if (target.checked) {
                // Uncheck all other is_thumbnail checkboxes in the same page
                const checkboxes = document.querySelectorAll('input[type="checkbox"][name$="-is_thumbnail"]');
                checkboxes.forEach(function (cb) {
                    if (cb !== target) {
                        cb.checked = false;
                    }
                });
            }
        }
    });
});
