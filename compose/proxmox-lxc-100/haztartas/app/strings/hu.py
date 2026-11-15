"""Every user-facing string. One language ships; a second is translation."""

S = {
    "app_name": "Háztartás",
    "login_title": "Bejelentkezés",
    "login_user": "Felhasználónév",
    "login_password": "Jelszó",
    "login_submit": "Belépés",
    "login_failed": "Hibás felhasználónév vagy jelszó.",
    "login_locked": "A fiók ideiglenesen zárolva. Próbáld újra 15 perc múlva.",
    "logout": "Kilépés",

    "menu": "Menü",
    "month_nav": "Hónap választása",
    "month_prev": "Előző hónap",
    "month_next": "Következő hónap",
    "nav_entries": "Tételek",
    "nav_drafts": "Tervezetek",
    "nav_pocket": "Zsebpénz",
    "nav_settings": "Beállítások",

    "statement_left": "{month_in} ennyi maradt:",
    "statement_over": "{month_in} ennyivel több ment el, mint amennyi bejött:",
    "expected_prefix": "Még várható:",
    "child_statement": "A zsebpénzedből ennyi van:",
    "map_title_adult": "Hova ment a pénz",
    "map_title_child": "Mire költötted",
    "see_entries": "Tételek",
    "of_limit": "/ {limit} keret",
    "over_limit": "+{amount} felett",
    "map_legend": "A csempe alján lévő sáv a havi keretet mutatja.",
    "by_author": "Ki mennyit költött",
    "child_recent": "Legutóbbi tételeid",

    "capture_photo": "Fotó",
    "capture_voice": "Hang",
    "capture_manual": "Kézi",
    "soon": "hamarosan",
    "queue_pending": "{n} tétel vár feltöltésre",
}


# Month names for the stepper and the statement sentence ("Novemberben ...").
# Index 0 is January. Kept out of S because they are lists, not strings.
MONTHS = ["január", "február", "március", "április", "május", "június",
          "július", "augusztus", "szeptember", "október", "november", "december"]
MONTHS_IN = ["Januárban", "Februárban", "Márciusban", "Áprilisban", "Májusban",
             "Júniusban", "Júliusban", "Augusztusban", "Szeptemberben",
             "Októberben", "Novemberben", "Decemberben"]
