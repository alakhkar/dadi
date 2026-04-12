"""
Indian calendar context for Dadi AI.
Provides current season (ritu), Hindu month, and nearby festivals
so Dadi can weave seasonal and cultural references naturally.
"""
from datetime import date


def _get_ritu(month: int) -> str:
    return {
        1:  "Shishir Ritu — winter, misty mornings, bajra roti weather",
        2:  "Shishir Ritu — winter fading, mustard fields blooming",
        3:  "Vasant Ritu — spring, flowers, neem in the air",
        4:  "Vasant Ritu — spring warming into summer, mango season beginning",
        5:  "Grishma Ritu — peak summer, loo winds, raw mango panna weather",
        6:  "Grishma Ritu — blazing heat, clouds building, monsoon any day now",
        7:  "Varsha Ritu — monsoon, petrichor, sawan, everything green",
        8:  "Varsha Ritu — monsoon in full swing, kadhi-chawal weather",
        9:  "Sharad Ritu — post-monsoon, cool evenings, festival season begins",
        10: "Sharad Ritu — autumn, Diwali season, diyas and mithai in the air",
        11: "Hemant Ritu — early winter, sweater weather, fog arriving",
        12: "Hemant Ritu — winter, heaters on, gajar ka halwa season",
    }.get(month, "")


def _get_hindu_month(month: int) -> str:
    return {
        1:  "Paush / Magh",
        2:  "Magh / Phalgun",
        3:  "Phalgun / Chaitra",
        4:  "Chaitra / Vaishakh",
        5:  "Vaishakh / Jyeshtha",
        6:  "Jyeshtha / Ashadha",
        7:  "Ashadha / Shravan",
        8:  "Shravan / Bhadrapad",
        9:  "Bhadrapad / Ashwin",
        10: "Ashwin / Kartik",
        11: "Kartik / Margashirsha",
        12: "Margashirsha / Paush",
    }.get(month, "")


