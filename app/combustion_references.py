"""Curated NASA bibliography; linked context, not ingested measurement data."""

REFERENCES = [
    {
        "id": "20210011385", "title": "Burning and Suppression of Solids–II (BASS-II) Summary Report",
        "document_type": "NASA Technical Memorandum", "date": "2021-10-01",
        "authors": "Sandra L. Olson and colleagues", "topics": ["bass_ii"],
        "url": "https://ntrs.nasa.gov/citations/20210011385",
        "scope_en": "Describes BASS-II apparatus, ventilation, fuel variables, and pre/post gas readings.",
        "scope_ar": "يصف أجهزة BASS-II والتهوية ومتغيرات الوقود وقراءات الغاز قبل الاختبار وبعده.",
        "limit_en": "Research context and report findings; do not assume every result applies to the selected table row.",
        "limit_ar": "سياق ونتائج التقرير؛ لا يُفترض أن كل نتيجة تنطبق على صف الجدول المحدد."
    },
    {
        "id": "20210015913", "title": "Advanced Combustion via Microgravity Experiments (ACME) on the International Space Station (ISS)",
        "document_type": "NASA conference poster", "date": None, "authors": "Dennis Stocker",
        "topics": ["flame_design", "cool_flames"],
        "url": "https://ntrs.nasa.gov/citations/20210015913",
        "scope_en": "Describes the goals and hardware of the ACME gas-flame investigations.",
        "scope_ar": "يعرض أهداف وأجهزة دراسات ACME للهب الغازي.",
        "limit_en": "Project-level poster; not a calibration certificate or a row-specific measurement.",
        "limit_ar": "ملصق على مستوى المشروع؛ ليس شهادة معايرة ولا قياساً خاصاً بصف معين."
    },
    {
        "id": "20220015583", "title": "ACME: Advanced Combustion via Microgravity Experiments",
        "document_type": "NASA conference poster", "date": None, "authors": "Dennis P. Stocker",
        "topics": ["flame_design", "cool_flames"],
        "url": "https://ntrs.nasa.gov/citations/20220015583",
        "scope_en": "Summarizes six ACME investigations and their differing burner configurations.",
        "scope_ar": "يلخّص ست دراسات ACME واختلاف تصاميم المواقد المستخدمة فيها.",
        "limit_en": "Program overview, not evidence that experiments had equivalent test conditions.",
        "limit_ar": "نظرة عامة على البرنامج، وليست دليلاً على تطابق ظروف التجارب."
    },
    {
        "id": "20250001364", "title": "Fire and Flame Research in the International Space Station’s Combustion Integrated Rack",
        "document_type": "NASA conference abstract", "date": None, "authors": "Dennis P. Stocker",
        "topics": ["flame_design", "cool_flames"],
        "url": "https://ntrs.nasa.gov/citations/20250001364",
        "scope_en": "Context on gas, droplet and solid-fuel combustion research in the ISS Combustion Integrated Rack.",
        "scope_ar": "سياق لأبحاث احتراق الغازات والقطرات والمواد الصلبة في رف الاحتراق بالمحطة الفضائية.",
        "limit_en": "Conference abstract describing multiple investigations; not evidence for a particular selected test.",
        "limit_ar": "ملخص مؤتمر يصف دراسات متعددة؛ لا يمثل دليلاً على اختبار محدد بعينه."
    },
]


def references(topic=""):
    if topic and topic not in {"bass_ii", "flame_design", "cool_flames"}:
        raise ValueError("Unknown research topic")
    return [dict(item) for item in REFERENCES if not topic or topic in item["topics"]]
