const fullNameInput = document.getElementById("name");
const registrationForm = fullNameInput?.form;
const fullNameFeedback = document.getElementById("name-help");
const usernameInput = document.getElementById("username");
const usernameFeedback = document.getElementById("username-help");
const emailInput = document.getElementById("email");
const emailFeedback = document.getElementById("email-help");
const emailCustomConfirmed = document.getElementById("email-custom-confirmed");
const passwordInput = document.getElementById("password");
const passwordFeedback = document.getElementById("password-help");
const confirmPasswordInput = document.getElementById("confirm_password");
const confirmPasswordFeedback = document.getElementById("confirm-password-help");

function blockSpaces(input, feedback, message) {
    function showSpaceMessage() {
        feedback.textContent = message;
        input.setAttribute("aria-invalid", "true");
    }

    // Stop a space key or other typed whitespace before it appears in the field.
    input.addEventListener("keydown", (event) => {
        if (event.key === " ") {
            event.preventDefault();
            showSpaceMessage();
        }
    });

    // Also stop whitespace inserted by mobile keyboards or other input methods.
    input.addEventListener("beforeinput", (event) => {
        if (event.data && /\s/.test(event.data)) {
            event.preventDefault();
            showSpaceMessage();
        }
    });

    // Reject pasted text with spaces so they cannot bypass the typing check.
    input.addEventListener("paste", (event) => {
        const pastedText = event.clipboardData.getData("text");
        if (/\s/.test(pastedText)) {
            event.preventDefault();
            showSpaceMessage();
        }
    });

    // Clear the space warning once the field contains no whitespace.
    input.addEventListener("input", () => {
        if (!/\s/.test(input.value)) {
            feedback.textContent = "";
            input.setAttribute("aria-invalid", "false");
        }
    });
}

if (passwordInput && passwordFeedback) {
    blockSpaces(passwordInput, passwordFeedback, "Spaces aren't allowed in passwords.");
}

if (confirmPasswordInput && confirmPasswordFeedback) {
    blockSpaces(confirmPasswordInput, confirmPasswordFeedback, "Spaces aren't allowed in passwords.");
}