# (year_or_None, month, day, name, flavour_note)
# year=None → recurs every year on that fixed date
_FESTIVALS = [
    # ── Fixed-date national / cultural ───────────────────────────────────────
    (None, 1,  1,  "New Year's Day",       "new beginnings, resolutions, everyone hopeful"),
    (None, 1,  14, "Makar Sankranti",      "harvest festival, kite-flying, til-gur, 'til gul ghya, god god bola'"),
    (None, 1,  26, "Republic Day",         "India's Republic Day, parade in Delhi, national pride"),
    (None, 4,  13, "Baisakhi",             "Punjabi harvest festival, Sikh New Year, bhangra and langar"),
    (None, 8,  15, "Independence Day",     "India's Independence Day, 'Jai Hind', flag hoisting"),
    (None, 10, 2,  "Gandhi Jayanti",       "Bapu's birthday, non-violence, spinning wheel, simplicity"),
    (None, 12, 25, "Christmas",            "carols, cake, Santa, churches lit up"),
    (None, 12, 31, "New Year's Eve",       "the whole family staying up, countdown, memories of the year"),

    # ── 2025 variable festivals ───────────────────────────────────────────────
    (2025, 1,  29, "Vasant Panchami",      "Saraswati Puja, yellow clothes, books and veena worshipped"),
    (2025, 2,  12, "Maghi Purnima",        "holy dip in the Ganga, lamp-lighting"),
    (2025, 2,  26, "Maha Shivaratri",      "fasting, Shiva puja, 'Har Har Mahadev', night jaagran"),
    (2025, 3,  13, "Holika Dahan",         "bonfire night before Holi, burning of evil"),
    (2025, 3,  14, "Holi",                 "festival of colours, gulal, gujiya, thandai, everyone drenched"),
    (2025, 3,  30, "Ugadi / Gudi Padwa",   "Telugu and Marathi New Year, neem-jaggery, new beginnings"),
    (2025, 4,  2,  "Ram Navami",           "Lord Ram's birthday, temple bells, Ram katha, aarti"),
    (2025, 4,  6,  "Mahavir Jayanti",      "birthday of Lord Mahavira, Jain celebration"),
    (2025, 4,  14, "Ambedkar Jayanti",     "Dr. Babasaheb Ambedkar's birthday"),
    (2025, 4,  18, "Good Friday",          "solemn day, churches, fasting"),
    (2025, 4,  20, "Easter",               "resurrection, church gatherings, eggs"),
    (2025, 5,  12, "Buddha Purnima",       "birth, enlightenment and mahaparinirvana of Lord Buddha"),
    (2025, 6,  7,  "Eid ul-Adha / Bakrid", "festival of sacrifice, qurbani, sevai, family gatherings"),
    (2025, 6,  27, "Rath Yatra",           "Lord Jagannath's chariot festival in Puri — massive procession"),
    (2025, 7,  6,  "Muharram",             "Islamic New Year, Ashura"),
    (2025, 7,  10, "Guru Purnima",         "honouring teachers and gurus, reverence for knowledge"),
    (2025, 8,  9,  "Hariyali Teej",        "sawan begins, green everything, swings, women singing"),
    (2025, 8,  16, "Janmashtami",          "Lord Krishna's birthday — dahi handi, midnight celebrations, mathura vibes"),
    (2025, 8,  27, "Ganesh Chaturthi",     "Ganpati Bappa arrives — 10 days of modaks, aarti, celebration"),
    (2025, 9,  5,  "Ganesh Visarjan",      "Bappa's farewell — procession, 'Ganpati Bappa Morya, Pudhchya Varshi Lavkar Ya'"),
    (2025, 9,  22, "Navratri begins",      "nine nights of Mata worship, garba, dandiya, fasting"),
    (2025, 10, 1,  "Navratri ends",        "last night of Navratri"),
    (2025, 10, 2,  "Dussehra",             "victory of Ram over Ravan — burning of Ravan's effigy, jalebi, fair"),
    (2025, 10, 20, "Diwali",               "festival of lights — diyas, lakshmi puja, mithai, patakhe, new clothes"),
    (2025, 10, 21, "Govardhan Puja",       "day after Diwali — Krishna lifted Govardhan, annakut prasad"),
    (2025, 10, 22, "Bhai Dooj",            "celebrating siblings — tilak, gift, love between brothers and sisters"),
    (2025, 10, 28, "Chhath Puja",          "sunrise and sunset worship of Surya Dev, standing in river, thekua"),
    (2025, 11, 5,  "Guru Nanak Jayanti",   "Gurpurab — birthday of Guru Nanak Dev Ji, langar, kirtan"),
    (2025, 11, 15, "Kartik Purnima",       "Dev Deepawali, holy dip, diyas on the Ganga ghats"),
    (2025, 12, 24, "Christmas Eve",        "carols, midnight mass, cakes being cut"),

    # ── 2026 variable festivals ───────────────────────────────────────────────
    (2026, 1,  23, "Vasant Panchami",      "Saraswati Puja, yellow clothes, veena and books worshipped"),
    (2026, 2,  15, "Maha Shivaratri",      "fasting, Shiva puja, night jaagran"),
    (2026, 3,  2,  "Holika Dahan",         "bonfire night before Holi"),
    (2026, 3,  3,  "Holi",                 "festival of colours, gulal, gujiya, thandai"),
    (2026, 3,  19, "Ugadi / Gudi Padwa",   "Telugu and Marathi New Year"),
    (2026, 3,  28, "Ram Navami",           "Lord Ram's birthday"),
    (2026, 5,  1,  "Akshaya Tritiya",      "auspicious day for new beginnings, gold buying, weddings"),
    (2026, 5,  31, "Buddha Purnima",       "birth and enlightenment of Lord Buddha"),
    (2026, 8,  6,  "Janmashtami",          "Lord Krishna's birthday"),
    (2026, 8,  19, "Ganesh Chaturthi",     "Ganpati Bappa arrives"),
    (2026, 10, 9,  "Diwali",               "festival of lights"),
    (2026, 10, 10, "Govardhan Puja",       "day after Diwali"),
    (2026, 10, 11, "Bhai Dooj",            "celebrating the bond between siblings"),
]


def get_calendar_context() -> str:
    today = date.today()
    y, m, d = today.year, today.month, today.day

    day_name   = today.strftime("%A")
    month_name = today.strftime("%B")
    ritu       = _get_ritu(m)
    hindu_month = _get_hindu_month(m)

    today_festivals:  list[tuple[str, str]] = []
    upcoming_festivals: list[tuple[int, str, str]] = []  # (days_away, name, flavour)

    def _check_year(check_year: int):
        for entry in _FESTIVALS:
            yr_filter, fm, fd, name, flavour = entry
            if yr_filter and yr_filter != check_year:
                continue
            try:
                f_date = date(check_year, fm, fd)
            except ValueError:
                continue
            delta = (f_date - today).days
            if delta == 0:
                today_festivals.append((name, flavour))
            elif 1 <= delta <= 21:
                upcoming_festivals.append((delta, name, flavour))

    _check_year(y)
    if m >= 11:  # wrap-around: check January of next year too
        _check_year(y + 1)

    upcoming_festivals.sort(key=lambda x: x[0])

    lines = [
        f"DATE: {day_name}, {d} {month_name} {y}",
        f"SEASON: {ritu}",
        f"HINDU MONTH: {hindu_month}",
    ]

    if today_festivals:
        for name, flavour in today_festivals:
            lines.append(f"TODAY'S FESTIVAL: {name} — {flavour}")

    if upcoming_festivals:
        for days, name, flavour in upcoming_festivals[:3]:
            when = "tomorrow" if days == 1 else f"in {days} days"
            lines.append(f"UPCOMING: {name} {when} — {flavour}")

    return "\n".join(lines)
