import json
import os
import re
from urllib import error, request
from urllib.parse import quote_plus, urlsplit

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from wagtail.models import Page


def _extract_recent_user_query(messages):
    for item in reversed(messages[-12:]):
        if not isinstance(item, dict):
            continue
        if item.get("role") != "user":
            continue

        raw_content = item.get("content")
        if isinstance(raw_content, str):
            content = raw_content.strip()
            if content:
                return content[:200]

    return ""


def _is_placeholder_openai_key(api_key):
    normalized = (api_key or "").strip()
    if not normalized:
        return True

    placeholder_values = {
        "your-key",
        "your_openai_api_key",
        "openai_api_key",
        "changeme",
        "replace-me",
        "replace_with_real_key",
        "sk-your-key",
        "sk-test",
    }
    lowered = normalized.lower()
    return lowered in placeholder_values or "your-key" in lowered


def _build_site_context(query):
    if not query:
        return ""

    try:
        limit = max(1, min(int(os.environ.get("AI_ASSISTANT_SITE_CONTEXT_LIMIT", "5")), 10))
    except ValueError:
        limit = 5

    try:
        pages = Page.objects.live().public().search(query)[:limit]
    except Exception:
        return ""

    chunks = []
    for page in pages:
        title = (getattr(page, "title", "") or "").strip()
        if not title:
            continue

        description = (getattr(page, "search_description", "") or "").strip()
        page_url = (getattr(page, "url", "") or getattr(page, "full_url", "") or "").strip()
        parts = [f"Title: {title}"]
        if description:
            parts.append(f"Summary: {description[:300]}")
        if page_url:
            parts.append(f"URL: {page_url}")

        chunks.append("\n".join(parts))

    if not chunks:
        return ""

    return "\n\n---\n\n".join(chunks)


def _infer_business_focus(page_title, page_context, site_context):
    text = f"{page_title}\n{page_context[:4000]}\n{site_context[:4000]}".lower()

    buckets = [
        (
            ("course", "courses", "class", "lesson", "teacher", "weekday", "报名", "课程", "上课"),
            "课程与培训服务",
        ),
        (
            ("product", "products", "price", "rm ", "shop", "购买", "商品", "产品", "价钱"),
            "产品销售与商品介绍",
        ),
        (
            ("work", "portfolio", "project", "case", "作品", "案例", "项目"),
            "作品集与案例展示",
        ),
        (
            ("about", "company", "brand", "team", "关于", "我们", "品牌"),
            "品牌与公司介绍",
        ),
    ]

    focus = []
    for keywords, label in buckets:
        if any(keyword in text for keyword in keywords):
            focus.append(label)

    if not focus:
        return "未能从页面文本中明确识别业务类型"

    return "、".join(focus[:2])


def _detect_response_language(messages):
    last_user_text = ""
    for item in reversed(messages[-12:]):
        if isinstance(item, dict) and item.get("role") == "user" and isinstance(item.get("content"), str):
            last_user_text = item.get("content").strip().lower()
            if last_user_text:
                break

    if not last_user_text:
        return ("English", "Respond only in English.")

    malay_markers = (
        " saya ",
        " anak ",
        " tahun",
        " berapa",
        " boleh",
        " untuk",
        " kelas",
        " kursus",
        " tak",
        " tidak",
        " mahu",
        " nak ",
    )
    english_markers = (
        "what",
        "how",
        "can i",
        "price",
        "course",
        "product",
        "where",
        "when",
        "why",
    )

    if any(marker in f" {last_user_text} " for marker in malay_markers):
        return ("Bahasa Melayu", "Jawab dalam Bahasa Melayu sahaja.")

    if any("\u4e00" <= ch <= "\u9fff" for ch in last_user_text):
        return ("简体中文", "仅使用简体中文回答。")

    if any(marker in last_user_text for marker in english_markers):
        return ("English", "Respond only in English.")

    return ("English", "Respond only in English.")


def _extract_requested_age(query):
    ages = _extract_requested_ages(query)
    return ages[0] if ages else None


def _extract_requested_ages(query):
    text = (query or "").strip().lower()
    if not text:
        return []

    ages = []
    for match in re.finditer(r"(^|[^\d])(\d{1,2})\s*(?:岁|歲|years?\s*old|yo|y\/o|tahun|umur)?", text):
        age = int(match.group(2))
        if 1 <= age <= 99 and age not in ages:
            ages.append(age)

    zh_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    for zh_match in re.finditer(r"([一二三四五六七八九十]{1,3})\s*[岁歲]", query or ""):
        token = zh_match.group(1)
        value = None
        if token == "十":
            value = 10
        elif token.startswith("十") and len(token) == 2 and token[1] in zh_map:
            value = 10 + zh_map[token[1]]
        elif token.endswith("十") and len(token) == 2 and token[0] in zh_map:
            value = zh_map[token[0]] * 10
        elif "十" in token and len(token) == 3 and token[0] in zh_map and token[2] in zh_map:
            value = zh_map[token[0]] * 10 + zh_map[token[2]]
        elif token in zh_map:
            value = zh_map[token]

        if isinstance(value, int) and 1 <= value <= 99 and value not in ages:
            ages.append(value)

    return ages


def _is_age_query(query):
    text = (query or "").strip().lower()
    if not text:
        return False

    markers = (
        "age",
        "years old",
        "year old",
        "old",
        "岁",
        "歲",
        "几岁",
        "幾歲",
        "年龄",
        "年齡",
        "umur",
        "usia",
        "tahun",
    )
    if any(marker in text for marker in markers):
        return True

    child_markers = ("kid", "kids", "child", "children", "孩子", "小孩", "小朋友", "anak")
    return any(marker in text for marker in child_markers) and bool(re.search(r"\b\d{1,2}\b", text))


