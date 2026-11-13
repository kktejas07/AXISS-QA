"""Ready-made starting points: scan presets and test-case packs. Fixed content, the same for every organisation."""
from __future__ import annotations

SCAN_PRESETS = [
    {"id": "quick-security", "name": "Quick security pass", "about": "A fast look for the most common weaknesses. Good before a demo.",
     "outputs": ["security"], "depth": "quick", "for": ["web", "repo", "code", "api"]},
    {"id": "pre-release", "name": "Pre-release check", "about": "Security findings plus manual test cases at standard depth. Run it before every release.",
     "outputs": ["security", "manual"], "depth": "standard", "for": ["web", "repo", "code", "api", "android", "ios"]},
    {"id": "full-audit", "name": "Full audit", "about": "Everything Wiseflow can produce for this app, at the deepest setting. Takes longest.",
     "outputs": ["security", "manual", "playwright", "appium"], "depth": "deep", "for": ["web", "android", "ios", "repo", "code"]},
    {"id": "automation", "name": "Automation starter", "about": "Test cases and ready-to-run scripts, without the security checks.",
     "outputs": ["manual", "playwright", "appium"], "depth": "standard", "for": ["web", "android", "ios"]},
]


def _case(title: str, steps: list[str], expected: str, priority: str = "High", category: str = "Functional") -> dict:
    return {"title": title, "steps": steps, "expected_result": expected, "priority": priority, "category": category}


TEST_PACKS = [
    {"id": "login", "name": "Sign-in", "about": "Signing in, signing out, wrong details and lockouts.", "cases": [
        _case("Sign in with a valid email and password", ["Open the sign-in page", "Enter a valid email and password", "Submit"], "The person lands on their home screen and stays signed in after a reload."),
        _case("Wrong password is refused without saying which part was wrong", ["Enter a valid email and a wrong password", "Submit"], "A single message says the details do not match. It does not reveal whether the email exists.", "High", "Security"),
        _case("Repeated wrong passwords are slowed down", ["Submit a wrong password ten times in a row"], "Further attempts are delayed or blocked for a while, and the account owner can still recover access.", "High", "Security"),
        _case("Signing out ends the session everywhere it should", ["Sign in", "Sign out", "Press the browser's Back button"], "Protected pages are not shown; the sign-in page is.", "Medium", "Security"),
        _case("Password field hides what is typed and allows paste", ["Type in the password field", "Paste a password from a password manager"], "Characters are hidden and pasting works.", "Low", "Usability"),
    ]},
    {"id": "signup", "name": "Sign-up", "about": "Creating an account, email checks and duplicates.", "cases": [
        _case("Create an account with valid details", ["Open sign-up", "Enter a name, a new email and a strong password", "Submit"], "The account is created and the person is told what happens next."),
        _case("An email already in use is refused", ["Sign up with an email that already has an account"], "The form explains the address is taken and offers sign-in or password reset.", "High", "Negative"),
        _case("Weak passwords are refused with the rule shown", ["Enter a password shorter than the minimum"], "The form says what a valid password needs before submitting.", "Medium", "Negative"),
        _case("Email format is checked", ["Enter 'name@' as the email", "Submit"], "The form points at the email field and explains the problem.", "Medium", "Negative"),
    ]},
    {"id": "payments", "name": "Payments and checkout", "about": "Paying, declined cards, double clicks and refunds.", "cases": [
        _case("Pay with a valid card", ["Add an item to the basket", "Check out with a valid test card"], "The order is confirmed once, the amount is right, and a receipt is sent."),
        _case("A declined card leaves no order behind", ["Check out with a card that is declined"], "The person sees why, can try another card, and no order or charge exists.", "High", "Negative"),
        _case("Pressing Pay twice charges once", ["Press Pay twice quickly"], "Exactly one charge and one order are created.", "High", "Negative"),
        _case("The price cannot be changed from the browser", ["Change the amount in the request sent at checkout"], "The server uses its own price and refuses or ignores the changed one.", "High", "Security"),
        _case("A refund returns the right amount", ["Refund a paid order in full"], "The customer is refunded the full amount once and the order shows as refunded.", "Medium", "Functional"),
    ]},
    {"id": "search", "name": "Search and lists", "about": "Finding things, empty results, paging and odd input.", "cases": [
        _case("A known item is found", ["Search for the exact name of an item that exists"], "The item is in the first results."),
        _case("No results is explained", ["Search for text that matches nothing"], "The page says nothing matched and suggests what to try.", "Medium", "Usability"),
        _case("Special characters do not break search", ["Search for: ' \" < > % ; --"], "The page shows normal results or none. Nothing is run or shown as markup.", "High", "Security"),
        _case("Paging keeps the search", ["Search, then go to page 2"], "Page 2 shows more results for the same search.", "Medium", "Functional"),
    ]},
    {"id": "uploads", "name": "File upload", "about": "Allowed types, size limits and unsafe files.", "cases": [
        _case("An allowed file uploads and can be opened again", ["Upload a file of an allowed type within the size limit"], "The upload finishes, and the file opens unchanged."),
        _case("A file over the size limit is refused before it uploads fully", ["Upload a file larger than the limit"], "The person is told the limit; nothing is stored.", "Medium", "Negative"),
        _case("A disguised file type is refused", ["Rename a script to .png and upload it"], "The upload is refused, or the file is stored without ever being run or served as a page.", "High", "Security"),
        _case("File names cannot escape the upload folder", ["Upload a file named ../../test.txt"], "The file is stored under a safe name inside the upload area.", "High", "Security"),
    ]},
    {"id": "accessibility", "name": "Accessibility basics", "about": "Keyboard use, labels, contrast and zoom.", "cases": [
        _case("Everything works with the keyboard alone", ["Put the mouse aside", "Use Tab, Shift+Tab, Enter and Space to complete the main task"], "Every control can be reached and used, and the focused control is always visible.", "High", "Accessibility"),
        _case("Form fields have labels a screen reader announces", ["Move through a form with a screen reader"], "Each field is announced with its name, and errors are announced when they appear.", "High", "Accessibility"),
        _case("Text is readable at 200% zoom", ["Zoom the browser to 200%"], "No text is cut off and the page does not scroll sideways.", "Medium", "Accessibility"),
        _case("Meaning is not carried by colour alone", ["Look at errors, statuses and charts in greyscale"], "Each is still understandable from text or shape.", "Medium", "Accessibility"),
    ]},
]
for _pack in TEST_PACKS:
    for _i, _c in enumerate(_pack["cases"], 1):
        _c["id"] = f"{_pack['id'].upper()[:4]}-{_i:02d}"


def pack(pack_id: str) -> dict | None:
    return next((p for p in TEST_PACKS if p["id"] == pack_id), None)