if (fullNameInput && registrationForm && fullNameFeedback) {
    const nameSuffixes = ["sr.", "jr.", "ii", "iii", "iv", "v", "vi"];

    // Unicode letter checks also allow accented letters in names.
    function containsOnlyLetters(text) {
        return /^\p{L}+$/u.test(text);
    }

    function isMiddleInitial(text) {
        return /^\p{L}\.$/u.test(text);
    }

    function hasFirstAndLastName(value) {
        const parts = value.split(" ");
        const lastPart = parts[parts.length - 1].toLowerCase();

        // Remove a suffix so it is not mistaken for the person's last name.
        if (nameSuffixes.includes(lastPart)) {
            parts.pop();
        }

        if (parts.length < 2) {
            return false;
        }

        if (!containsOnlyLetters(parts[0]) || !containsOnlyLetters(parts[parts.length - 1])) {
            return false;
        }

        // Any parts between the first and last name must be names or initials.
        for (let index = 1; index < parts.length - 1; index += 1) {
            if (!containsOnlyLetters(parts[index]) && !isMiddleInitial(parts[index])) {
                return false;
            }
        }

        return true;
    }

    function cleanNameSpacing(trimEnd = false) {
        const oldValue = fullNameInput.value;
        // Remember where the typing cursor is so it stays in the right place after cleanup.
        const cursorBeforeCleaning = fullNameInput.selectionStart;
        const oldCursor = cursorBeforeCleaning === null ? oldValue.length : cursorBeforeCleaning;
        const textBeforeCursor = oldValue.slice(0, oldCursor)
            .replace(/^ +/, "")
            .replace(/ {2,}/g, " ");
        let newValue = oldValue.replace(/^ +/, "").replace(/ {2,}/g, " ");

        if (trimEnd) {
            newValue = newValue.trimEnd();
        }

        if (newValue !== oldValue) {
            fullNameInput.value = newValue;
            const newCursor = Math.min(textBeforeCursor.length, newValue.length);
            // Move the cursor back to its adjusted position.
            fullNameInput.setSelectionRange(newCursor, newCursor);
        }
    }

    function getNameError(value, checkCompleteName = false) {
        if (value.length > 50) {
            return "A full name can't be longer than 50 characters.";
        }

        if (/\p{N}/u.test(value)) {
            return "Numbers are not allowed.";
        }

        if (/[^\p{L} .]/u.test(value)) {
            return "Special characters are not allowed.";
        }

        if (value.startsWith(" ")) {
            return "A full name can't start with a space.";
        }

        if (value.includes("  ")) {
            return "Use only one space between name parts.";
        }

        if (value.includes(".")) {
            const parts = value.split(" ");
            const lastPart = parts[parts.length - 1].toLowerCase();

            for (let index = 0; index < parts.length; index += 1) {
                if (!parts[index].includes(".")) {
                    continue;
                }

                const isMiddleInitial = index > 0 && /^\p{L}\.$/u.test(parts[index]);
                const isSuffix = index === parts.length - 1 && ["jr.", "sr."].includes(lastPart);
                if (!isMiddleInitial && !isSuffix) {
                    return "A period is only allowed after a middle initial or in suffix.";
                }
            }
        }

        if (checkCompleteName && value && !hasFirstAndLastName(value)) {
            return "Enter a correct full name.";
        }

        const currentParts = value.trimEnd().split(" ");
        const hasTwoParts = currentParts.length >= 2 && currentParts.every(Boolean);
        if (value && (checkCompleteName || hasTwoParts)) {
            const parts = currentParts;
            if (nameSuffixes.includes(parts[parts.length - 1].toLowerCase())) {
                parts.pop();
            }

            const letterCount = (parts.join("").match(/\p{L}/gu) || []).length;
            if (letterCount < 6) {
                return "A full name must contain at least six letters.";
            }
        }

        return "";
    }

    function showNameError(checkCompleteName = false) {
        const message = getNameError(fullNameInput.value, checkCompleteName);
        fullNameFeedback.textContent = message;
        fullNameInput.setAttribute("aria-invalid", message ? "true" : "false");
        return message;
    }

    // Remove spaces at the beginning and collapse repeated spaces as the user types or pastes.
    fullNameInput.addEventListener("input", () => {
        cleanNameSpacing();
        showNameError();
    });

    // A space at the end may become the separator before another name part, so trim it
    // when the user leaves the field or submits the form.
    fullNameInput.addEventListener("blur", () => {
        cleanNameSpacing(true);
        showNameError(true);
    });

    registrationForm.addEventListener("submit", (event) => {
        cleanNameSpacing(true);
        if (showNameError(true)) {
            event.preventDefault();
            fullNameInput.focus();
        }
    });
}

if (usernameInput && usernameFeedback) {
    blockSpaces(usernameInput, usernameFeedback, "Spaces aren't allowed in a username.");

    function showUsernameError() {
        const username = usernameInput.value;
        let message = "";

        if (/\s/.test(username)) {
            message = "Spaces aren't allowed in a username.";
        } else if (/[^A-Za-z0-9_.]/.test(username)) {
            message = "Use only letters, numbers, underscores (_), or periods (.).";
        } else if (username.length > 0 && username.length < 3) {
            message = "A username must contain at least 3 characters.";
        } else if (username.length > 20) {
            message = "A username can't be longer than 20 characters.";
        }

        usernameFeedback.textContent = message;
        usernameInput.setAttribute("aria-invalid", message ? "true" : "false");
        return message;
    }

    usernameInput.addEventListener("input", showUsernameError);
    usernameInput.addEventListener("blur", showUsernameError);
}

