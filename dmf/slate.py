"""Pre-verified episode slate (§11) plus topic rotation.

Episode 11 (mountains) is the queued episode from MASTER_PROMPT.md §11. Each
record is a complete, fact-checked package: five sentences, five scenes, and an
accuracy table that the operator can defend in the comments.
"""

from __future__ import annotations

from typing import Any

VERIFIED_SLATE: list[dict[str, Any]] = [
    {
        "ep": 0,
        "slug": "sample-your-hair-grows-seven-hundred-kilometres",
        "series": "Cost Of One",
        "title": "Your hair grows seven hundred kilometres in a lifetime",
        "alt_titles": [
            "Nine kilometres of hair a year, from one hundred thousand follicles",
            "One strand of hair covers nine metres before you are done",   # ~9 m = 1 cm x 12 months x 75 years x 80% growth phase
            "Your scalp grows the distance from Delhi to Jaipur almost three times over",
        ],
        "hook_130": "A single follicle adds a centimetre a month, and a hundred thousand of them push out nine kilometres of hair every year.",
        "numbers_summary": "0.3 mm (per day, one follicle) -> 1 cm (per month) -> 3.5 m / 9 m / 9.3 km (ladder) -> 700 km (one lifetime)",
        "pinned_comment": "Run your hand through your hair right now. Everything you just touched is the newest centimetre of a seven hundred kilometre race.",
        "tags": "draw me a fact,cost of one,hair growth,human body facts,biology facts,scale check,science shorts,hand drawn facts,shorts",
        "sample": True,
        "sentences": [
            "The average scalp carries about a hundred thousand follicles, each one pushing out roughly zero point three millimetres of hair every single day.",
            "That works out to about a centimetre each month, which sounds tiny until you remember it never stops until it does.",
            "A fingernail manages three and a half metres in a lifetime, one strand reaches nine, and every follicle on one head adds up to nine kilometres a year.",
            "Over seventy five years that same scalp grows seven hundred kilometres of hair, two and a half times the drive from Delhi to Jaipur.",
            "So your body measures time in millimetres, so subscribe, and tap like.",
        ],
        "scenes": [
            {"icon": "strands", "headline": "A HUNDRED THOUSAND FOLLICLES", "display_number": "0.3 mm", "target_num": 0.3, "unit": "mm/day", "caption": "average growth per follicle, per day"},
            {"icon": "ruler", "headline": "ONE MONTH OF GROWTH", "display_number": "1 cm", "target_num": 1.0, "unit": "cm/month", "caption": "monthly growth, per single strand"},
            {
                "icon": "ladder",
                "headline": "MEASURED IN METRES, THEN KILOMETRES",
                "display_number": "9.3 km",
                "target_num": 9.3,
                "unit": "km",
                "caption": "one scalp, one year of growth",
                "ladder": [
                    {"label": "Fingernail, lifetime", "val": 3.5, "text": "3.5 m"},
                    {"label": "One strand, lifetime", "val": 9.0, "text": "9 m"},
                    {"label": "One scalp, one year", "val": 93.0, "text": "9.3 km"},
                ],
            },
            {
                "icon": "compare",
                "headline": "SEVENTY FIVE YEARS OF HAIR",
                "display_number": "700 km",
                "target_num": 700.0,
                "unit": "km",
                "caption": "every follicle, averaged over a lifetime",
                "compare": {"left_name": "Delhi to Jaipur", "left_val": 281.0, "left_txt": "281 km", "right_name": "75 Years of Hair", "right_val": 700.0, "right_txt": "700 km"},
            },
            {"icon": "strands", "reframe": "YOU MEASURE TIME IN MILLIMETRES", "emphasis_word": "700 KM", "ruler_label": "3.5 m      9.3 km      700 km"},
        ],
        "accuracy_table": [
            {"claim": "Scalp follicle count", "value": "~100,000 (range 90,000-150,000)", "source": "Robbins (2012), Chemical and Physical Behavior of Human Hair"},
            {"claim": "Scalp hair growth rate", "value": "~0.34 mm/day (~1 cm/month)", "source": "American Academy of Dermatology; Robbins 2012"},
            {"claim": "Share of follicles in the growth phase", "value": "~80% (anagen)", "source": "Robbins 2012 hair growth cycle data"},
            {"claim": "Fingernail growth over a lifetime", "value": "~3.5 mm/month, ~3.5 m in 75 years", "source": "American Academy of Dermatology nail growth data"},
            {"claim": "One strand over 75 years", "value": "~9 m (1 cm x 12 x 75 x 0.8)", "source": "Calculated from the AAD growth rate and 80% anagen fraction"},
            {"claim": "Whole scalp, one year", "value": "~9.3 km (100,000 follicles x 0.032 cm/day x 365 x 0.8)", "source": "Calculated from the figures above"},
            {"claim": "Whole scalp over 75 years", "value": "~700 km", "source": "Calculated from the figures above"},
            {"claim": "Delhi to Jaipur road distance", "value": "~281 km", "source": "National Highways Authority of India route data"},
        ],
    },
    {
        "ep": 11,
        "slug": "mountains-10km-limit",
        "series": "Scale Check",
        "title": "Why Earth's mountains stop under 10 kilometres",
        "alt_titles": [
            "Gravity crushes any Earth mountain taller than 10 km",
            "Mount Everest is 8.85 km — Earth's rock limit is 10 km",
            "Why Mars has a 22 km mountain and Earth never could",
        ],
        "hook_130": "Mount Everest stands 8.85 km above sea level, perilously close to the 10 km limit where Earth's own gravity crushes granite.",
        "numbers_summary": "4.2 km (Mauna Kea above sea) -> 8.85 km (Everest) -> 10 km (Earth rock-crush ceiling) -> 22 km (Olympus Mons on Mars)",
        "pinned_comment": "If Earth suddenly had Mars gravity tomorrow, which mountain range would you climb first?",
        "tags": "draw me a fact,scale check,mount everest,olympus mons,earth gravity,geology facts,science shorts,physics scale,hand drawn facts,shorts",
        "sentences": [
            "Mount Everest stops at eight point eight five kilometres high, not because plates stopped pushing, but because granite slowly liquefies at the base under its own weight.",
            "Stack rock any higher on Earth and gravity squeezes the bottom crust outward like putty, capping any dry peak near ten kilometres.",
            "Mauna Kea rises four point two kilometres above the waves, Everest climbs to eight point eight five, and ten kilometres is where bedrock gives way.",
            "Yet on Mars, Olympus Mons towers twenty two kilometres high, purely because Martian gravity pulls with thirty eight percent of Earth's strength.",
            "So Everest is not just a tall peak, it is the heaviest stack our planet refuses to sink, so subscribe, and tap like.",
        ],
        "scenes": [
            {
                "icon": "mountain",
                "headline": "EVEREST'S TRUE CEILING",
                "display_number": "8.85 km",
                "target_num": 8.85,
                "unit": "km",
                "caption": "peak elevation above sea level",
            },
            {
                "icon": "weight_crush",
                "headline": "GRANITE UNDER GRAVITY",
                "display_number": "10 km",
                "target_num": 10.0,
                "unit": "km",
                "caption": "bedrock yield ceiling on Earth",
            },
            {
                "icon": "ladder",
                "headline": "CLIMBING THE CEILING",
                "display_number": "10 km",
                "target_num": 10.0,
                "unit": "km",
                "caption": "height above datum in kilometres",
                "ladder": [
                    {"label": "Mauna Kea (dry)", "val": 4.2, "text": "4.2 km"},
                    {"label": "Mt. Everest", "val": 8.85, "text": "8.85 km"},
                    {"label": "Earth Rock Limit", "val": 10.0, "text": "10 km"},
                ],
            },
            {
                "icon": "compare",
                "headline": "38% GRAVITY ON MARS",
                "display_number": "22 km",
                "target_num": 22.0,
                "unit": "km",
                "caption": "Olympus Mons above Mars datum",
                "compare": {
                    "left_name": "Earth Max",
                    "left_val": 10.0,
                    "left_txt": "10 km",
                    "right_name": "Olympus Mons",
                    "right_val": 22.0,
                    "right_txt": "22 km",
                },
            },
            {
                "icon": "mountain",
                "reframe": "NOT JUST A PEAK — EARTH'S WEIGHT LIMIT",
                "emphasis_word": "WEIGHT LIMIT",
                "ruler_label": "0 km      10 km      22 km",
            },
        ],
        "accuracy_table": [
            {"claim": "Mount Everest official elevation", "value": "8,848.86 m (8.85 km)", "source": "2020 China-Nepal Joint Survey / USGS"},
            {"claim": "Mauna Kea elevation above sea level", "value": "4,207 m (4.2 km)", "source": "USGS Hawaiian Volcano Observatory"},
            {"claim": "Theoretical max mountain height on Earth", "value": "~10 km (isostatic / compressive rock-strength limit)", "source": "Weisskopf (1975), Science 187:605 'Of Atoms, Mountains, and Stars'"},
            {"claim": "Olympus Mons height & Mars surface gravity", "value": "~21.9 km (~22 km) at 0.38 g", "source": "NASA Mars Orbiter Laser Altimeter (MOLA)"},
        ],
    },
    {
        "ep": 12,
        "slug": "fold-paper-42-times-moon",
        "series": "Fold It",
        "title": "42 folds of one sheet of paper reaches the Moon",
        "alt_titles": [
            "How 42 folds turns 0.1 mm of paper into 440,000 km",
            "Exponential thickness: folding one sheet to the Moon",
            "Why 23 folds of paper is already 838 metres tall",
        ],
        "hook_130": "One sheet of printer paper is 0.1 millimetres thick, yet doubling it 42 times stacks past the Moon.",
        "numbers_summary": "0.1 mm (0 folds) -> 10 cm (10 folds) -> 838 m (23 folds) -> 439,800 km (42 folds, past the Moon)",
        "pinned_comment": "How many folds do you think it takes to reach the Sun? (Hint: surprisingly few more.)",
        "tags": "draw me a fact,fold it,paper folding,exponential growth,distance to moon,math shorts,physics scale,hand drawn animation,shorts",
        "sentences": [
            "A fresh sheet of printer paper is zero point one millimetres thick, thin enough to slip under a locked door.",
            "Every time you fold that sheet in half you double every layer beneath your fingers into pure exponential growth.",
            "Ten folds reaches ten centimetres, twenty three folds towers eight hundred and thirty eight metres past the Burj Khalifa, and thirty folds hits one hundred and seven kilometres.",
            "Fold it a forty second time and your single stack stands four hundred and thirty nine thousand eight hundred kilometres tall, well past the Moon.",
            "So the paper never lacked the reach for space, it only refused to bend past fold seven, so subscribe, and tap like.",
        ],
        "scenes": [
            {"icon": "paper", "headline": "ONE PRINTER SHEET", "display_number": "0.1 mm", "target_num": 0.1, "unit": "mm", "caption": "standard 80 gsm sheet thickness"},
            {"icon": "fold_layers", "headline": "DOUBLING EVERY LAYER", "display_number": "10 cm", "target_num": 10.0, "unit": "cm", "caption": "thickness after just 10 folds (1,024 layers)"},
            {
                "icon": "ladder",
                "headline": "THE EXPONENTIAL CLIMB",
                "display_number": "107 km",
                "target_num": 107.0,
                "unit": "km",
                "caption": "stack height by fold count",
                "ladder": [
                    {"label": "14 Folds", "val": 14.0, "text": "1.6 m"},
                    {"label": "23 Folds", "val": 45.0, "text": "838 m"},
                    {"label": "30 Folds", "val": 100.0, "text": "107 km"},
                ],
            },
            {
                "icon": "compare",
                "headline": "FOLD NUMBER FORTY-TWO",
                "display_number": "439,800 km",
                "target_num": 439800.0,
                "unit": "km",
                "caption": "0.1 mm x 2^42 vs the Moon's 384,400 km",
                "compare": {"left_name": "Moon Orbit", "left_val": 384.4, "left_txt": "384,400 km", "right_name": "42 Folds", "right_val": 439.8, "right_txt": "439,800 km"},
            },
            {"icon": "paper", "reframe": "NEVER TOO THIN — JUST EXPONENTIAL", "emphasis_word": "EXPONENTIAL", "ruler_label": "0.1 mm      838 m      439,800 km"},
        ],
        "accuracy_table": [
            {"claim": "Standard copy paper caliper", "value": "0.10 mm (100 micrometres)", "source": "ISO 534 paper thickness standard"},
            {"claim": "Thickness at 10, 23 and 30 folds", "value": "102.4 mm, 838.86 m, 107.37 km", "source": "Exact binary power 0.0001 m x 2^n"},
            {"claim": "Thickness at 42 folds", "value": "439,804.65 km", "source": "0.0001 m x 2^42 = 4.398 x 10^8 m"},
            {"claim": "Mean Earth-Moon distance", "value": "384,400 km", "source": "NASA Lunar Fact Sheet"},
        ],
    },
    {
        "ep": 13,
        "slug": "single-cloud-500-tonnes",
        "series": "Wrong By Default",
        "title": "One white cumulus cloud weighs 500 tonnes",
        "alt_titles": [
            "Why a fluffy summer cloud weighs 500,000 kilograms",
            "How 500 tonnes of water floats above your head",
            "A 1 km cumulus cloud weighs as much as 100 elephants",
        ],
        "hook_130": "One fair-weather cumulus cloud holds half a gram of water per cubic metre, adding up to 500 metric tonnes overhead.",
        "numbers_summary": "0.5 g (per cubic metre) -> 500 kg (stadium box) -> 50 tonnes (a tenth of the cloud) -> 500 tonnes (the whole cloud)",
        "pinned_comment": "Before watching this, what would you have guessed a single white cloud weighed?",
        "tags": "draw me a fact,wrong by default,cloud weight,atmospheric physics,500 tonnes,weather facts,science shorts,shorts",
        "sentences": [
            "One cubic metre of summer cumulus cloud holds just zero point five grams of water, roughly ten small raindrops.",
            "It looks weightless only because that cloud stretches one kilometre wide, long, and tall across a billion cubic metres of sky.",
            "A shipping container fills to twenty five grams, a stadium volume to five hundred kilograms, and one tenth of the cloud already tips fifty tonnes.",
            "Measure the whole cubic kilometre together and five hundred tonnes of liquid water hangs silently overhead, heavier than three jumbo jets.",
            "So a cloud never floats because it is light, it floats because the dry air around it is denser, so subscribe, and tap like.",
        ],
        "scenes": [
            {"icon": "cloud", "headline": "ONE CUBIC METRE OF CLOUD", "display_number": "0.5 g", "target_num": 0.5, "unit": "g", "caption": "liquid water droplets per cubic metre"},
            {"icon": "cube_grid", "headline": "ONE BILLION CUBIC METRES", "display_number": "1 km³", "target_num": 1.0, "unit": "km³", "caption": "typical fair-weather cumulus volume"},
            {
                "icon": "ladder",
                "headline": "ADDING UP THE MIST",
                "display_number": "500 tonnes",
                "target_num": 500.0,
                "unit": "tonnes",
                "caption": "water mass as cloud volume scales",
                "ladder": [
                    {"label": "Container Box", "val": 8.0, "text": "25 g"},
                    {"label": "Stadium Box", "val": 38.0, "text": "500 kg"},
                    {"label": "1/10th Cloud", "val": 90.0, "text": "50 tonnes"},
                ],
            },
            {
                "icon": "compare",
                "headline": "ONE WHOLE CUMULUS CLOUD",
                "display_number": "500 tonnes",
                "target_num": 500.0,
                "unit": "tonnes",
                "caption": "500,000 kg of suspended micro-droplets",
                "compare": {"left_name": "Boeing 747", "left_val": 183.0, "left_txt": "183 t", "right_name": "One Cloud", "right_val": 500.0, "right_txt": "500 t"},
            },
            {"icon": "cloud", "reframe": "NOT LIGHT — JUST SPREAD ACROSS A SKY", "emphasis_word": "500 TONNES", "ruler_label": "0.5 g      500 kg      500 tonnes"},
        ],
        "accuracy_table": [
            {"claim": "Cumulus liquid water content", "value": "~0.5 g/m³", "source": "NOAA / NCAR (Peggy LeMone) in-cloud measurements"},
            {"claim": "Typical fair-weather cumulus dimensions", "value": "~1 km x 1 km x 1 km (10^9 m³)", "source": "USGS Water Science School / NCAR"},
            {"claim": "Total liquid water mass", "value": "5 x 10^8 g = 500,000 kg (500 tonnes)", "source": "NCAR / USGS consensus calculation"},
            {"claim": "Boeing 747 maximum take-off weight", "value": "~183 tonnes (747-400 MTOW)", "source": "Boeing 747-400 Airplane Characteristics for Airport Planning"},
        ],
    },
    {
        "ep": 14,
        "slug": "cotton-tshirt-2700-litres",
        "series": "Cost Of One",
        "title": "One cotton T-shirt takes 2,700 litres of water",
        "alt_titles": [
            "Why there are 2,700 litres of water inside one T-shirt",
            "One 250-gram cotton shirt = 900 days of drinking water",
            "The hidden water ledger inside a single cotton shirt",
        ],
        "hook_130": "A plain cotton T-shirt weighs 250 grams on your shoulders, yet growing and dyeing its fibres took 2,700 litres of water.",
        "numbers_summary": "250 g (shirt mass) -> 200 litres (processing & dyeing) -> 1,200 litres (half the harvest) -> 2,700 litres (total footprint)",
        "pinned_comment": "Look at the shirt you are wearing right now — cotton or polyester?",
        "tags": "draw me a fact,cost of one,water footprint,cotton tshirt,2700 litres,sustainability facts,numbers,shorts",
        "sentences": [
            "A plain white cotton T-shirt weighs two hundred and fifty grams dry, yet almost none of the water that made it stays inside.",
            "Cotton bolls transpire water through sunlit leaves for five straight months long before a spinning mill touches a thread.",
            "Bleaching and dyeing drinks two hundred litres, half the harvest takes twelve hundred, and one finished shirt climbs to two thousand seven hundred litres.",
            "At three litres of drinking water per day, that single folded shirt in your drawer holds nine hundred days of human hydration.",
            "So the tag shows what the cloth cost at the counter, never what the river paid first, so subscribe, and tap like.",
        ],
        "scenes": [
            {"icon": "tshirt", "headline": "ONE DRY COTTON SHIRT", "display_number": "250 g", "target_num": 250.0, "unit": "g", "caption": "finished garment, dry fabric weight"},
            {"icon": "water", "headline": "DYEHOUSE AND MILL WATER", "display_number": "200 L", "target_num": 200.0, "unit": "litres", "caption": "scouring, bleaching and wet processing"},
            {
                "icon": "ladder",
                "headline": "THE WATER LEDGER",
                "display_number": "2,700 L",
                "target_num": 2700.0,
                "unit": "litres",
                "caption": "cumulative virtual water per shirt",
                "ladder": [
                    {"label": "Mill & Dye", "val": 12.0, "text": "200 L"},
                    {"label": "Half Harvest", "val": 50.0, "text": "1,200 L"},
                    {"label": "Full Shirt", "val": 100.0, "text": "2,700 L"},
                ],
            },
            {
                "icon": "compare",
                "headline": "DRINKING WATER EQUIVALENT",
                "display_number": "900 days",
                "target_num": 900.0,
                "unit": "days",
                "caption": "at three litres of drinking water per day",
                "compare": {"left_name": "One Year", "left_val": 365.0, "left_txt": "365 days", "right_name": "One Shirt", "right_val": 900.0, "right_txt": "900 days"},
            },
            {"icon": "tshirt", "reframe": "THE TAG NEVER SHOWS THE RIVER", "emphasis_word": "2,700 LITRES", "ruler_label": "250 g      200 L      2,700 L"},
        ],
        "accuracy_table": [
            {"claim": "Mass of a plain cotton T-shirt", "value": "~250 g", "source": "Textile industry standard, 180-250 gsm jersey"},
            {"claim": "Virtual water of one cotton T-shirt", "value": "~2,700 litres", "source": "Water Footprint Network / UNESCO-IHE Hoekstra & Chapagain"},
            {"claim": "Daily drinking water per person", "value": "~3 litres", "source": "EFSA / IOM adequate intake reference"},
            {"claim": "Share of footprint from cotton cultivation", "value": "~45% of the total", "source": "Water Footprint Network cotton report"},
        ],
    },
]

# Alternate topics used when the slate is exhausted and no LLM key is present.
TOPIC_BANK: list[dict[str, str]] = [
    {"topic": "One tablespoon of soil holds more living organisms than there are people on Earth.",
     "series": "Tiny Machines", "number": "bacteria per gram of soil"},
    {"topic": "A single teaspoon of neutron star material would weigh about six billion tonnes.",
     "series": "Scale Check", "number": "tonnes per teaspoon"},
    {"topic": "One bolt of lightning is roughly five times hotter than the surface of the Sun.",
     "series": "Wrong By Default", "number": "degrees Celsius"},
]


def find_episode(slug_or_number: str | int) -> dict[str, Any] | None:
    key = str(slug_or_number).strip().lower()
    for ep in VERIFIED_SLATE:
        if key in (str(ep["ep"]), ep["slug"].lower()) or key in ep["title"].lower():
            return ep
    return None


def next_from_slate(shipped_slugs: set[str]) -> dict[str, Any] | None:
    """Next real episode to produce. Sample episodes are never auto-selected."""
    for ep in VERIFIED_SLATE:
        if ep.get("sample"):
            continue
        if ep["slug"] not in shipped_slugs:
            return ep
    return None
