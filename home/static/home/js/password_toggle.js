(function () {
    function addPasswordToggles() {
        document.querySelectorAll('input[type="password"]').forEach((input) => {
            if (input.parentElement.classList.contains('password-toggle-wrapper')) {
                return;
            }

            const wrapper = document.createElement('span');
            wrapper.className = 'password-toggle-wrapper';
            wrapper.style.marginBottom = window.getComputedStyle(input).marginBottom;
            input.parentElement.insertBefore(wrapper, input);
            wrapper.appendChild(input);

            const button = document.createElement('button');
            button.className = 'password-toggle';
            button.type = 'button';
            button.setAttribute('aria-label', 'Show password');
            button.setAttribute('aria-pressed', 'false');
            button.title = 'Show password';
            button.innerHTML =
                '<svg viewBox="0 0 24 24" aria-hidden="true">' +
                '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"></path>' +
                '<circle cx="12" cy="12" r="3"></circle>' +
                '</svg>';
            wrapper.appendChild(button);

            button.addEventListener('click', () => {
                const isVisible = input.type === 'text';
                input.type = isVisible ? 'password' : 'text';
                button.setAttribute('aria-pressed', String(!isVisible));
                button.setAttribute('aria-label', isVisible ? 'Show password' : 'Hide password');
                button.title = isVisible ? 'Show password' : 'Hide password';
                button.innerHTML = isVisible
                    ? '<svg viewBox="0 0 24 24" aria-hidden="true">' +
                      '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"></path>' +
                      '<circle cx="12" cy="12" r="3"></circle>' +
                      '</svg>'
                    : '<svg viewBox="0 0 24 24" aria-hidden="true">' +
                      '<path d="M3 3l18 18"></path>' +
                      '<path d="M10.6 5.2A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a15.7 15.7 0 0 1-3.1 3.9"></path>' +
                      '<path d="M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7a10.7 10.7 0 0 0 4.1-.8"></path>' +
                      '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"></path>' +
                      '</svg>';
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addPasswordToggles);
    } else {
        addPasswordToggles();
    }
})();