def _extract_structured_courses(page_context):
    courses = []
    text = page_context or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for raw_line in (page_context or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("Course:"):
            continue

        course = {}
        for part in line.split("|"):
            segment = part.strip()
            if ":" not in segment:
                continue
            key, value = segment.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                course[key] = value

        if course.get("Course") and course.get("Age"):
            courses.append(course)

    if courses:
        return courses

    # Fallback: parse plain page text blocks (e.g., title + Age/Time/Location lines).
    parsed = []
    for idx, line in enumerate(lines):
        if not line.lower().startswith("age:"):
            continue

        age_value = line.split(":", 1)[1].strip() if ":" in line else ""
        if not age_value:
            continue

        title = ""
        price = ""
        start = max(0, idx - 8)
        for j in range(idx - 1, start - 1, -1):
            prev = lines[j]
            if not price and re.match(r"^rm\s*\d", prev.lower()):
                price = prev
            if ":" not in prev and not re.match(r"^rm\s*\d", prev.lower()) and len(prev) <= 100:
                title = prev
                break

        if not title:
            continue

        course = {"Course": title, "Age": age_value}
        for j in range(max(0, idx - 6), min(len(lines), idx + 7)):
            item = lines[j]
            lower_item = item.lower()
            if lower_item.startswith("location:"):
                course["Location"] = item.split(":", 1)[1].strip()
            elif lower_item.startswith("time:"):
                course["Time"] = item.split(":", 1)[1].strip()
            elif lower_item.startswith("weekday:"):
                course["Weekday"] = item.split(":", 1)[1].strip()
            elif lower_item.startswith("start date:"):
                course["Start Date"] = item.split(":", 1)[1].strip()
            elif lower_item.startswith("type:"):
                course["Type"] = item.split(":", 1)[1].strip()

        if price:
            course["Price"] = price

        key = (course.get("Course", ""), course.get("Age", ""))
        if not any((item.get("Course", ""), item.get("Age", "")) == key for item in parsed):
            parsed.append(course)

    return parsed


def _load_global_courses():
    try:
        from courses.models import CoursePage

        pages = CoursePage.objects.live().public().order_by("-first_published_at")
        items = []
        for page in pages[:30]:
            title = (getattr(page, "title", "") or "").strip()
            age = (getattr(page, "age", "") or "").strip()
            if not title:
                continue

            price = getattr(page, "price", None)
            price_text = f"RM{price:.2f}" if price is not None else ""
            time_text = ""
            start_time = getattr(page, "start_time", None)
            end_time = getattr(page, "end_time", None)
            if start_time and end_time:
                time_text = f"{start_time.strftime('%I:%M %p').lstrip('0')} - {end_time.strftime('%I:%M %p').lstrip('0')}"

            item = {
                "Course": title,
                "Age": age,
                "Location": (getattr(page, "location", "") or "").strip(),
                "Time": time_text,
                "Price": price_text,
                "Weekday": (getattr(page, "get_weekday_display", lambda: "")() or "").strip(),
                "URL": (getattr(page, "full_url", "") or getattr(page, "url", "") or "").strip(),
            }
            items.append(item)

        return items
    except Exception:
        return []


def _get_available_courses(page_context):
    local_courses = _extract_structured_courses(page_context)
    global_courses = _load_global_courses()

    merged = []
    seen = set()
    for course in local_courses + global_courses:
        key = ((course.get("Course", "") or "").strip().lower(), (course.get("Age", "") or "").strip())
        if not key[0] or key in seen:
            continue
        seen.add(key)
        merged.append(course)

    return merged


def _short_page_label(url):
    raw = (url or "").strip()
    if not raw:
        return "-"

    if raw.startswith("/"):
        return raw

    try:
        parsed = urlsplit(raw)
    except Exception:
        return raw

    if parsed.path:
        return parsed.path
    if parsed.netloc:
        return parsed.netloc
    return raw


def _extract_structured_products(page_context):
    products = []
    for raw_line in (page_context or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("Product:"):
            continue

        product = {}
        for part in line.split("|"):
            segment = part.strip()
            if ":" not in segment:
                continue
            key, value = segment.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                product[key] = value

        if product.get("Product"):
            products.append(product)
    return products


def _load_global_products():
    try:
        from portfolio.models import ProductPage

        pages = ProductPage.objects.live().public().order_by("-first_published_at")
        items = []
        for page in pages[:30]:
            title = (getattr(page, "title", "") or "").strip()
            if not title:
                continue
            price = getattr(page, "price", None)
            price_text = f"RM{price:.2f}" if price is not None else ""
            items.append(
                {
                    "Product": title,
                    "Price": price_text,
                    "URL": (getattr(page, "full_url", "") or getattr(page, "url", "") or "").strip(),
                }
            )
        return items
    except Exception:
        return []


def _get_available_products(page_context):
    local_products = _extract_structured_products(page_context)
    global_products = _load_global_products()

    merged = []
    seen = set()
    for product in local_products + global_products:
        key = ((product.get("Product", "") or "").strip().lower(), (product.get("Price", "") or "").strip())
        if not key[0] or key in seen:
            continue
        seen.add(key)
        merged.append(product)
    return merged


def _age_matches_rule(age, age_rule):
    rule = (age_rule or "").strip().lower()
    if not rule or age is None:
        return False

    rule = (
        rule.replace("–", "-")
        .replace("—", "-")
        .replace(" to ", "-")
        .replace("至", "-")
        .replace("到", "-")
    )

    range_match = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})", rule)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        if low > high:
            low, high = high, low
        return low <= age <= high

    plus_match = re.search(r"(\d{1,2})\s*\+", rule)
    if plus_match:
        return age >= int(plus_match.group(1))

    under_match = re.search(r"(?:under|below|<)\s*(\d{1,2})", rule)
    if under_match:
        return age < int(under_match.group(1))

    single_match = re.search(r"\b(\d{1,2})\b", rule)
    if single_match:
        return age == int(single_match.group(1))

    return False