if (emailInput && emailFeedback) {
    blockSpaces(emailInput, emailFeedback, "Spaces aren't allowed in an email address.");

    let emailCheckTimer;
    let emailCheckNumber = 0;
    let confirmedEmail = "";

    function showEmailSuggestion(suggestedEmail) {
        emailFeedback.textContent = `Did you mean ${suggestedEmail}? `;

        const useSuggestionButton = document.createElement("button");
        useSuggestionButton.type = "button";
        useSuggestionButton.className = "btn btn-link btn-sm p-0";
        useSuggestionButton.textContent = "Use suggestion";
        useSuggestionButton.addEventListener("click", () => {
            emailInput.value = suggestedEmail;
            emailInput.dispatchEvent(new Event("input", { bubbles: true }));
            emailInput.focus();
        });

        const keepAddressButton = document.createElement("button");
        keepAddressButton.type = "button";
        keepAddressButton.className = "btn btn-link btn-sm p-0";
        keepAddressButton.textContent = "Keep my address";
        keepAddressButton.addEventListener("click", () => {
            emailCustomConfirmed.value = "yes";
            confirmedEmail = emailInput.value;
            emailFeedback.textContent = "Okay, we'll keep this address. Make sure it is correct.";
            emailInput.setAttribute("aria-invalid", "false");
        });

        emailFeedback.append(useSuggestionButton, document.createTextNode(" or "), keepAddressButton);
        emailInput.setAttribute("aria-invalid", "true");
    }

    function showEmailError() {
        // A newer check makes any older response out of date.
        emailCheckNumber += 1;
        const thisCheckNumber = emailCheckNumber;
        clearTimeout(emailCheckTimer);

        if (emailCustomConfirmed.value === "yes" && confirmedEmail === emailInput.value) {
            emailFeedback.textContent = "Okay, we'll keep this address. Make sure it is correct.";
            emailInput.setAttribute("aria-invalid", "false");
            return;
        }

        const hasSpaces = /\s/.test(emailInput.value);
        let message = "";

        if (hasSpaces) {
            message = "Spaces aren't allowed in an email address.";
        } else if (emailInput.value.length > 254) {
            message = "An email address can't be longer than 254 characters.";
        } else if (emailInput.value && emailInput.validity.typeMismatch) {
            message = "Enter a valid email address, such as name@example.com.";
        }

        if (message || !emailInput.value) {
            emailFeedback.textContent = message;
            emailInput.setAttribute("aria-invalid", message ? "true" : "false");
            return;
        }

        // Wait briefly so the app does not check the domain after every keystroke.
        emailFeedback.textContent = "Checking whether this email domain can receive mail…";
        emailInput.setAttribute("aria-invalid", "false");

        emailCheckTimer = setTimeout(async () => {
            try {
                const response = await fetch(emailInput.dataset.checkUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: emailInput.value }),
                });

                if (!response.ok) {
                    throw new Error("Email check failed.");
                }

                const result = await response.json();

                // Ignore the result if the user has changed the email since this check began.
                if (thisCheckNumber !== emailCheckNumber) {
                    return;
                }

                if (result.suggestion) {
                    showEmailSuggestion(result.suggestion);
                    return;
                }

                const domainError = result.valid
                    ? ""
                    : "This email domain can't receive mail. Check the spelling.";
                emailFeedback.textContent = domainError;
                emailInput.setAttribute("aria-invalid", domainError ? "true" : "false");
            } catch (error) {
                if (thisCheckNumber === emailCheckNumber) {
                    emailFeedback.textContent = "The domain couldn't be checked now. It will be checked again when you register.";
                    emailInput.setAttribute("aria-invalid", "false");
                }
            }
        }, 700);
    }

    emailInput.addEventListener("input", () => {
        emailCustomConfirmed.value = "";
        confirmedEmail = "";
        showEmailError();
    });
    emailInput.addEventListener("blur", showEmailError);
    showEmailError();
}