def _build_age_match_hint(messages, page_context):
    query = _extract_recent_user_query(messages)
    requested_age = _extract_requested_age(query)
    if requested_age is None:
        return ""

    courses = _get_available_courses(page_context)
    if not courses:
        return ""

    matched = [course for course in courses if _age_matches_rule(requested_age, course.get("Age", ""))]
    if not matched:
        return (
            f"年龄匹配预处理结果：用户提到年龄 {requested_age} 岁，"
            "但在当前页面结构化课程数据中没有匹配到 Age 范围。"
        )

    lines = []
    for course in matched[:8]:
        parts = [
            f"Course: {course.get('Course', '')}",
            f"Age: {course.get('Age', '')}",
        ]
        for key in ("Time", "Weekday", "Location", "Price", "Start Date", "Type"):
            if course.get(key):
                parts.append(f"{key}: {course[key]}")
        lines.append(" | ".join(parts))

    return (
        f"年龄匹配预处理结果：用户提到年龄 {requested_age} 岁，以下课程匹配该年龄范围：\n"
        + "\n".join(lines)
    )


def _build_age_template_reply(messages, page_context, language_name):
    query = _extract_recent_user_query(messages)
    if not _is_age_query(query):
        return ""

    requested_ages = _extract_requested_ages(query)

    courses = _get_available_courses(page_context)
    if not courses:
        if language_name == "English":
            return (
                "I can't find course data on this page right now.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        if language_name == "Bahasa Melayu":
            return (
                "Saya belum jumpa data kursus pada halaman ini.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        return (
            "我这边暂时没有在本页找到课程数据。\n"
            f"{_build_contact_cta(language_name, query)}"
        )

    if not requested_ages:
        age_ranges = []
        for course in courses:
            age_rule = (course.get("Age", "") or "").strip()
            if age_rule and age_rule not in age_ranges:
                age_ranges.append(age_rule)

        top_courses = courses[:2]
        if language_name == "English":
            lines = [f"Available age ranges: {', '.join(age_ranges) if age_ranges else 'See course list'}"]
            for idx, course in enumerate(top_courses, start=1):
                lines.append(f"{idx}. Course: {course.get('Course', '')} ({course.get('Age', '')})")
            return "\n".join(lines[:3])
        if language_name == "Bahasa Melayu":
            lines = [f"Julat umur tersedia: {', '.join(age_ranges) if age_ranges else 'Rujuk senarai kursus'}"]
            for idx, course in enumerate(top_courses, start=1):
                lines.append(f"{idx}. Kursus: {course.get('Course', '')} ({course.get('Age', '')})")
            return "\n".join(lines[:3])

        lines = [f"本页可报名年龄范围：{'、'.join(age_ranges) if age_ranges else '请查看课程列表'}"]
        for idx, course in enumerate(top_courses, start=1):
            lines.append(f"{idx}. 课程名：{course.get('Course', '')}（{course.get('Age', '')}）")
        return "\n".join(lines[:3])

    if len(requested_ages) > 1:
        if language_name == "English":
            lines = ["Age matching results:"]
            for age in requested_ages[:3]:
                matched = [course for course in courses if _age_matches_rule(age, course.get("Age", ""))]
                if matched:
                    names = ", ".join(
                        [
                            (
                                f"{item.get('Course', '')} ({item.get('Age', '')})"
                                + (f" -> {_short_page_label(item.get('URL', ''))}" if item.get("URL") else "")
                            )
                            for item in matched[:2]
                        ]
                    )
                    lines.append(f"- Age {age}: {names}")
                else:
                    lines.append(f"- Age {age}: no direct match on this page")
            lines.append(_build_contact_cta(language_name, query))
            return "\n".join(lines[:5])
        if language_name == "Bahasa Melayu":
            lines = ["Keputusan padanan umur:"]
            for age in requested_ages[:3]:
                matched = [course for course in courses if _age_matches_rule(age, course.get("Age", ""))]
                if matched:
                    names = ", ".join(
                        [
                            (
                                f"{item.get('Course', '')} ({item.get('Age', '')})"
                                + (f" -> {_short_page_label(item.get('URL', ''))}" if item.get("URL") else "")
                            )
                            for item in matched[:2]
                        ]
                    )
                    lines.append(f"- Umur {age}: {names}")
                else:
                    lines.append(f"- Umur {age}: tiada padanan terus pada halaman ini")
            lines.append(_build_contact_cta(language_name, query))
            return "\n".join(lines[:5])

        lines = ["按年龄匹配结果："]
        for age in requested_ages[:3]:
            matched = [course for course in courses if _age_matches_rule(age, course.get("Age", ""))]
            if matched:
                names = "、".join(
                    [
                        (
                            f"{item.get('Course', '')}（{item.get('Age', '')}）"
                            + (f"（页面: {_short_page_label(item.get('URL', ''))}）" if item.get("URL") else "")
                        )
                        for item in matched[:2]
                    ]
                )
                lines.append(f"- {age}岁：{names}")
            else:
                lines.append(f"- {age}岁：本页暂时没有直接匹配课程")
        lines.append(_build_contact_cta(language_name, query))
        return "\n".join(lines[:5])

    requested_age = requested_ages[0]
    matched = [course for course in courses if _age_matches_rule(requested_age, course.get("Age", ""))]
    if not matched:
        age_ranges = []
        for course in courses:
            age_rule = (course.get("Age", "") or "").strip()
            if age_rule and age_rule not in age_ranges:
                age_ranges.append(age_rule)
        if language_name == "English":
            return (
                f"For age {requested_age}, there is no direct match on this page right now.\n"
                f"Available age ranges: {', '.join(age_ranges) if age_ranges else 'See course list'}\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        if language_name == "Bahasa Melayu":
            return (
                f"Untuk umur {requested_age}, belum ada padanan terus pada halaman ini.\n"
                f"Julat umur tersedia: {', '.join(age_ranges) if age_ranges else 'Rujuk senarai kursus'}\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        return (
            f"{requested_age}岁：本页暂时没有直接匹配课程。\n"
            f"本页可报名年龄范围：{'、'.join(age_ranges) if age_ranges else '请查看课程列表'}\n"
            f"{_build_contact_cta(language_name, query)}"
        )

    lines = []
    max_items = 2
    if language_name == "English":
        lines.append(f"For age {requested_age}, these courses are suitable:")
        for idx, course in enumerate(matched[:max_items], start=1):
            weekday = course.get("Weekday", "")
            time = course.get("Time", "")
            location = course.get("Location", "")
            time_location = ", ".join([part for part in [weekday, time, location] if part])
            lines.append(f"{idx}. Course: {course.get('Course', '')}")
            lines.append(f"   Age: {course.get('Age', '')}")
            lines.append(f"   Time/Location: {time_location or 'See course page'}")
            if course.get("URL"):
                lines.append(f"   Page: {_short_page_label(course.get('URL', ''))}")
    elif language_name == "Bahasa Melayu":
        lines.append(f"Untuk umur {requested_age}, kursus yang sesuai:")
        for idx, course in enumerate(matched[:max_items], start=1):
            weekday = course.get("Weekday", "")
            time = course.get("Time", "")
            location = course.get("Location", "")
            time_location = ", ".join([part for part in [weekday, time, location] if part])
            lines.append(f"{idx}. Kursus: {course.get('Course', '')}")
            lines.append(f"   Umur: {course.get('Age', '')}")
            lines.append(f"   Masa/Lokasi: {time_location or 'Rujuk halaman kursus'}")
            if course.get("URL"):
                lines.append(f"   Halaman: {_short_page_label(course.get('URL', ''))}")
    else:
        lines.append(f"{requested_age}岁可参考以下课程：")
        for idx, course in enumerate(matched[:max_items], start=1):
            weekday = course.get("Weekday", "")
            time = course.get("Time", "")
            location = course.get("Location", "")
            time_location = "，".join([part for part in [weekday, time, location] if part])
            lines.append(f"{idx}. 课程名：{course.get('Course', '')}")
            lines.append(f"   年龄：{course.get('Age', '')}")
            lines.append(f"   时间地点：{time_location or '请查看课程页'}")
            if course.get("URL"):
                lines.append(f"   页面：{_short_page_label(course.get('URL', ''))}")

    return "\n".join(lines[: 1 + max_items * 4])


def _normalize_phone_for_whatsapp(raw_phone):
    if not raw_phone:
        return ""
    return re.sub(r"\D", "", str(raw_phone))


def _resolve_contact_page_url():
    try:
        from portfolio.models import ContactPage

        page = ContactPage.objects.live().public().first()
        if page:
            full_url = (getattr(page, "full_url", "") or "").strip()
            if full_url:
                lowered = full_url.lower()
                if "://localhost" not in lowered and "://127.0.0.1" not in lowered:
                    return full_url
            relative_url = (getattr(page, "url", "") or "").strip()
            if relative_url:
                return relative_url
    except Exception:
        pass
    return "/contact/"


def _resolve_whatsapp_link():
    env_phone = (os.environ.get("AI_ASSISTANT_WHATSAPP_PHONE", "") or "").strip()
    phone_digits = _normalize_phone_for_whatsapp(env_phone)
    if phone_digits:
        return f"https://wa.me/{phone_digits}"

    try:
        from portfolio.models import ContactPage

        page = ContactPage.objects.live().public().first()
        phone_digits = _normalize_phone_for_whatsapp(getattr(page, "phone", ""))
        if phone_digits:
            return f"https://wa.me/{phone_digits}"
    except Exception:
        pass

    return ""


def _append_whatsapp_prefill(whatsapp_link, prefill_text):
    if not whatsapp_link:
        return ""

    text = (prefill_text or "").strip()
    if not text:
        return whatsapp_link

    separator = "&" if "?" in whatsapp_link else "?"
    return f"{whatsapp_link}{separator}text={quote_plus(text[:240])}"


def _build_contact_cta(language_name, user_query=""):
    whatsapp_link = _append_whatsapp_prefill(_resolve_whatsapp_link(), user_query)
    contact_url = _resolve_contact_page_url()

    if language_name == "English":
        if whatsapp_link:
            return f"If you want, message us on WhatsApp and we can help arrange a suitable plan: {whatsapp_link}"
        return f"If you want, contact us and we can help arrange a suitable plan: {contact_url}"

    if language_name == "Bahasa Melayu":
        if whatsapp_link:
            return f"Jika anda mahu, WhatsApp kami dan kami boleh bantu aturkan pelan yang sesuai: {whatsapp_link}"
        return f"Jika anda mahu, hubungi kami dan kami boleh bantu aturkan pelan yang sesuai: {contact_url}"

    if whatsapp_link:
        return f"如果你愿意，可以直接 WhatsApp 我们，我们帮你安排合适方案：{whatsapp_link}"
    return f"如果你愿意，可以联系我们，我们帮你安排合适方案：{contact_url}"


def _is_contact_query(query):
    text = (query or "").strip().lower()
    if not text:
        return False

    markers = (
        "contact",
        "contacts",
        "contact us",
        "phone",
        "tel",
        "whatsapp",
        "whatapp",
        "wa",
        "联系方式",
        "联络",
        "联系",
        "电话",
        "wechat",
        "hubungi",
        "nombor",
        "nomor",
        "telefon",
    )
    return any(marker in text for marker in markers)


def _build_contact_reply(messages, language_name):
    query = _extract_recent_user_query(messages)
    if not _is_contact_query(query):
        return ""

    contact_url = _resolve_contact_page_url()
    whatsapp_link = _append_whatsapp_prefill(_resolve_whatsapp_link(), query)

    if language_name == "English":
        if whatsapp_link:
            return (
                "You can contact us on WhatsApp:\n"
                f"{whatsapp_link}\n"
                f"Contact page: {contact_url}"
            )
        return f"Please use our contact page: {contact_url}"

    if language_name == "Bahasa Melayu":
        if whatsapp_link:
            return (
                "Anda boleh hubungi kami melalui WhatsApp:\n"
                f"{whatsapp_link}\n"
                f"Halaman contact: {contact_url}"
            )
        return f"Sila gunakan halaman contact kami: {contact_url}"

    if whatsapp_link:
        return (
            "你可以点击这个 WhatsApp 链接直接联系：\n"
            f"{whatsapp_link}\n"
            f"联系页面：{contact_url}"
        )
    return f"请使用联系页面：{contact_url}"


def _build_local_faq_reply(messages, language_name):
    query = _extract_recent_user_query(messages)
    lower_query = (query or "").lower()
    if not lower_query:
        return ""

    recent_text_chunks = []
    for item in messages[-8:]:
        if isinstance(item, dict) and isinstance(item.get("content"), str):
            recent_text_chunks.append(item.get("content").strip().lower())
    recent_text = " ".join(recent_text_chunks)

    art_markers = ("art", "绘画", "美术", "画画", "seni", "lukis")
    benefit_markers = ("好处", "益处", "作用", "帮助", "benefit", "advantages", "help", "kebaikan", "faedah")
    future_ai_markers = (
        "ai时代",
        "人工智能时代",
        "未来",
        "future",
        "future-ready",
        "ai era",
        "masa depan",
    )

    has_art_context = any(marker in lower_query for marker in art_markers) or any(
        marker in recent_text for marker in art_markers
    )
    asks_benefits = any(marker in lower_query for marker in benefit_markers)
    asks_future_ai = any(marker in lower_query for marker in future_ai_markers)

    if has_art_context and asks_benefits and asks_future_ai:
        if language_name == "English":
            return (
                "Art learning gives children long-term advantages in the AI era:\n"
                "1. Creativity and original thinking that AI cannot fully replace.\n"
                "2. Better observation and visual communication for digital work.\n"
                "3. Stronger problem-solving through experimentation and iteration.\n"
                "4. Confidence in presenting ideas across human-AI collaboration."
            )
        if language_name == "Bahasa Melayu":
            return (
                "Seni memberi kelebihan jangka panjang dalam era AI:\n"
                "1. Kreativiti dan pemikiran asli yang sukar diganti AI.\n"
                "2. Pemerhatian dan komunikasi visual yang penting dalam kerja digital.\n"
                "3. Kemahiran menyelesaikan masalah melalui eksperimen dan iterasi.\n"
                "4. Keyakinan membentangkan idea dalam kolaborasi manusia-AI."
            )
        return (
            "学习艺术在未来AI时代有这些优势：\n"
            "1. 培养创造力与原创思维，这是AI最难替代的能力。\n"
            "2. 强化观察力与视觉表达，适用于数字内容与设计沟通。\n"
            "3. 通过反复练习提升解决问题能力与审美判断。\n"
            "4. 增强表达与展示自信，更适应人机协作场景。"
        )

    expand_markers = (
        "除了画画",
        "除了画画还",
        "还能学什么",
        "还可以学什么",
        "besides drawing",
        "what else can",
        "what else do",
        "selain melukis",
        "boleh belajar apa lagi",
    )
    asks_expand = any(marker in lower_query for marker in expand_markers)
    if has_art_context and asks_expand:
        if language_name == "English":
            return (
                "Besides drawing, children also learn:\n"
                "1. Observation and visual analysis.\n"
                "2. Color sense and composition.\n"
                "3. Focus, patience, and discipline.\n"
                "4. Creativity, storytelling, and self-expression.\n"
                "5. Problem-solving through trial and revision."
            )
        if language_name == "Bahasa Melayu":
            return (
                "Selain melukis, kanak-kanak juga belajar:\n"
                "1. Pemerhatian dan analisis visual.\n"
                "2. Rasa warna dan komposisi.\n"
                "3. Fokus, sabar, dan disiplin.\n"
                "4. Kreativiti, penceritaan, dan ekspresi diri.\n"
                "5. Penyelesaian masalah melalui percubaan dan pembaikan."
            )
        return (
            "除了画画，小孩还会学到：\n"
            "1. 观察力与视觉分析能力。\n"
            "2. 色彩感与构图能力。\n"
            "3. 专注力、耐心和纪律性。\n"
            "4. 创造力、叙事与表达能力。\n"
            "5. 通过反复修改建立解决问题能力。"
        )

    if not (has_art_context and asks_benefits):
        return ""

    if language_name == "English":
        return (
            "Art learning helps children in several ways:\n"
            "1. Builds creativity and visual expression.\n"
            "2. Improves focus, patience, and task completion.\n"
            "3. Strengthens observation, color, and composition skills.\n"
            "4. Increases confidence through completed work."
        )
    if language_name == "Bahasa Melayu":
        return (
            "Belajar seni membantu kanak-kanak dalam beberapa aspek:\n"
            "1. Meningkatkan kreativiti dan ekspresi visual.\n"
            "2. Melatih fokus, kesabaran, dan disiplin menyiapkan tugasan.\n"
            "3. Menguatkan kemahiran pemerhatian, warna, dan komposisi.\n"
            "4. Membina keyakinan melalui hasil karya."
        )

    return (
        "学习美术对小孩有这些帮助：\n"
        "1. 提升创造力与表达能力。\n"
        "2. 训练专注力、耐心和完成任务的习惯。\n"
        "3. 增强观察力、色彩感与构图能力。\n"
        "4. 通过作品积累自信。"
    )


def _is_art_interest_query(query):
    text = (query or "").strip().lower()
    if not text:
        return False

    art_markers = ("画画", "绘画", "美术", "art", "drawing", "lukis", "seni")
    child_markers = ("孩子", "小孩", "小朋友", "kid", "kids", "child", "children", "anak")
    intent_markers = ("想", "要", "学", "learn", "want", "interested", "nak", "mahu", "belajar")
    return (
        any(marker in text for marker in art_markers)
        and any(marker in text for marker in child_markers)
        and any(marker in text for marker in intent_markers)
    )


def _build_art_interest_reply(messages, page_context, language_name):
    query = _extract_recent_user_query(messages)
    if not _is_art_interest_query(query):
        return ""

    courses = _get_available_courses(page_context)
    if not courses:
        if language_name == "English":
            return (
                "Great question. We can recommend based on your child's age and location.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        if language_name == "Bahasa Melayu":
            return (
                "Soalan yang baik. Kami boleh cadangkan ikut umur anak dan lokasi anda.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        return (
            "这个问题很好。我们可以按孩子年龄和地点帮你推荐。\n"
            f"{_build_contact_cta(language_name, query)}"
        )

    top_courses = courses[:3]
    if language_name == "English":
        lines = ["Great choice. These art courses may fit your child:"]
        for course in top_courses:
            lines.append(
                f"- {course.get('Course', '')} | Age: {course.get('Age', '-')}"
                f" | Time: {course.get('Time', '-')}"
                f" | Location: {course.get('Location', '-')}"
                f" | Page: {_short_page_label(course.get('URL', ''))}"
            )
        lines.append("Tell me your child's age and preferred location, and I can narrow it down for you.")
        return "\n".join(lines)

    if language_name == "Bahasa Melayu":
        lines = ["Pilihan yang baik. Kursus seni ini mungkin sesuai:"]
        for course in top_courses:
            lines.append(
                f"- {course.get('Course', '')} | Umur: {course.get('Age', '-')}"
                f" | Masa: {course.get('Time', '-')}"
                f" | Lokasi: {course.get('Location', '-')}"
                f" | Halaman: {_short_page_label(course.get('URL', ''))}"
            )
        lines.append("Beritahu umur anak dan lokasi pilihan anda, saya boleh cadangkan kursus paling sesuai.")
        return "\n".join(lines)

    lines = ["这个想法很好。以下课程可能适合孩子："]
    for course in top_courses:
        lines.append(
            f"- {course.get('Course', '')} | 年龄: {course.get('Age', '-')}"
            f" | 时间: {course.get('Time', '-')}"
            f" | 地点: {course.get('Location', '-')}"
            f" | 页面: {_short_page_label(course.get('URL', ''))}"
        )
    lines.append("你告诉我孩子年龄和方便地点，我可以帮你缩小到最合适的1-2个课程。")
    return "\n".join(lines)


def _is_course_list_query(query):
    text = (query or "").strip().lower()
    if not text:
        return False

    markers = (
        "课程",
        "课",
        "看看课程",
        "介绍课程",
        "有什么课",
        "course",
        "courses",
        "class",
        "classes",
        "show me",
        "list",
        "kursus",
        "kelas",
    )
    return any(marker in text for marker in markers)


def _is_product_query(query):
    text = (query or "").strip().lower()
    if not text:
        return False

    product_markers = (
        "产品",
        "商品",
        "卖什么",
        "有卖",
        "东西",
        "product",
        "products",
        "sell",
        "sale",
        "shop",
        "barang",
        "produk",
        "jual",
    )
    return any(marker in text for marker in product_markers)


def _build_product_list_reply(messages, page_context, language_name):
    query = _extract_recent_user_query(messages)
    if not _is_product_query(query):
        return ""

    products = _get_available_products(page_context)
    if not products:
        if language_name == "English":
            return (
                "I can't find a product list on this page right now.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        if language_name == "Bahasa Melayu":
            return (
                "Saya belum jumpa senarai produk pada halaman ini.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        return (
            "我这边暂时没有在本页找到产品列表。\n"
            f"{_build_contact_cta(language_name, query)}"
        )

    top_products = products[:5]
    if language_name == "English":
        lines = ["We currently have these products:"]
        for idx, item in enumerate(top_products, start=1):
            lines.append(
                f"{idx}. {item.get('Product', '')} | Price: {item.get('Price', '-')}"
                f" | Page: {_short_page_label(item.get('URL', ''))}"
            )
        return "\n".join(lines)

    if language_name == "Bahasa Melayu":
        lines = ["Produk semasa kami:"]
        for idx, item in enumerate(top_products, start=1):
            lines.append(
                f"{idx}. {item.get('Product', '')} | Harga: {item.get('Price', '-')}"
                f" | Halaman: {_short_page_label(item.get('URL', ''))}"
            )
        return "\n".join(lines)

    lines = ["我们目前有这些产品："]
    for idx, item in enumerate(top_products, start=1):
        lines.append(
            f"{idx}. {item.get('Product', '')} | 价格: {item.get('Price', '-')}"
            f" | 页面: {_short_page_label(item.get('URL', ''))}"
        )
    return "\n".join(lines)


def _is_course_page_query(query):
    text = (query or "").strip().lower()
    if not text:
        return False

    page_markers = (
        "在哪一页",
        "在哪页",
        "在那一页",
        "在那页",
        "哪一页",
        "哪页",
        "页面",
        "page",
        "link",
        "url",
    )
    course_markers = ("课程", "course", "courses", "class", "classes", "kursus", "kelas")
    return any(marker in text for marker in page_markers) and any(marker in text for marker in course_markers)


def _build_course_page_reply(messages, page_context, language_name):
    query = _extract_recent_user_query(messages)
    if not _is_course_page_query(query):
        return ""

    courses = _get_available_courses(page_context)
    if not courses:
        if language_name == "English":
            return (
                "I can't find course page links on this page yet.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        if language_name == "Bahasa Melayu":
            return (
                "Saya belum jumpa pautan halaman kursus pada halaman ini.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        return (
            "我这边暂时没有在本页找到课程页面链接。\n"
            f"{_build_contact_cta(language_name, query)}"
        )

    top_courses = courses[:6]
    if language_name == "English":
        lines = ["Course pages:"]
        for idx, course in enumerate(top_courses, start=1):
            lines.append(f"{idx}. {course.get('Course', '')} -> {_short_page_label(course.get('URL', ''))}")
        return "\n".join(lines)

    if language_name == "Bahasa Melayu":
        lines = ["Halaman kursus:"]
        for idx, course in enumerate(top_courses, start=1):
            lines.append(f"{idx}. {course.get('Course', '')} -> {_short_page_label(course.get('URL', ''))}")
        return "\n".join(lines)

    lines = ["课程页面如下："]
    for idx, course in enumerate(top_courses, start=1):
        lines.append(f"{idx}. {course.get('Course', '')} -> {_short_page_label(course.get('URL', ''))}")
    return "\n".join(lines)


def _is_registration_query(query):
    text = (query or "").strip().lower()
    if not text:
        return False

    markers = (
        "报名",
        "报课",
        "怎么报",
        "如何报",
        "我要报名",
        "register",
        "signup",
        "sign up",
        "enroll",
        "enrol",
        "join class",
        "daftar",
    )
    return any(marker in text for marker in markers)


def _build_registration_reply(messages, page_context, language_name):
    query = _extract_recent_user_query(messages)
    if not _is_registration_query(query):
        return ""

    courses = _get_available_courses(page_context)
    top_courses = courses[:3]

    if language_name == "English":
        lines = ["You can register in 3 quick steps:"]
        lines.append("1. Pick a suitable course (age/time/location).")
        lines.append("2. Open the course page and review schedule details.")
        lines.append("3. Submit your registration through the page/contact method shown there.")
        if top_courses:
            lines.append("Suggested pages:")
            for course in top_courses:
                lines.append(f"- {course.get('Course', '')}: {_short_page_label(course.get('URL', ''))}")
        else:
            lines.append(_build_contact_cta(language_name, query))
        return "\n".join(lines)

    if language_name == "Bahasa Melayu":
        lines = ["Anda boleh daftar dalam 3 langkah ringkas:"]
        lines.append("1. Pilih kursus yang sesuai (umur/masa/lokasi).")
        lines.append("2. Buka halaman kursus dan semak jadual.")
        lines.append("3. Hantar pendaftaran melalui kaedah pada halaman tersebut.")
        if top_courses:
            lines.append("Halaman dicadangkan:")
            for course in top_courses:
                lines.append(f"- {course.get('Course', '')}: {_short_page_label(course.get('URL', ''))}")
        else:
            lines.append(_build_contact_cta(language_name, query))
        return "\n".join(lines)

    lines = ["可以按这 3 步报名："]
    lines.append("1. 先选合适课程（年龄/时间/地点）。")
    lines.append("2. 打开对应课程页面，确认上课安排。")
    lines.append("3. 按页面显示的报名/联系方式提交资料。")
    if top_courses:
        lines.append("你可以先看这些页面：")
        for course in top_courses:
            lines.append(f"- {course.get('Course', '')}：{_short_page_label(course.get('URL', ''))}")
    else:
        lines.append(_build_contact_cta(language_name, query))
    return "\n".join(lines)


def _build_course_list_reply(messages, page_context, language_name):
    query = _extract_recent_user_query(messages)
    if not _is_course_list_query(query):
        return ""

    courses = _get_available_courses(page_context)
    if not courses:
        if language_name == "English":
            return (
                "I can't find course details on this page right now.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        if language_name == "Bahasa Melayu":
            return (
                "Saya belum jumpa butiran kursus pada halaman ini.\n"
                f"{_build_contact_cta(language_name, query)}"
            )
        return (
            "我这边暂时没有在本页找到课程详情。\n"
            f"{_build_contact_cta(language_name, query)}"
        )

    top_courses = courses[:3]
    if language_name == "English":
        lines = ["Current courses on this page:"]
        for idx, course in enumerate(top_courses, start=1):
            lines.append(f"{idx}. {course.get('Course', '')}")
            lines.append(f"   Age: {course.get('Age', '-')}")
            lines.append(f"   Time: {course.get('Time', '-')}")
            lines.append(f"   Location: {course.get('Location', '-')}")
            lines.append(f"   Price: {course.get('Price', '-')}")
            lines.append(f"   Page: {_short_page_label(course.get('URL', ''))}")
        return "\n".join(lines)

    if language_name == "Bahasa Melayu":
        lines = ["Kursus di halaman ini:"]
        for idx, course in enumerate(top_courses, start=1):
            lines.append(f"{idx}. {course.get('Course', '')}")
            lines.append(f"   Umur: {course.get('Age', '-')}")
            lines.append(f"   Masa: {course.get('Time', '-')}")
            lines.append(f"   Lokasi: {course.get('Location', '-')}")
            lines.append(f"   Harga: {course.get('Price', '-')}")
            lines.append(f"   Halaman: {_short_page_label(course.get('URL', ''))}")
        return "\n".join(lines)

    lines = ["本页课程如下："]
    for idx, course in enumerate(top_courses, start=1):
        lines.append(f"{idx}. {course.get('Course', '')}")
        lines.append(f"   年龄: {course.get('Age', '-')}")
        lines.append(f"   时间: {course.get('Time', '-')}")
        lines.append(f"   地点: {course.get('Location', '-')}")
        lines.append(f"   价格: {course.get('Price', '-')}")
        lines.append(f"   页面: {_short_page_label(course.get('URL', ''))}")
    return "\n".join(lines)


@require_POST
def ai_assistant_chat(request_):
    expected_token = os.environ.get("AI_ASSISTANT_API_TOKEN", "").strip()
    if expected_token:
        provided_token = request_.headers.get("X-AI-Token", "").strip()
        if provided_token != expected_token:
            return JsonResponse(
                {
                    "error": "Unauthorized",
                    "reply": "当前 AI 服务未授权访问。",
                },
                status=401,
            )

    try:
        payload = json.loads(request_.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    messages = payload.get("messages") or []
    raw_page_context = payload.get("page_context")
    raw_page_title = payload.get("page_title")
    raw_page_url = payload.get("page_url")

    if raw_page_context is None:
        page_context = ""
    elif isinstance(raw_page_context, str):
        page_context = raw_page_context.strip()
    else:
        return JsonResponse({"error": "page_context must be a string."}, status=400)

    if not isinstance(messages, list):
        return JsonResponse({"error": "messages must be a list."}, status=400)

    page_title = raw_page_title.strip() if isinstance(raw_page_title, str) else ""
    page_url = raw_page_url.strip() if isinstance(raw_page_url, str) else ""
    language_name, language_rule = _detect_response_language(messages)

    contact_reply = _build_contact_reply(messages, language_name)
    if contact_reply:
        return JsonResponse({"reply": contact_reply})

    local_faq_reply = _build_local_faq_reply(messages, language_name)
    if local_faq_reply:
        return JsonResponse({"reply": local_faq_reply})

    art_interest_reply = _build_art_interest_reply(messages, page_context, language_name)
    if art_interest_reply:
        return JsonResponse({"reply": art_interest_reply})

    age_template_reply = _build_age_template_reply(messages, page_context, language_name)
    if age_template_reply:
        return JsonResponse({"reply": age_template_reply})

    registration_reply = _build_registration_reply(messages, page_context, language_name)
    if registration_reply:
        return JsonResponse({"reply": registration_reply})

    product_list_reply = _build_product_list_reply(messages, page_context, language_name)
    if product_list_reply:
        return JsonResponse({"reply": product_list_reply})

    course_page_reply = _build_course_page_reply(messages, page_context, language_name)
    if course_page_reply:
        return JsonResponse({"reply": course_page_reply})

    course_list_reply = _build_course_list_reply(messages, page_context, language_name)
    if course_list_reply:
        return JsonResponse({"reply": course_list_reply})

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if _is_placeholder_openai_key(api_key):
        return JsonResponse(
            {
                "error": "OPENAI_API_KEY is not configured correctly.",
                "reply": "当前 AI 服务密钥未正确配置，请检查服务器环境变量中的 OPENAI_API_KEY，避免使用 your-key 这类占位值。",
            },
            status=503,
        )

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    endpoint = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")

    site_query = _extract_recent_user_query(messages)
    site_context = _build_site_context(site_query)
    business_focus = _infer_business_focus(page_title, page_context, site_context)

    system_prompt = (
        "你是网站内嵌销售与内容助手。请严格按页面事实回答，不要泛泛介绍。\n"
        f"当前页面推断业务重点：{business_focus}\n"
        f"本次回复语言：{language_name}\n"
        "回答规则：\n"
        "1) 先一句话说明该页面卖什么或提供什么服务。\n"
        "2) 再回答用户问题，优先使用页面里的课程、产品、价格、时间、地点信息。\n"
        "2.1) 若用户询问孩子年龄适合什么课程，优先使用课程的 Age 字段做匹配，给出课程名称与关键信息。\n"
        "2.2) 若存在多个匹配课程，按列表形式给出，不少于 2 条关键信息（如时间/地点/价格）。\n"
        "2.3) 若用户只说“7岁呢/8岁呢”这类短追问，也按年龄匹配问题处理，不要回答无法确认。\n"
        "3) 不编造价格、库存、联系方式、优惠或承诺。\n"
        "4) 信息不足时，明确说根据当前页面信息暂时无法确认，并给下一步建议。\n"
        "5) 输出格式必须是纯文本，不要使用 Markdown（例如 **、#、`、表格）。\n"
        "6) 句子简短，优先分行展示；总长度控制在 6 行以内。\n"
        f"7) 语言规则：{language_rule}"
    )

    llm_messages = [{"role": "system", "content": system_prompt}]

    if page_title or page_url:
        llm_messages.append(
            {
                "role": "system",
                "content": f"页面元信息:\nTitle: {page_title[:200]}\nURL: {page_url[:500]}",
            }
        )

    if page_context:
        llm_messages.append(
            {
                "role": "system",
                "content": f"当前页面文本上下文（可能被截断）:\n{page_context[:10000]}",
            }
        )

    age_match_hint = _build_age_match_hint(messages, page_context)
    if age_match_hint:
        llm_messages.append({"role": "system", "content": age_match_hint[:2000]})

    if site_context:
        llm_messages.append(
            {
                "role": "system",
                "content": f"全站相关页面检索结果（可能被截断）:\n{site_context[:6000]}",
            }
        )

    for item in messages[-12:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        raw_content = item.get("content")
        if raw_content is None:
            content = ""
        elif isinstance(raw_content, str):
            content = raw_content.strip()
        else:
            continue
        if role in {"user", "assistant"} and content:
            llm_messages.append({"role": role, "content": content[:2000]})

    body = {
        "model": model,
        "messages": llm_messages,
        "temperature": 0.2,
    }

    req = request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return JsonResponse(
            {
                "error": "LLM upstream HTTP error",
                "detail": detail[:1000],
                "reply": "AI 服务暂时不可用，请稍后重试。",
            },
            status=502,
        )
    except Exception as exc:
        return JsonResponse(
            {
                "error": "LLM request failed",
                "detail": str(exc),
                "reply": "AI 服务连接失败，请稍后再试。",
            },
            status=502,
        )

    reply = ""
    choices = data.get("choices") or []
    if choices:
        reply = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()

    if not reply:
        reply = "我暂时没有生成有效回复，请换个问题再试试。"

    return JsonResponse({"reply": reply})
